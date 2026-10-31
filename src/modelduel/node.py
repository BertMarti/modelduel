"""Node.js para las tareas en JavaScript y TypeScript (experimental, desde la 1.1.0).

modelduel no instala Node ni lo necesita para las tareas de Python: solo lo busca en el PATH
cuando hay alguna tarea de JavaScript o TypeScript. Los tests de esas tareas usan el ejecutor
nativo de Node (``node:test``) y se lanzan con el MISMO runner que los de Python (temporal propio,
entorno sin secretos, límites ``setrlimit``, supervisor, red cortada, contenedor…); además, Node
corre con su modelo de permisos: solo puede leer y escribir en la carpeta de la ejecución y no
puede lanzar procesos, *workers* ni complementos nativos.

TypeScript: Node >= 22.6 borra las anotaciones de tipo al cargar (*type stripping*); no
comprueba los tipos. Antes de la 22.18 (y en la 23 antes de la 23.6) hay que pedirlo con
``--experimental-strip-types``.
"""

from __future__ import annotations

import functools
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

Version = tuple[int, int, int]

NODE_URL = "https://nodejs.org/es/download"
# --disable-warning llegó a la rama 20 en la 20.11.
MIN_NODE: Version = (20, 11, 0)
MIN_NODE_TS: Version = (22, 6, 0)
# Montículo máximo de V8 (MiB): por debajo del límite de espacio de direcciones del runner, para
# que una solución que agota la memoria termine con un mensaje claro de Node.
NODE_HEAP_MB = 2048
HEAP_OOM_TEXT = "JavaScript heap out of memory"
# Reporter propio de node:test: cuenta los resultados y los escribe con writeFileSync al terminar.
# Los reporteros de archivo de Node (junit con --test-reporter-destination) cierran el archivo con
# fsync, que el modelo de permisos prohíbe en las versiones recientes.
REPORTER_FILE = "modelduel-reporter.mjs"
RESULTS_FILE = "resultados-node.json"
_REPORTER_SOURCE = """\
import { writeFileSync } from "node:fs";

// Generado por modelduel: cuenta los tests hoja (no las suites ni los padres de subtests).
export default async function* modelduelReporter(source) {
  const counts = { passed: 0, failed: 0, skipped: 0 };
  const children = [];
  for await (const event of source) {
    if (event.type !== "test:pass" && event.type !== "test:fail") continue;
    const data = event.data ?? {};
    const level = data.nesting ?? 0;
    const hadChildren = (children[level + 1] ?? 0) > 0;
    children[level + 1] = 0;
    children[level] = (children[level] ?? 0) + 1;
    if (data.details?.type === "suite") continue;
    const failure = data.details?.error?.failureType;
    if (hadChildren && (event.type === "test:pass" || failure === "subtestsFailed")) continue;
    if ((data.skip ?? false) !== false || (data.todo ?? false) !== false) counts.skipped++;
    else if (event.type === "test:pass") counts.passed++;
    else counts.failed++;
  }
  writeFileSync(__OUT__, JSON.stringify(counts));
}
"""


class NodeError(Exception):
    """Falta Node o su versión no basta para las tareas pedidas."""


@dataclass(frozen=True)
class NodeInfo:
    path: str
    version: Version

    @property
    def text(self) -> str:
        return "v" + ".".join(map(str, self.version))


def parse_version(text: str) -> Version | None:
    """``"v22.6.0"`` -> ``(22, 6, 0)``; ``None`` si no lo parece."""
    match = re.match(r"\s*v?(\d+)\.(\d+)\.(\d+)", text or "")
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def _version_text(version: Version) -> str:
    return ".".join(map(str, version))


@functools.cache
def find_node() -> NodeInfo | None:
    """Node del PATH y su versión (se pregunta una vez con ``node --version``)."""
    return probe_node()


