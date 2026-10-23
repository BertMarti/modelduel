"""Construye el prompt y ejecuta los tests de una tarea sobre el código de un modelo.

El código generado se ejecuta SIEMPRE en un directorio temporal, en un subproceso con límite
de tiempo, sin las variables de entorno que parecen secretos y con ``HOME`` apuntando al
temporal. En POSIX el subproceso arranca además con límites del sistema (``setrlimit``): memoria,
CPU, tamaño de archivo, descriptores y sin volcados de memoria. Al terminar (o al agotar el
tiempo) se mata el árbol de procesos completo: un *Job Object* en Windows y un grupo de procesos
en POSIX. La salida va a un archivo y solo se leen su principio y su final, así que una solución
que imprime sin parar no puede agotar la memoria.

No es un aislamiento real: la solución tiene red y puede leer y escribir rutas absolutas del
disco. Para código no confiable, usa un contenedor o una máquina virtual.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import site
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
# Bytes que se leen como máximo del archivo de salida (mitad del principio, mitad del final).
MAX_READ_BYTES = 256 * 1024

PROMPT_INSTRUCTIONS = """\
---
Instrucciones de formato:
- Responde con UN ÚNICO bloque de código Python delimitado por ```python y ```.
- El bloque debe contener la implementación completa y autocontenida (solo biblioteca estándar).
- No incluyas tests ni código que se ejecute al importar el módulo.
- Respeta exactamente el nombre y la firma de la función pedida."""

# Una variable cuyo nombre contenga alguna de estas piezas no llega a la solución.
_SECRET_HINTS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASS",  # PASSWORD, PASSWD, PASSPHRASE
    "CREDENTIAL",
    "AUTH",  # SSH_AUTH_SOCK (agente SSH), *_AUTH
    "PRIVATE",
    "COOKIE",
    "SESSION",  # AWS_SESSION_TOKEN, DBUS_SESSION_BUS_ADDRESS
    "SIGNATURE",
    "DSN",  # SENTRY_DSN y cadenas de conexión con usuario y contraseña
)
# Variables sin «pista» en el nombre que dan acceso a algo: conexión a bases de datos,
# al demonio de Docker, a Kubernetes o al agente GPG.
_SENSITIVE_VARS = frozenset(
    {"DATABASE_URL", "REDIS_URL", "MONGODB_URI", "DOCKER_HOST", "KUBECONFIG", "GPG_AGENT_INFO"}
)
# Variables de directorios personales que se redirigen al temporal de la ejecución.
_HOME_VARS = (
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
)

# Límites POSIX (``setrlimit``) del subproceso. Windows no tiene ``resource``: allí solo se
# aplican el límite de tiempo y el Job Object que mata el árbol.
MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024  # 1 GiB de espacio de direcciones
FILE_SIZE_LIMIT_BYTES = 64 * 1024 * 1024  # ningún archivo (ni la salida) pasa de 64 MiB
OPEN_FILES_LIMIT = 256
# Margen de CPU sobre el límite de tiempo: el reloj de pared sigue siendo el que manda.
CPU_MARGIN_S = 5

# Arranque del subproceso: aplica los límites y ejecuta pytest en el mismo proceso. Así no hace
# falta ``preexec_fn`` (inseguro con hilos, y modelduel tiene el de la señal de vida).
_BOOTSTRAP = """\
import json, sys
try:
    import resource
except ImportError:
    resource = None
if resource is not None:
    for _name, _value in json.loads(sys.argv[1]).items():
        _res = getattr(resource, _name, None)
        if _res is None:
            continue
        try:
            _soft, _hard = resource.getrlimit(_res)
            if _hard != resource.RLIM_INFINITY:
                _value = min(_value, _hard)
            resource.setrlimit(_res, (_value, _value))
        except (ValueError, OSError):
            pass  # p. ej. RLIMIT_AS en macOS: se sigue con el resto de límites
