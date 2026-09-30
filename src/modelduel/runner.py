"""Construye el prompt y ejecuta los tests de una tarea sobre el código de un modelo.

El código generado se ejecuta SIEMPRE en un directorio temporal, en un subproceso con límite
de tiempo y sin las variables de entorno que parecen secretos.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

from modelduel.tasks import TEST_FILE, Task

DEFAULT_TIMEOUT = 20.0
MAX_OUTPUT_CHARS = 12_000

PROMPT_INSTRUCTIONS = """\
---
Instrucciones de formato:
- Responde con UN ÚNICO bloque de código Python delimitado por ```python y ```.
- El bloque debe contener la implementación completa y autocontenida (solo biblioteca estándar).
- No incluyas tests ni código que se ejecute al importar el módulo.
- Respeta exactamente el nombre y la firma de la función pedida."""

_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


class RunnerError(Exception):
    """Error de configuración del runner (no del código del modelo)."""


@dataclass
class TestRun:
    """Resultado de ejecutar los tests de una tarea sobre una solución."""

    status: str  # ok | no_code | import_error | timeout | error
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    duration_s: float = 0.0
    output: str = ""
    message: str = ""

    @property
    def solved(self) -> bool:
        return self.status == "ok" and self.total > 0 and self.passed == self.total

    def to_dict(self) -> dict:
        data = asdict(self)
        data["solved"] = self.solved
        return data


def build_prompt(task: Task) -> str:
    return f"{task.statement}\n\n{PROMPT_INSTRUCTIONS}\n"


def ensure_pytest_available() -> None:
    if importlib.util.find_spec("pytest") is None:
        raise RunnerError(
            "modelduel necesita pytest para ejecutar los tests de las tareas. "
            "Instálalo en este entorno con: pip install pytest"
        )


def safe_env() -> dict[str, str]:
    """Entorno para el subproceso sin claves ni configuración de pytest ajena."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not any(hint in name.upper() for hint in _SECRET_HINTS)
    }
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH", "PYTHONSTARTUP"):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def run_tests(code: str | None, task: Task, timeout: float = DEFAULT_TIMEOUT) -> TestRun:
    """Ejecuta ``test_task.py`` contra ``code`` guardado como ``solution.py``."""
    expected = task.expected_tests
    if code is None:
        return TestRun(
            status="no_code",
            total=expected,
            message="La respuesta no contiene ningún bloque de código.",
        )

    with tempfile.TemporaryDirectory(prefix="modelduel-", ignore_cleanup_errors=True) as tmp:
        workdir = Path(tmp)
        (workdir / "solution.py").write_text(code, encoding="utf-8")
        shutil.copyfile(task.test_path, workdir / TEST_FILE)
        conftest = task.path / "conftest.py"
        if conftest.is_file():
            shutil.copyfile(conftest, workdir / "conftest.py")
        # Un pytest.ini vacío aísla la ejecución de cualquier configuración del usuario.
        (workdir / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        junit = workdir / "junit.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit}",
            TEST_FILE,
        ]
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                env=safe_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            output = _decode(exc.stdout) + _decode(exc.stderr)
            return TestRun(
                status="timeout",
                total=expected,
                duration_s=round(time.perf_counter() - start, 3),
                output=_truncate(output),
                message=f"Los tests superaron el límite de {timeout:g} s y se interrumpieron.",
            )
        duration = round(time.perf_counter() - start, 3)
        output = _truncate(_clean_output(proc.stdout + proc.stderr, workdir))
        counts = parse_junit(junit) if junit.is_file() else None

    if counts is None:
        return TestRun(
            status="error",
            total=expected,
            duration_s=duration,
            output=output,
            message=f"pytest terminó con código {proc.returncode} sin generar resultados.",
        )
    if counts["collection_error"] or (proc.returncode in (2, 3, 4) and counts["total"] == 0):
        return TestRun(
            status="import_error",
            total=expected,
            errors=max(counts["errors"], 1),
            duration_s=duration,
            output=output,
            message="No se pudo importar la solución o recoger los tests.",
        )
    total = counts["total"] or expected
    return TestRun(
        status="ok",
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["errors"],
        skipped=counts["skipped"],
        total=total,
        duration_s=duration,
        output=output,
    )


def parse_junit(path: Path) -> dict | None:
    """Cuenta resultados leyendo el XML JUnit de pytest."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0}
    collection_error = False
    for case in root.iter("testcase"):
        tags = {child.tag for child in case}
        if "error" in tags:
            counts["errors"] += 1
            # Los errores de recogida (p. ej. ImportError) aparecen sin nombre de clase.
            if not case.get("classname"):
                collection_error = True
        elif "failure" in tags:
            counts["failed"] += 1
        elif "skipped" in tags:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    if collection_error:
        counts["total"] = 0
        counts["passed"] = counts["failed"] = counts["skipped"] = 0
    else:
        counts["total"] = sum(counts[k] for k in ("passed", "failed", "errors", "skipped"))
    counts["collection_error"] = collection_error
    return counts


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _clean_output(output: str, workdir: Path) -> str:
    """Quita la ruta del directorio temporal para que el informe no muestre rutas locales."""
    for variant in {str(workdir), str(workdir.resolve()), workdir.as_posix()}:
        output = output.replace(variant, "<tmp>")
    return re.sub(r"\n{3,}", "\n\n", output).strip()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [salida recortada: {len(text) - limit} caracteres más]"
