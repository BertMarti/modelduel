"""Construye el prompt y ejecuta los tests de una tarea sobre el código de un modelo.

El código generado se ejecuta SIEMPRE en un directorio temporal, en un subproceso con límite
de tiempo, sin las variables de entorno que parecen secretos y con ``HOME`` apuntando al
temporal. En POSIX el subproceso arranca además con límites del sistema (``setrlimit``): memoria,
CPU, tamaño de archivo, descriptores y sin volcados de memoria. Al terminar (o al agotar el
tiempo) se mata el árbol de procesos completo: un *Job Object* en Windows y un grupo de procesos
en POSIX. La salida va a un archivo y solo se leen su principio y su final, así que una solución
que imprime sin parar no puede agotar la memoria.

En Linux, por defecto, el supervisor corta además la red con un espacio de nombres propio
(``sandbox.network_isolation_available``). Aun así puede leer y escribir rutas absolutas del disco:
para código no confiable, usa ``--sandbox docker|podman`` (``sandbox.py``), que ejecuta los tests
en un contenedor sin red, sin privilegios y de solo lectura.
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

from modelduel.sandbox import (
    CONTAINER_FAILURE_CODES,
    CONTAINER_GRACE_S,
    CONTAINER_MEMORY,
    CONTAINER_ROOT,
    TIMEOUT_EXIT_CODE,
    Sandbox,
    container_command,
    container_name,
    network_isolation_available,
    remove_container,
)
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
    "PROXY",  # HTTP(S)_PROXY puede llevar usuario:contraseña@
    "WEBHOOK",  # una URL de webhook es en sí una credencial
    "_PWD",  # MYSQL_PWD (pero no PWD, el directorio actual)
)
# Variables sin «pista» en el nombre que dan acceso a algo: conexión a bases de datos,
# al demonio de Docker, a Kubernetes o al agente GPG, o rutas a archivos de configuración con
# credenciales (cambiar HOME no las neutraliza porque son absolutas).
_SENSITIVE_VARS = frozenset(
    {
        "DATABASE_URL",
        "REDIS_URL",
        "MONGODB_URI",
        "DOCKER_HOST",
        "DOCKER_CONFIG",
        "KUBECONFIG",
        "GPG_AGENT_INFO",
        "GNUPGHOME",
        "AWS_CONFIG_FILE",
        "NETRC",
        "NPM_CONFIG_USERCONFIG",
        "PIP_CONFIG_FILE",
        "GIT_CONFIG_GLOBAL",
        "CLOUDSDK_CONFIG",
        "AZURE_CONFIG_DIR",
    }
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
# 4 GiB de espacio de direcciones (no de memoria residente): cada hilo reserva su pila, así que
# con 1 GiB un ThreadPoolExecutor en una máquina de muchos núcleos ya fallaba. Solo Linux lo
# respeta; macOS no aplica RLIMIT_AS.
MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
# Ningún archivo (tampoco la salida de los tests) pasa de 256 MiB. CPython ignora SIGXFSZ: al
# superarlo, write() lanza «OSError: [Errno 27] File too large» y el mensaje lo explica. La lectura
# de la salida ya está acotada por ``_read_capped``.
FILE_SIZE_LIMIT_BYTES = 256 * 1024 * 1024
OPEN_FILES_LIMIT = 256
# Margen de CPU sobre el límite de tiempo: el reloj de pared sigue siendo el que manda.
CPU_MARGIN_S = 5
# Windows: memoria comprometida máxima de cada proceso del Job Object
# (JOB_OBJECT_LIMIT_PROCESS_MEMORY). Al superarla, la reserva falla (MemoryError en Python).
WINDOWS_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024

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
        # Con blando == duro en la CPU el núcleo manda SIGKILL y nunca SIGXCPU: un segundo de
        # margen en el duro permite explicar el final. El resto, blando == duro.
        _new_hard = _value + 1 if _name == "RLIMIT_CPU" else _value
        try:
            _soft, _hard = resource.getrlimit(_res)
            if _hard != resource.RLIM_INFINITY:
                _value = min(_value, _hard)
                _new_hard = min(_new_hard, _hard)
            resource.setrlimit(_res, (_value, _new_hard))
        except (ValueError, OSError):
            pass  # p. ej. RLIMIT_AS en macOS: se sigue con el resto de límites
del sys.argv[1]
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
"""


