"""Aislamiento del código de los modelos: contenedor (Docker o Podman) o red cortada en Linux.

Tres niveles, del más fuerte al más débil:

* ``--sandbox docker`` / ``--sandbox podman``: cada ejecución de los tests corre en un contenedor
  desechable de la imagen oficial de Python (fijada por digest) sin red (``--network none``), sin
  privilegios (``--cap-drop ALL``, ``no-new-privileges``, usuario sin root), con el sistema de
  archivos de solo lectura salvo la carpeta de la ejecución y un ``/tmp`` en memoria, y con
  techos de memoria, CPU y procesos. pytest no viene en la imagen: se monta, de solo lectura, el
  de este entorno (``pytest_mounts``).
* Por defecto en Linux (``auto``): el supervisor entra en un espacio de nombres de usuario y de red
  nuevos (lo mismo que ``unshare --map-current-user --net``, sin root), así que la solución no tiene
  más red que un ``lo`` apagado. Si el sistema no lo permite, se avisa.
* ``--sandbox ninguno``: solo las protecciones de siempre (temporal, entorno limpio, límites,
  supervisor).
"""

from __future__ import annotations

import contextlib
import functools
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

# Imagen oficial de Python fijada por digest (índice multiarquitectura: amd64, arm64, armv7…).
# Para actualizarla: etiqueta nueva + su «docker-content-digest» (lo explica docs/DESARROLLO.md).
DEFAULT_IMAGE = (
    "python:3.13.17-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962"
)
CONTAINER_TOOLS = ("docker", "podman")
SANDBOX_CHOICES = ("auto", "docker", "podman", "ninguno")
# Techos del contenedor (además de los setrlimit del arranque, que también se aplican dentro).
CONTAINER_MEMORY = "1g"
CONTAINER_MEMORY_TEXT = "1 GiB"
CONTAINER_CPUS = "1"
CONTAINER_PIDS = 128
CONTAINER_TMPFS = "/tmp:rw,nosuid,nodev,noexec,size=64m"
# Rutas dentro del contenedor.
CONTAINER_ROOT = "/sandbox"
CONTAINER_DEPS = "/deps"
# Margen del padre sobre el límite de tiempo para arrancar y parar el contenedor.
CONTAINER_GRACE_S = 30.0
# Docker/Podman (125) o ``timeout`` (125, 126, 127) no pudieron ni ejecutar los tests.
CONTAINER_FAILURE_CODES = frozenset({125, 126, 127})
# Código de salida de ``timeout`` de coreutils cuando se agota el tiempo.
TIMEOUT_EXIT_CODE = 124

Runner = Callable[..., subprocess.CompletedProcess]


class SandboxError(Exception):
    """No se puede usar el aislamiento pedido (herramienta ausente, imagen, demonio…)."""


@dataclass(frozen=True)
class Sandbox:
    """Cómo se ejecutan los tests: ``local`` (con o sin red) o en un contenedor."""

    kind: str = "local"  # local | docker | podman
    executable: str | None = None  # ruta de docker/podman
    image: str = DEFAULT_IMAGE
    isolate_network: bool = False  # solo local: espacio de nombres de red propio (Linux)
    user_args: tuple[str, ...] = field(default_factory=tuple)  # --user / --userns del contenedor

    @property
    def is_container(self) -> bool:
        return self.kind in CONTAINER_TOOLS

    def describe(self) -> str:
        """Una línea para la cabecera de ``modelduel run``."""
        if self.is_container:
            return (
                f"contenedor {self.kind} sin red, sin privilegios y de solo lectura "
                f"({CONTAINER_MEMORY_TEXT} de memoria, {CONTAINER_CPUS} CPU, "
                f"{CONTAINER_PIDS} procesos)"
            )
        if self.isolate_network:
            return "red cortada (espacio de nombres de Linux) + temporal, entorno limpio y límites"
        return "temporal, entorno limpio y límites, pero CON red"


# ---------------------------------------------------------------- red local (Linux)