def probe_node(
    which: Callable[[str], str | None] | None = None,
    run: Callable[..., subprocess.CompletedProcess] | None = None,
) -> NodeInfo | None:
    which = which or shutil.which
    run = run or subprocess.run
    path = which("node")
    if path is None:
        return None
    try:
        done = run(
            [path, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    version = parse_version(done.stdout) if done.returncode == 0 else None
    return NodeInfo(path, version) if version else None


def needs_strip_flag(version: Version) -> bool:
    """``True`` si esta versión solo borra tipos con ``--experimental-strip-types``."""
    if version >= (23, 6, 0):
        return False
    if version[0] == 23:
        return True
    return version < (22, 18, 0)


def permission_flag(version: Version) -> str:
    """El modelo de permisos se llamó ``--experimental-permission`` hasta la 22.13 / 23.5."""
    if version >= (23, 5, 0) or ((22, 13, 0) <= version < (23, 0, 0)):
        return "--permission"
    return "--experimental-permission"


def required_version(languages: Iterable[str]) -> Version | None:
    """Versión mínima de Node para estos lenguajes (``None`` si ninguno necesita Node)."""
    languages = set(languages)
    if "typescript" in languages:
        return MIN_NODE_TS
    if "javascript" in languages:
        return MIN_NODE
    return None


def check_node(languages: Iterable[str], info: NodeInfo | None) -> NodeInfo | None:
    """Comprueba que hay un Node válido para ``languages``; ``NodeError`` con qué hacer si no."""
    languages = set(languages)
    needed = required_version(languages)
    if needed is None:
        return info
    which = "TypeScript" if "typescript" in languages else "JavaScript"
    if info is None:
        raise NodeError(
            f"hay tareas en {which} y sus tests se ejecutan con Node.js {_version_text(needed)} "
            f"o más nuevo, pero no encuentro `node` en el PATH. Instálalo ({NODE_URL}) y "
            "comprueba con `node --version` y `modelduel doctor`, o quita esas tareas."
        )
    if info.version < needed:
        raise NodeError(
            f"hay tareas en {which} y necesitan Node.js {_version_text(needed)} o más nuevo "
            f"(tienes {info.text} en {info.path}). Actualízalo ({NODE_URL}) o quita esas tareas."
        )
    return info


def reporter_source(results_path: str) -> str:
    """Código del reporter que deja el recuento en ``results_path`` (ruta tal y como la ve node)."""
    return _REPORTER_SOURCE.replace("__OUT__", json.dumps(results_path))


def parse_node_results(path: Path) -> dict | None:
    """Recuento del reporter (``None`` si falta o no es válido), como el de ``parse_junit``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    keys = ("passed", "failed", "skipped")
    if not isinstance(data, dict) or not all(
        isinstance(data.get(k), int) and not isinstance(data.get(k), bool) and data[k] >= 0
        for k in keys
    ):
        return None
    counts = {k: data[k] for k in keys}
    counts["errors"] = 0
    counts["total"] = sum(counts.values())
    counts["collection_error"] = False
    return counts


def wasm_trap_flag_supported(version: Version) -> bool:
    """``--disable-wasm-trap-handler`` existe desde la 20.15 (rama 20) y la 22.2."""
    return version >= (22, 2, 0) or (20, 15, 0) <= version < (21, 0, 0)


def node_test_args(
    version: Version,
    language: str,
    *,
    root: str,
    reporter: str,
    test_file: str,
    heap_mb: int | None = None,
) -> list[str]:
    """Argumentos de ``node`` para ejecutar ``test_file`` con ``node:test``.

    El archivo de tests se ejecuta directamente (no con ``node --test``, que lanzaría un proceso
    hijo por archivo y obligaría a permitirlos): los tests se registran con ``node:test`` igual, el
    reportero ``spec`` deja un resumen legible en la salida y ``reporter`` (URL ``file://`` del
    módulo de ``reporter_source``) escribe el recuento. Con el modelo de permisos de Node solo se
    puede leer y escribir dentro de ``root`` y no se pueden lanzar procesos, *workers*, WASI ni
    complementos nativos. Sin el manejador de trampas de WebAssembly, V8 no reserva decenas de GiB
    de memoria virtual por instancia, así que WebAssembly (y el borrado de tipos de TypeScript, que
    lo usa) funciona dentro del límite de espacio de direcciones del runner.
    """
    args = [
        permission_flag(version),
        f"--allow-fs-read={root}",
        f"--allow-fs-write={root}",
        "--disable-warning=ExperimentalWarning",
        f"--max-old-space-size={heap_mb or NODE_HEAP_MB}",
    ]
    if wasm_trap_flag_supported(version):
        args.append("--disable-wasm-trap-handler")
    args += [
        "--test-reporter=spec",
        "--test-reporter-destination=stdout",
        f"--test-reporter={reporter}",
        "--test-reporter-destination=stdout",
    ]
    if language == "typescript" and needs_strip_flag(version):
        args.append("--experimental-strip-types")
    args.append(test_file)
    return args


def heap_message() -> str:
    return (
        f"La solución agotó la memoria de Node (montículo de {NODE_HEAP_MB} MiB) y el proceso "
        "terminó."
    )


def node_env(env: dict[str, str]) -> dict[str, str]:
    """Quita del entorno lo que cambiaría cómo arranca Node y apaga los colores."""
    env = dict(env)
    for name in ("NODE_OPTIONS", "NODE_PATH", "NODE_REPL_EXTERNAL_MODULE", "FORCE_COLOR"):
        env.pop(name, None)
    env["NO_COLOR"] = "1"
    env["NODE_DISABLE_COLORS"] = "1"
    return env