del sys.argv[1]
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
"""


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


def is_sensitive_var(name: str) -> bool:
    """``True`` si la variable parece un secreto o da acceso a otro servicio."""
    upper = name.upper()
    return upper in _SENSITIVE_VARS or any(hint in upper for hint in _SECRET_HINTS)


def safe_env(home: Path | None = None) -> dict[str, str]:
    """Entorno para el subproceso sin claves ni configuración de pytest ajena.

    Con ``home``, los directorios personales (``HOME``, ``USERPROFILE``, ``XDG_*``…) apuntan
    ahí: ``~/.netrc``, ``~/.aws`` o ``~/.ssh`` no se encuentran por accidente. ``PYTHONUSERBASE``
    conserva el valor real para que un pytest instalado con ``pip install --user`` siga cargando.
    """
    env = {name: value for name, value in os.environ.items() if not is_sensitive_var(name)}
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH", "PYTHONSTARTUP"):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if home is not None:
        env.setdefault("PYTHONUSERBASE", site.getuserbase())
        for name in _HOME_VARS:
            env[name] = str(home)
    return env


def resource_limits(timeout: float) -> dict[str, int]:
    """Límites ``setrlimit`` (por nombre de ``resource``) para una ejecución de ``timeout`` s."""
    return {
        "RLIMIT_AS": MEMORY_LIMIT_BYTES,
        "RLIMIT_CPU": math.ceil(timeout) + CPU_MARGIN_S,
        "RLIMIT_FSIZE": FILE_SIZE_LIMIT_BYTES,
        "RLIMIT_NOFILE": OPEN_FILES_LIMIT,
        "RLIMIT_CORE": 0,
    }


def run_tests(code: str | None, task: Task, timeout: float = DEFAULT_TIMEOUT) -> TestRun:
    """Ejecuta ``test_task.py`` contra ``code`` guardado como ``solution.py``."""
    expected = task.expected_tests
    if code is None:
        return TestRun(
            status="no_code",
            total=expected,
            message="La respuesta no contiene ningún bloque de código.",
        )

    root = Path(tempfile.mkdtemp(prefix="modelduel-"))
    try:
        workdir = root / "work"
        tmpdir = root / "tmp"
        workdir.mkdir()
        tmpdir.mkdir()
        (workdir / "solution.py").write_text(code, encoding="utf-8", errors="replace")
        shutil.copyfile(task.test_path, workdir / TEST_FILE)
        conftest = task.path / "conftest.py"
        if conftest.is_file():
            shutil.copyfile(conftest, workdir / "conftest.py")
        # Un pytest.ini vacío aísla la ejecución de cualquier configuración del usuario.
        (workdir / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        junit = root / "junit.xml"
        output_path = root / "output.log"
        cmd = [
            sys.executable,
            "-c",
            _BOOTSTRAP,
            json.dumps(resource_limits(timeout)),
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit}",
            TEST_FILE,
        ]
        env = safe_env(home=tmpdir)
        # Los temporales de la solución y de pytest se quedan dentro de la ejecución y se borran.
        for name in ("TMP", "TEMP", "TMPDIR"):
            env[name] = str(tmpdir)
        returncode, duration = _execute(cmd, workdir, env, output_path, timeout)
        output = _truncate(_clean_output(_read_capped(output_path), root))
        counts = parse_junit(junit) if junit.is_file() else None
    finally:
        _remove_tree(root)

    if returncode is None:
        return TestRun(
            status="timeout",
            total=expected,
            duration_s=duration,
            output=output,
            message=f"Los tests superaron el límite de {timeout:g} s y se interrumpieron.",
        )
    if returncode == 5 and (counts is None or counts["total"] == 0):
        return TestRun(
            status="error",
            total=expected,
            duration_s=duration,
            output=output,
            message="pytest no encontró ningún test en la tarea: revisa su test_task.py.",
        )
    if counts is None:
        return TestRun(
            status="error",
            total=expected,
            duration_s=duration,
            output=output,
            message=_no_results_message(returncode),
        )
    if counts["collection_error"] or (returncode in (2, 3, 4) and counts["total"] == 0):
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


_LIMIT_SIGNALS = {
    "SIGXCPU": "superó el límite de CPU",
    "SIGXFSZ": f"escribió un archivo de más de {FILE_SIZE_LIMIT_BYTES // (1024 * 1024)} MiB",
    "SIGKILL": "fue terminado a la fuerza (SIGKILL)",
    "SIGSEGV": "falló con una violación de segmento (¿sin memoria?)",
}


def _no_results_message(returncode: int) -> str:
    """Explica un final sin XML; si fue una señal de un límite, lo dice."""
    if returncode < 0:
        try:
            name = signal.Signals(-returncode).name
        except ValueError:
            name = f"señal {-returncode}"
        reason = _LIMIT_SIGNALS.get(name)
        if reason:
            return f"El proceso de los tests {reason} y terminó sin generar resultados."
        return f"El proceso de los tests terminó por la señal {name} sin generar resultados."
    return f"pytest terminó con código {returncode} sin generar resultados."


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


# ---------------------------------------------------------------- subproceso


def _execute(
    cmd: list[str], workdir: Path, env: dict[str, str], output_path: Path, timeout: float
) -> tuple[int | None, float]:
    """Ejecuta ``cmd`` y devuelve ``(código de salida, duración)``; ``None`` si agota el tiempo.

    stdout y stderr van juntos a ``output_path``: un archivo no obliga a esperar a que los
    procesos nietos suelten una tubería. Al volver no queda vivo ningún proceso del árbol
    (salvo los que se desliguen a propósito de él; ver «Problemas conocidos» en MEMORY.md).
    """
    extra: dict = {}
    if os.name != "nt":
        extra["start_new_session"] = True  # grupo de procesos propio para matarlo entero
    start = time.perf_counter()
    with open(output_path, "wb") as out:
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            **extra,
        )
        tree = _ProcessTree(proc)
        try:
            returncode: int | None = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            returncode = None
        finally:
            # También tras un final normal: la solución puede haber dejado hijos en marcha.
            tree.kill()
            proc.wait()
    return returncode, round(time.perf_counter() - start, 3)


class _ProcessTree:
    """Mata un proceso y todos sus descendientes solo con la biblioteca estándar."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self.proc = proc
        self.job = _win_job_for(proc) if os.name == "nt" else None

    def kill(self) -> None:
        if os.name != "nt":
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.proc.pid, signal.SIGKILL)
            return
        if self.job is not None:  # pragma: no cover - solo Windows
            _win_terminate_job(self.job)
            self.job = None
        elif self.proc.poll() is None:  # pragma: no cover - solo Windows sin Job Object
            # taskkill recorre el árbol mientras el proceso padre siga vivo.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def _kernel32():  # pragma: no cover - solo Windows
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _win_job_for(proc: subprocess.Popen) -> int | None:  # pragma: no cover - solo Windows
    """Mete ``proc`` en un Job Object nuevo (sus hijos entran solos). ``None`` si no se puede."""
    try:
        kernel32 = _kernel32()
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        if not kernel32.AssignProcessToJobObject(job, int(proc._handle)):  # type: ignore[attr-defined]
            kernel32.CloseHandle(job)
            return None
        return job
    except (OSError, AttributeError, ValueError):
        return None