# Supervisor intermedio (solo Linux). Una solución que llame a ``setsid()`` o haga un doble fork
# sale del grupo de procesos y sobreviviría al ``killpg``. El supervisor se declara «subreaper»
# (``prctl(PR_SET_CHILD_SUBREAPER)``, sin privilegios): los procesos que se queden huérfanos por
# debajo de él pasan a ser hijos suyos en vez de irse a init, así que siguen siendo descendientes
# suyos aunque cambien de sesión o de grupo. Al terminar (o al agotar el tiempo, o con SIGTERM)
# mata a TODOS sus descendientes recorriendo /proc y los recoge. Por la tubería ``argv[1]``
# devuelve el código de salida de pytest («timeout» si se agotó el tiempo). pytest corre en un
# hijo con ``close_fds``: la solución no hereda la tubería.
_SUPERVISOR = """\
import ctypes, os, signal, subprocess, sys, time
status_fd, timeout, isolate, cmd = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3], sys.argv[4:]
try:
    ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER
except (OSError, AttributeError):
    pass  # sin subreaper solo se ven los descendientes que no se hayan desligado
if isolate == "net":
    # Espacio de nombres de usuario y de red propios (como `unshare --map-current-user --net`):
    # sin root, el mismo UID dentro y solo un `lo` apagado. Si falla, no se ejecuta nada.
    try:
        uid, gid = os.getuid(), os.getgid()
        os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET)
        maps = (("setgroups", "deny"), ("uid_map", f"{uid} {uid} 1"), ("gid_map", f"{gid} {gid} 1"))
        for name, text in maps:
            with open("/proc/self/" + name, "w") as fh:
                fh.write(text)
    except (OSError, AttributeError):
        os.write(status_fd, b"nonet")
        raise SystemExit(0)
me = os.getpid()


def descendants():
    children = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open("/proc/" + name + "/stat", "rb") as fh:
                data = fh.read()
            ppid = int(data[data.rindex(b")") + 2 :].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(int(name))
    found, todo = [], [me]
    while todo:
        for pid in children.get(todo.pop(), ()):
            found.append(pid)
            todo.append(pid)
    return found


def parent_of(pid):
    try:
        with open("/proc/" + str(pid) + "/stat", "rb") as fh:
            data = fh.read()
        return int(data[data.rindex(b")") + 2 :].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def kill(pid, tree):
    # pidfd fija el proceso: si muere y su PID se reutiliza antes de la señal, la señal falla
    # en vez de alcanzar a otro. Se comprueba que sigue colgando del árbol tras abrirlo.
    fd = -1
    try:
        fd = os.pidfd_open(pid)
    except (OSError, AttributeError):
        pass
    try:
        if parent_of(pid) not in tree:
            return
        if fd >= 0:
            signal.pidfd_send_signal(fd, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    finally:
        if fd >= 0:
            os.close(fd)


def reap_all():
    deadline = time.monotonic() + 10
    while True:
        pids = descendants()
        tree = set(pids) | {me}
        for pid in pids:
            kill(pid, tree)
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0:
                    break
            except ChildProcessError:
                break
        if not pids or time.monotonic() > deadline:
            return
        time.sleep(0.005)


class Stop(Exception):
    pass


def stop(signum, frame):
    raise Stop


status = "stopped"
try:
    signal.signal(signal.SIGTERM, stop)
    child = subprocess.Popen(cmd)
    try:
        status = str(child.wait(timeout=timeout))
    except subprocess.TimeoutExpired:
        status = "timeout"
except Stop:
    pass
finally:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    reap_all()
    os.write(status_fd, status.encode())
"""
# Margen del padre sobre el límite de tiempo antes de no fiarse del supervisor y matar el grupo.
SUPERVISOR_GRACE_S = 10.0
# Marca en el entorno de cada ejecución: si el supervisor muere (p. ej. la solución lo mata),
# el padre busca en /proc los procesos que aún la lleven y los mata.
RUN_MARKER_VAR = "MODELDUEL_RUN"