# Lo mismo que hace el supervisor antes de lanzar pytest; aquí solo para saber si se puede.
# Entrar en un espacio de nombres de usuario y de red propio (como
# `unshare --map-current-user --net`, sin root) y encender `lo`, que nace apagado: sin él ni
# 127.0.0.1 funciona y fallarían las tareas cuyos tests levantan un servidor local. El ioctl
# SIOCSIFFLAGS (0x8914) necesita CAP_NET_ADMIN, que se tiene en el espacio de nombres nuevo hasta
# el siguiente execve (pytest ya no lo conserva). Lo usan el supervisor y la prueba previa.
NETNS_ENTER = """\
def enter_netns():
    import fcntl, os, socket, struct
    uid, gid = os.getuid(), os.getgid()
    os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET)
    maps = (("setgroups", "deny"), ("uid_map", f"{uid} {uid} 1"), ("gid_map", f"{gid} {gid} 1"))
    for name, text in maps:
        with open("/proc/self/" + name, "w") as fh:
            fh.write(text)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        # struct ifreq: nombre (16) + ifr_flags (IFF_UP | IFF_RUNNING) + relleno hasta 40 bytes.
        fcntl.ioctl(sock, 0x8914, struct.pack("16sH22s", b"lo", 0x1 | 0x40, b""))
"""

_NETNS_PROBE = (
    NETNS_ENTER
    + """\
import os, socket
uid = os.getuid()
enter_netns()
assert os.getuid() == uid
names = [n for _, n in socket.if_nameindex()]
assert names == ["lo"], names
with socket.create_server(("127.0.0.1", 0)) as server:
    socket.create_connection(server.getsockname(), timeout=2).close()
"""
)