def _win_terminate_job(job: int) -> None:  # pragma: no cover - solo Windows
    kernel32 = _kernel32()
    kernel32.TerminateJobObject(job, 1)
    kernel32.CloseHandle(job)


def _remove_tree(path: Path) -> None:
    """Borra el temporal; en Windows reintenta porque un proceso recién muerto tarda en soltarlo."""
    for _ in range(10):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.2)


# ---------------------------------------------------------------- salida


def _read_capped(path: Path, limit: int = MAX_READ_BYTES) -> str:
    """Lee como mucho ``limit`` bytes del archivo: su principio y su final."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size <= limit:
                return fh.read().decode("utf-8", errors="replace")
            half = limit // 2
            head = fh.read(half)
            fh.seek(size - half)
            tail = fh.read(half)
    except OSError:
        return ""
    return (
        head.decode("utf-8", errors="replace")
        + f"\n… [salida recortada: {size - 2 * half} bytes omitidos] …\n"
        + tail.decode("utf-8", errors="replace")
    )


def _clean_output(output: str, root: Path) -> str:
    """Normaliza los finales de línea y quita la ruta del temporal para no mostrar rutas locales."""
    output = output.replace("\r\n", "\n").replace("\r", "\n")
    variants: set[str] = set()
    for base in (root / "work", root):
        for form in (base, base.resolve()):
            variants |= {str(form), form.as_posix()}
    # Primero las más largas, para que ``<root>/work`` no quede como ``<tmp>/work``.
    for variant in sorted(variants, key=len, reverse=True):
        output = output.replace(variant, "<tmp>")
    return re.sub(r"\n{3,}", "\n\n", output).strip()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Conserva el principio y el final: pytest imprime el resumen al final."""
    if len(text) <= limit:
        return text
    half = limit // 2
    omitted = len(text) - 2 * half
    return f"{text[:half]}\n… [salida recortada: {omitted} caracteres omitidos] …\n{text[-half:]}"