def supervisor_supported() -> bool:
    """``True`` en Linux con /proc y ``prctl(PR_SET_CHILD_SUBREAPER)`` disponibles."""
    if not sys.platform.startswith("linux") or not os.path.isdir("/proc/self"):
        return False
    try:
        import ctypes

        value = ctypes.c_int(0)
        # PR_GET_CHILD_SUBREAPER (37): solo consulta, no cambia nada en este proceso.
        return ctypes.CDLL(None, use_errno=True).prctl(37, ctypes.byref(value), 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


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


def isolation_summary() -> list[str]:
    """Medidas de protección que el runner aplica en este sistema (para ``modelduel doctor``)."""
    items = ["directorio temporal propio y entorno sin secretos", "límite de tiempo por respuesta"]
    if os.name == "nt":
        items.append(
            "Job Object que mata el árbol de procesos y limita la memoria a "
            f"{WINDOWS_MEMORY_LIMIT_BYTES // 2**30} GiB por proceso"
        )
        return items
    items.append("límites del sistema (setrlimit): CPU, memoria, archivos y descriptores")
    if supervisor_supported():
        items.append(
            "supervisor «subreaper» que mata también los procesos que se desligan (setsid)"
        )
    else:
        items.append(
            "grupo de procesos propio que se mata al terminar (no recoge los que hacen setsid)"
        )
    if network_isolation_available() and supervisor_supported():
        items.append("red cortada por defecto (espacio de nombres de red de Linux, sin root)")
    items.append("para código no fiable: --sandbox docker o podman (contenedor sin red ni root)")
    return items


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


def default_sandbox() -> Sandbox:
    """Lo de siempre más la red cortada en Linux cuando el sistema lo permite (``auto``)."""
    return Sandbox(isolate_network=network_isolation_available())


def run_tests(
    code: str | None,
    task: Task,
    timeout: float = DEFAULT_TIMEOUT,
    sandbox: Sandbox | None = None,
) -> TestRun:
    """Ejecuta ``test_task.py`` contra ``code`` guardado como ``solution.py``.

    ``sandbox`` decide dónde: en local (por defecto, con la red cortada si se puede) o en un
    contenedor de Docker/Podman ya preparado con ``sandbox.prepare_container``.
    """
    sandbox = default_sandbox() if sandbox is None else sandbox
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
        pytest_args = ["-q", "--tb=short", "-p", "no:cacheprovider"]
        limits = json.dumps(resource_limits(timeout))
        if sandbox.is_container:
            python_args = [
                "-c",
                _BOOTSTRAP,
                limits,
                *pytest_args,
                f"--junitxml={CONTAINER_ROOT}/junit.xml",
                TEST_FILE,
            ]
            returncode, duration = _execute_container(
                sandbox, root, python_args, output_path, timeout
            )
        else:
            cmd = [
                sys.executable,
                "-c",
                _BOOTSTRAP,
                limits,
                *pytest_args,
                f"--junitxml={junit}",
                TEST_FILE,
            ]
            env = safe_env(home=tmpdir)
            # Los temporales de la solución y de pytest se quedan dentro de la ejecución.
            for name in ("TMP", "TEMP", "TMPDIR"):
                env[name] = str(tmpdir)
            returncode, duration = _execute(
                cmd, workdir, env, output_path, timeout, isolate_network=sandbox.isolate_network
            )
        output = _truncate(_clean_output(_read_capped(output_path), root))
        counts = parse_junit(junit) if junit.is_file() else None
    except _SetupFailed as exc:
        return TestRun(status="error", total=expected, message=str(exc))
    finally:
        _remove_tree(root)

    if sandbox.is_container and returncode in CONTAINER_FAILURE_CODES and counts is None:
        return TestRun(
            status="error",
            total=expected,
            duration_s=duration,
            output=output,
            message=(
                f"{sandbox.kind} no pudo ejecutar los tests en el contenedor (código {returncode})."
                " Revisa la salida y `modelduel doctor`."
            ),
        )
    result = _classify(returncode, counts, output, duration, expected, timeout)
    if sandbox.is_container and returncode in (-9, 137) and counts is None:  # SIGKILL
        result.message = (
            "El contenedor terminó los tests a la fuerza: ¿superó la memoria "
            f"({CONTAINER_MEMORY.upper()}iB) o el número de procesos?"
        )
    if _hit_file_size_limit(output):
        result.message = file_size_message()
    return result


def file_size_message() -> str:
    return (
        f"La solución escribió más de {FILE_SIZE_LIMIT_BYTES // (1024 * 1024)} MiB de salida "
        "o en un archivo (límite del sistema)."
    )


def _hit_file_size_limit(output: str) -> bool:
    """``True`` si la salida muestra el ``OSError`` de ``RLIMIT_FSIZE`` (CPython ignora SIGXFSZ)."""
    return "[Errno 27]" in output or "File too large" in output


def _classify(
    returncode: int | None,
    counts: dict | None,
    output: str,
    duration: float,
    expected: int,
    timeout: float,
) -> TestRun:
    """Convierte el código de salida y el XML de pytest en un ``TestRun``."""
    if returncode is not None and returncode < 0:
        # Muerte por señal (un límite, o la solución matando a su supervisor): el XML que haya
        # no es de fiar y el intento no puede contar como resuelto.
        counts = None
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


class _SetupFailed(Exception):
    """No se pudo preparar el aislamiento pedido para esta ejecución (no es culpa del modelo)."""


def _execute_container(
    sandbox: Sandbox, root: Path, python_args: list[str], output_path: Path, timeout: float
) -> tuple[int | None, float]:
    """Ejecuta los tests en un contenedor desechable; ``None`` si se agota el tiempo.

    Dentro, ``timeout -s KILL`` corta a los ``timeout`` s (sale con 124). El cliente de
    Docker/Podman corre con el entorno normal (lo necesita para hablar con su demonio); al
    contenedor solo llegan las variables de ``sandbox.container_env``. Si el cliente no vuelve a
    tiempo, ``rm -f`` para el contenedor y todo lo que haya dentro.
    """
    name = container_name()
    cmd = container_command(sandbox, name=name, root=root, python_args=python_args, timeout=timeout)
    start = time.perf_counter()
    finished = False
    with open(output_path, "wb") as out:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
        try:
            returncode: int | None = proc.wait(timeout=timeout + CONTAINER_GRACE_S)
            finished = True
        except subprocess.TimeoutExpired:
            returncode = None
        finally:
            if not finished:
                remove_container(sandbox, name)
                proc.kill()
                proc.wait()
    duration = round(time.perf_counter() - start, 3)
    # ``timeout -s KILL`` sale con 124 o, si la señal le alcanza también a él, con 137 (128 + 9):
    # un 137 al llegar al límite es tiempo agotado; antes, el contenedor lo mató (p. ej. memoria).
    if returncode == TIMEOUT_EXIT_CODE or (returncode == 137 and duration >= timeout):
        return None, duration
    # Señales que el proceso de dentro recibe por un límite (Windows no define todas).
    limit_signals = {
        int(sig)
        for name in ("SIGKILL", "SIGXCPU", "SIGXFSZ", "SIGSEGV")
        if (sig := getattr(signal, name, None)) is not None
    }
    if returncode is not None and returncode > 128 and returncode - 128 in limit_signals:
        # El proceso de dentro murió por una señal: se informa igual que en local.
        return -(returncode - 128), duration
    return returncode, duration


def _execute(
    cmd: list[str],
    workdir: Path,
    env: dict[str, str],
    output_path: Path,
    timeout: float,
    isolate_network: bool = False,
) -> tuple[int | None, float]:
    """Ejecuta ``cmd`` y devuelve ``(código de salida, duración)``; ``None`` si agota el tiempo.

    stdout y stderr van juntos a ``output_path``: un archivo no obliga a esperar a que los
    procesos nietos suelten una tubería. Al volver no queda vivo ningún proceso del árbol. En
    Linux, ``cmd`` corre bajo el supervisor ``_SUPERVISOR``, que recoge también a los que se
    desligan con ``setsid``/doble fork; en el resto de POSIX esos podrían sobrevivir.
    """
    if supervisor_supported():
        return _execute_supervised(cmd, workdir, env, output_path, timeout, isolate_network)
    if isolate_network:
        raise _SetupFailed(
            "Este sistema no permite cortar la red de los tests sin el supervisor de Linux. "
            "Usa --sandbox docker o --sandbox ninguno."
        )
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


def _execute_supervised(
    cmd: list[str],
    workdir: Path,
    env: dict[str, str],
    output_path: Path,
    timeout: float,
    isolate_network: bool = False,
) -> tuple[int | None, float]:
    """Como ``_execute``, pero a través del supervisor «subreaper» (solo Linux).

    Con ``isolate_network`` el supervisor entra antes en un espacio de nombres de red propio; si
    no puede, no ejecuta nada y se lanza ``_SetupFailed`` (nunca se ejecuta con red por sorpresa).
    """
    isolate = "net" if isolate_network else "-"
    marker = os.urandom(16).hex()
    env = {**env, RUN_MARKER_VAR: marker}
    read_fd, write_fd = os.pipe()
    start = time.perf_counter()
    timed_out = False
    try:
        with open(output_path, "wb") as out:
            proc = subprocess.Popen(
                [sys.executable, "-c", _SUPERVISOR, str(write_fd), repr(timeout), isolate, *cmd],
                cwd=workdir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                pass_fds=(write_fd,),
                start_new_session=True,
            )
            os.close(write_fd)
            write_fd = -1
            tree = _ProcessTree(proc, supervised=True)
            try:
                proc.wait(timeout=timeout + SUPERVISOR_GRACE_S)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                tree.kill()
                proc.wait()
                # Red de seguridad si alguien mató al supervisor antes de que limpiara.
                _kill_marked(marker)
        status = _read_status(read_fd)
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)
    duration = round(time.perf_counter() - start, 3)
    if status == "nonet":
        raise _SetupFailed(
            "No se pudo cortar la red de los tests (espacio de nombres de Linux) y no se "
            "ejecutaron. Usa --sandbox docker o --sandbox ninguno."
        )
    if timed_out or status == "timeout":
        return None, duration
    try:
        return int(status), duration
    except ValueError:
        pass
    if status == "stopped":
        # Al supervisor le llegó SIGTERM (de la propia solución, p. ej.): se informa como tal.
        return -signal.SIGTERM, duration
    # El supervisor no informó (lo mataron): su propio final es lo único que se sabe.
    return proc.returncode, duration