@functools.cache
def network_isolation_available() -> bool:
    """``True`` si este Linux deja crear espacios de nombres de usuario y red sin root.

    Se comprueba una vez, en un proceso aparte (``os.unshare`` cambia el proceso que lo llama).
    Puede fallar con ``kernel.unprivileged_userns_clone=0``, ``user.max_user_namespaces=0``,
    la restricción de AppArmor de Ubuntu 24.04 o dentro de algunos contenedores.
    """
    if not sys.platform.startswith("linux") or not hasattr(os, "unshare"):
        return False
    try:
        probe = subprocess.run(
            [sys.executable, "-I", "-c", _NETNS_PROBE],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def network_isolation_hint() -> str:
    """Por qué no hay aislamiento de red local y qué hacer."""
    if not sys.platform.startswith("linux"):
        return (
            "en Windows y macOS la red solo se corta con un contenedor. Para código no fiable usa "
            "--sandbox docker (o podman) o --solo-generar"
        )
    return (
        "este Linux no permite espacios de nombres sin root (p. ej. "
        "kernel.apparmor_restrict_unprivileged_userns=1 o user.max_user_namespaces=0): la "
        "solución tiene red. Usa --sandbox docker (o podman) o --solo-generar"
    )


# ---------------------------------------------------------------- elección


def resolve_sandbox(
    choice: str | None,
    image: str | None = None,
    which: Callable[[str], str | None] | None = None,
) -> Sandbox:
    """``Sandbox`` para ``--sandbox`` (``None`` = ``auto``). No arranca nada todavía."""
    which = which or shutil.which
    choice = (choice or "auto").strip().lower()
    if choice not in SANDBOX_CHOICES:
        raise SandboxError(
            f"--sandbox: «{choice}» no es válido (elige entre {', '.join(SANDBOX_CHOICES)})."
        )
    if choice == "ninguno":
        return Sandbox()
    if choice == "auto":
        return Sandbox(isolate_network=network_isolation_available())
    executable = which(choice)
    if executable is None:
        raise SandboxError(missing_tool_message(choice))
    return Sandbox(kind=choice, executable=executable, image=image or DEFAULT_IMAGE)


def missing_tool_message(tool: str) -> str:
    other = "podman" if tool == "docker" else "docker"
    url = (
        "https://docs.docker.com/engine/install/"
        if tool == "docker"
        else "https://podman.io/docs/installation"
    )
    return (
        f"--sandbox {tool}: no encuentro «{tool}» en el PATH. Instálalo ({url}) o prueba con "
        f"--sandbox {other}. Sin contenedor, modelduel corta la red en Linux cuando el sistema "
        "lo permite (mira `modelduel doctor`)."
    )


def available_container_tools(which: Callable[[str], str | None] | None = None) -> list[str]:
    """Docker y/o Podman instalados (solo se mira el PATH: no se arranca nada)."""
    which = which or shutil.which
    return [tool for tool in CONTAINER_TOOLS if which(tool)]


def prepare_container(
    sandbox: Sandbox,
    run: Runner | None = None,
    notify: Callable[[str], None] = lambda _msg: None,
) -> Sandbox:
    """Comprueba el demonio y la imagen (la descarga una vez si falta) antes del duelo.

    Así el tiempo de descarga nunca cuenta en el límite de los tests (``--pull never``).
    Devuelve el ``Sandbox`` con las opciones de usuario que tocan a este motor.
    """
    if not sandbox.is_container or sandbox.executable is None:
        return sandbox
    run = run or subprocess.run
    exe, tool = sandbox.executable, sandbox.kind
    try:
        found = run(
            [exe, "image", "inspect", sandbox.image],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if found.returncode != 0:
            notify(f"Descargando la imagen {sandbox.image} (solo la primera vez)…")
            pulled = run(
                [exe, "pull", sandbox.image],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            if pulled.returncode != 0:
                detail = _last_line(pulled.stderr or pulled.stdout)
                raise SandboxError(
                    f"{tool} no pudo descargar la imagen {sandbox.image}"
                    + (f" ({detail})" if detail else "")
                    + f". Comprueba que {tool} está en marcha (`{tool} info`) y que hay "
                    f"conexión, o descárgala a mano con `{tool} pull {sandbox.image}`."
                )
        user_args = _user_args(sandbox, run)
        # Antes de la primera llamada a una API: pytest se encuentra y sus rutas se pueden montar.
        for top, path in pytest_mounts():
            _mount(path, f"{CONTAINER_DEPS}/{top}", readonly=True)
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(
            f"{tool} no responde ({' '.join(exc.cmd[1:3])}). Comprueba que está en marcha "
            f"con `{tool} info`."
        ) from None
    except OSError as exc:
        raise SandboxError(f"no se pudo ejecutar {exe}: {exc.strerror or exc}.") from None
    return Sandbox(
        kind=sandbox.kind,
        executable=sandbox.executable,
        image=sandbox.image,
        user_args=user_args,
    )


def _user_args(sandbox: Sandbox, run: Runner) -> tuple[str, ...]:
    """Usuario del contenedor: sin root y capaz de escribir en la carpeta de la ejecución.

    * Podman sin root: ``--userns=keep-id`` (dentro eres tu propio usuario).
    * Docker sin root (rootless): el root del contenedor ya es tu usuario en el anfitrión.
    * Docker normal en Linux/macOS: ``--user UID:GID`` de quien ejecuta modelduel.
    * Windows (Docker Desktop): sin ``--user`` (no hay UID en el anfitrión).
    """
    if sandbox.kind == "podman":
        return ("--userns=keep-id",)
    if not hasattr(os, "getuid"):
        return ()
    info = run(
        [sandbox.executable, "info", "--format", "{{json .SecurityOptions}}"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if info.returncode != 0:
        detail = _last_line(info.stderr or info.stdout)
        raise SandboxError(
            "Docker no responde"
            + (f" ({detail})" if detail else "")
            + ". Arráncalo (p. ej. `sudo systemctl start docker` o abre Docker Desktop) y "
            "comprueba que tu usuario puede usarlo con `docker info`."
        )
    if "rootless" in (info.stdout or ""):
        return ()
    return ("--user", f"{os.getuid()}:{os.getgid()}")


def _last_line(text: str | None) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


# ---------------------------------------------------------------- pytest dentro del contenedor


def _dist_name(requirement: str) -> str | None:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return match.group(1) if match else None


def _top_levels(dist: metadata.Distribution) -> set[str]:
    """Paquetes y módulos de primer nivel que instala una distribución."""
    names: set[str] = set()
    for file in dist.files or ():
        parts = file.parts
        if not parts or parts[0] in ("..", "__pycache__"):
            continue
        top = parts[0]
        if top.endswith((".dist-info", ".egg-info", ".data")):
            continue
        if len(parts) == 1 and not top.endswith(".py"):
            continue  # .pth, binarios…
        names.add(top)
    return names


@functools.cache
def pytest_mounts() -> tuple[tuple[str, Path], ...]:
    """``(nombre, ruta)`` de pytest y sus dependencias en este entorno, para montarlos.

    La imagen oficial no trae pytest y el contenedor no tiene red para instalarlo: se montan,
    de solo lectura, los paquetes de Python puro de pytest (``_pytest``, ``pluggy``,
    ``iniconfig``, ``packaging``, ``pygments``…) en ``/deps``.
    """
    mounts: dict[str, Path] = {}
    seen: set[str] = set()
    todo = ["pytest"]
    while todo:
        name = todo.pop()
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        for requirement in dist.requires or ():
            if re.search(r"extra\s*==", requirement):
                continue
            dependency = _dist_name(requirement)
            if dependency:
                todo.append(dependency)
        for top in _top_levels(dist):
            path = Path(str(dist.locate_file(top)))
            if path.exists():
                mounts[top] = path
    if "_pytest" not in mounts or "pytest" not in mounts:
        raise SandboxError(
            "no encuentro los archivos de pytest de este entorno para montarlos en el "
            "contenedor. Instálalo con: pip install pytest"
        )
    return tuple(sorted(mounts.items()))


# ---------------------------------------------------------------- orden del contenedor


def _mount(source: Path, target: str, readonly: bool = False) -> str:
    text = str(source)
    if "," in text or "=" in text:
        raise SandboxError(
            f"la ruta {text} lleva «,» o «=», que la opción --mount de Docker/Podman no admite."
        )
    return f"type=bind,source={text},target={target}" + (",readonly" if readonly else "")


def container_command(
    sandbox: Sandbox,
    *,
    name: str,
    root: Path,
    python_args: list[str],
    timeout: float,
    mounts: tuple[tuple[str, Path], ...] | None = None,
) -> list[str]:
    """Orden ``docker run`` / ``podman run`` que ejecuta ``python <python_args>`` aislado.

    ``root`` (la carpeta temporal de la ejecución, con ``work/``) se monta en ``/sandbox``; el
    resto del sistema de archivos es de solo lectura y ``/tmp`` es un tmpfs de 64 MiB. Dentro,
    ``timeout -s KILL`` corta los tests al llegar al límite (sale con 124).
    """
    if sandbox.executable is None:
        raise SandboxError("falta la ruta de docker/podman.")
    deps = pytest_mounts() if mounts is None else mounts
    cmd = [
        sandbox.executable,
        "run",
        "--rm",
        "--name",
        name,
        "--pull",
        "never",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        # Sin etiquetas SELinux para los montajes: con SELinux en «enforcing» (Fedora/RHEL, sobre
        # todo con Podman) un bind mount sin etiquetar da «Permission denied». Sin SELinux no
        # cambia nada. Se prefiere a «:z», que reetiquetaría tus site-packages.
        "--security-opt",
        "label=disable",
        "--tmpfs",
        CONTAINER_TMPFS,
        "--memory",
        CONTAINER_MEMORY,
        "--memory-swap",
        CONTAINER_MEMORY,
        "--cpus",
        CONTAINER_CPUS,
        "--pids-limit",
        str(CONTAINER_PIDS),
        *sandbox.user_args,
        "--mount",
        _mount(root, CONTAINER_ROOT),
    ]
    for top, path in deps:
        cmd += ["--mount", _mount(path, f"{CONTAINER_DEPS}/{top}", readonly=True)]
    for var in container_env():
        cmd += ["--env", var]
    cmd += [
        "--workdir",
        f"{CONTAINER_ROOT}/work",
        "--entrypoint",
        "timeout",
        sandbox.image,
        "-s",
        "KILL",
        f"{timeout:g}",
        "python",
        *python_args,
    ]
    return cmd


def container_env() -> list[str]:
    """Entorno del contenedor: solo esto (nada del anfitrión, ni claves ni rutas)."""
    return [
        "HOME=/tmp",
        "TMPDIR=/tmp",
        f"PYTHONPATH={CONTAINER_DEPS}",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONIOENCODING=utf-8",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    ]


def container_name() -> str:
    return f"modelduel-{os.urandom(6).hex()}"


def remove_container(sandbox: Sandbox, name: str, run: Runner = subprocess.run) -> None:
    """``docker rm -f``: para el contenedor si el cliente murió o se agotó el tiempo."""
    if sandbox.executable is None:
        return
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        run(
            [sandbox.executable, "rm", "-f", name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