def _read_status(fd: int) -> str:
    chunks = []
    while True:
        chunk = os.read(fd, 64)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("ascii", errors="replace").strip()


def _kill_marked(marker: str) -> int:
    """Mata los procesos propios que conserven ``RUN_MARKER_VAR=marker`` en su entorno."""
    needle = f"{RUN_MARKER_VAR}={marker}".encode()
    me = os.getpid()
    killed = 0
    for _ in range(5):
        found = []
        try:
            names = os.listdir("/proc")
        except OSError:
            return killed
        for name in names:
            if not name.isdigit() or int(name) == me:
                continue
            try:
                with open(f"/proc/{name}/environ", "rb") as fh:
                    environ = fh.read()
            except OSError:
                continue  # de otro usuario, o ya terminó
            if needle in environ.split(b"\0"):
                found.append(int(name))
        if not found:
            return killed
        for pid in found:
            killed += _kill_if_marked(pid, needle)
        time.sleep(0.05)
    return killed


def _kill_if_marked(pid: int, needle: bytes) -> int:
    """Mata ``pid`` solo si sigue llevando la marca, sin carrera con la reutilización del PID.

    Con ``pidfd_open`` (Linux 5.3+) el descriptor fija el proceso: si muere y su PID pasa a otro
    entre la comprobación y la señal, ``pidfd_send_signal`` falla en vez de matar al nuevo.
    """
    pidfd = -1
    with contextlib.suppress(OSError, AttributeError):
        pidfd = os.pidfd_open(pid)
    try:
        try:
            with open(f"/proc/{pid}/environ", "rb") as fh:
                if needle not in fh.read().split(b"\0"):
                    return 0
        except OSError:
            return 0
        try:
            if pidfd >= 0:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            return 0
        return 1
    finally:
        if pidfd >= 0:
            os.close(pidfd)


class _ProcessTree:
    """Mata un proceso y todos sus descendientes solo con la biblioteca estándar."""

    def __init__(self, proc: subprocess.Popen, supervised: bool = False) -> None:
        self.proc = proc
        self.supervised = supervised
        self.job = _win_job_for(proc) if os.name == "nt" else None

    def kill(self) -> None:
        if os.name != "nt":
            if self.supervised and self.proc.poll() is None:
                # SIGTERM al supervisor: mata y recoge a todos sus descendientes antes de salir.
                with contextlib.suppress(ProcessLookupError):
                    self.proc.send_signal(signal.SIGTERM)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self.proc.wait(timeout=SUPERVISOR_GRACE_S)
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
    kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    return kernel32


# Estructuras de winnt.h para JOBOBJECT_EXTENDED_LIMIT_INFORMATION. Se definen con tipos de
# ctypes de tamaño fijo para poder comprobar su tamaño también fuera de Windows (tests).
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9


def _job_limit_structs():
    import ctypes

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    return ExtendedLimitInformation


def job_memory_limit_info(limit: int = WINDOWS_MEMORY_LIMIT_BYTES):
    """``JOBOBJECT_EXTENDED_LIMIT_INFORMATION`` con el tope de memoria por proceso.

    ``KILL_ON_JOB_CLOSE`` además: si modelduel muere, Windows cierra el Job y mata el árbol.
    """
    info = _job_limit_structs()()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.ProcessMemoryLimit = limit
    return info


def _win_limit_memory(kernel32, job) -> bool:  # pragma: no cover - solo Windows
    import ctypes

    info = job_memory_limit_info()
    return bool(
        kernel32.SetInformationJobObject(
            job,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
    )


def _win_job_for(proc: subprocess.Popen) -> int | None:  # pragma: no cover - solo Windows
    """Mete ``proc`` en un Job Object nuevo (sus hijos entran solos). ``None`` si no se puede."""
    try:
        kernel32 = _kernel32()
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        # Si el límite no se puede poner, el Job sigue sirviendo para matar el árbol.
        _win_limit_memory(kernel32, job)
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
    variants |= {f"{CONTAINER_ROOT}/work", CONTAINER_ROOT}
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
