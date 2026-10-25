"""Aislamiento (fase 3): contenedor Docker/Podman, red cortada en Linux y memoria en Windows.

Ningún test arranca contenedores reales salvo los marcados con ``MODELDUEL_TEST_DOCKER=1`` (el CI
de Ubuntu lo activa). El camino del contenedor se prueba con un «docker» falso que ejecuta la
orden en local, para comprobar rutas, códigos de salida y limpieza sin depender de Docker.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap

import pytest

from modelduel import runner, sandbox
from modelduel.cli import main
from modelduel.doctor import FAIL, OK, WARN, isolation_checks
from modelduel.runner import run_tests
from modelduel.sandbox import (
    CONTAINER_MEMORY,
    CONTAINER_PIDS,
    DEFAULT_IMAGE,
    Sandbox,
    SandboxError,
    container_command,
    container_env,
    network_isolation_available,
    prepare_container,
    pytest_mounts,
    resolve_sandbox,
)
from tests.conftest import ADD_TESTS

ADD_OK = "```python\ndef add(a, b):\n    return a + b\n```"
GOOD = "def add(a, b):\n    return a + b\n"


def _docker(**kwargs) -> Sandbox:
    return Sandbox(kind="docker", executable="/usr/bin/docker", **kwargs)


def _value_after(cmd: list[str], flag: str) -> list[str]:
    return [cmd[i + 1] for i, part in enumerate(cmd[:-1]) if part == flag]


# ---------------------------------------------------------------- imagen y orden


def test_la_imagen_es_la_oficial_de_python_fijada_por_digest():
    assert re.fullmatch(r"python:3\.\d+\.\d+-slim@sha256:[0-9a-f]{64}", DEFAULT_IMAGE)


def test_la_orden_del_contenedor_aisla_red_privilegios_y_recursos(tmp_path):
    mounts = (("_pytest", tmp_path / "_pytest"), ("pytest", tmp_path / "pytest"))
    cmd = container_command(
        _docker(user_args=("--user", "1000:1000")),
        name="modelduel-abc",
        root=tmp_path,
        python_args=["-c", "print(1)"],
        timeout=20,
        mounts=mounts,
    )
    image_at = cmd.index(DEFAULT_IMAGE)
    options = cmd[:image_at]
    assert cmd[:3] == ["/usr/bin/docker", "run", "--rm"]
    assert _value_after(options, "--network") == ["none"]
    assert _value_after(options, "--cap-drop") == ["ALL"]
    assert _value_after(options, "--security-opt") == ["no-new-privileges"]
    assert "--read-only" in options
    assert _value_after(options, "--pull") == ["never"]
    assert _value_after(options, "--memory") == [CONTAINER_MEMORY]
    assert _value_after(options, "--memory-swap") == [CONTAINER_MEMORY]  # sin swap extra
    assert _value_after(options, "--pids-limit") == [str(CONTAINER_PIDS)]
    assert _value_after(options, "--cpus") == ["1"]
    assert _value_after(options, "--user") == ["1000:1000"]
    assert _value_after(options, "--name") == ["modelduel-abc"]
    assert _value_after(options, "--tmpfs")[0].startswith("/tmp:")
    assert "--privileged" not in cmd
    mounts_text = _value_after(options, "--mount")
    assert mounts_text[0] == f"type=bind,source={tmp_path},target=/sandbox"
    # pytest y compañía, siempre de solo lectura.
    assert all(m.endswith(",readonly") for m in mounts_text[1:])
    assert f"type=bind,source={tmp_path / '_pytest'},target=/deps/_pytest,readonly" in mounts_text
    # Tras la imagen: timeout de coreutils que mata a los 20 s y el Python del contenedor.
    assert cmd[image_at + 1 :] == ["-s", "KILL", "20", "python", "-c", "print(1)"]
    assert _value_after(options, "--entrypoint") == ["timeout"]


def test_al_contenedor_no_llega_ninguna_variable_del_anfitrion(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secreto-de-prueba")
    monkeypatch.setenv("HOME", "/home/alguien")
    cmd = container_command(
        _docker(), name="n", root=tmp_path, python_args=[], timeout=5, mounts=()
    )
    envs = _value_after(cmd, "--env")
    assert envs == container_env()
    assert "HOME=/tmp" in envs
    assert not any("sk-secreto" in part or "/home/alguien" in part for part in cmd)


def test_rutas_con_coma_se_rechazan(tmp_path):
    raro = tmp_path / "a,b"
    with pytest.raises(SandboxError, match="«,»"):
        container_command(_docker(), name="n", root=raro, python_args=[], timeout=5, mounts=())


def test_los_paquetes_de_pytest_se_encuentran_para_montarlos():
    mounts = dict(pytest_mounts())
    assert {"pytest", "_pytest", "pluggy", "iniconfig"} <= set(mounts)
    assert all(path.exists() for path in mounts.values())
    assert not any(name.endswith((".dist-info", ".pth")) for name in mounts)


# ---------------------------------------------------------------- elección y preparación


def test_sandbox_desconocido_o_herramienta_ausente_dan_un_error_claro():
    with pytest.raises(SandboxError, match="no es válido"):
        resolve_sandbox("kvm")
    with pytest.raises(SandboxError, match="no encuentro «docker»") as info:
        resolve_sandbox("docker", which=lambda _name: None)
    assert "--sandbox podman" in str(info.value)
    with pytest.raises(SandboxError, match="no encuentro «podman»"):
        resolve_sandbox("podman", which=lambda _name: None)


def test_sandbox_elegidos():
    assert resolve_sandbox("ninguno") == Sandbox()
    found = resolve_sandbox("docker", which=lambda name: f"/opt/{name}")
    assert found.is_container and found.executable == "/opt/docker"
    assert resolve_sandbox("podman", "mi/imagen:1", which=lambda n: n).image == "mi/imagen:1"
    auto = resolve_sandbox(None)
    assert not auto.is_container
    assert auto.isolate_network == network_isolation_available()


class FakeRun:
    """Sustituye a ``subprocess.run`` en ``prepare_container``: nada llega a Docker."""

    def __init__(self, codes: dict[str, int], info: str = '["name=seccomp"]') -> None:
        self.codes = codes
        self.info = info
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **_kwargs):
        self.calls.append(cmd)
        verb = cmd[1]
        stdout = self.info if verb == "info" else ""
        return subprocess.CompletedProcess(cmd, self.codes.get(verb, 0), stdout, "fallo raro")


def test_preparar_con_la_imagen_ya_descargada_no_descarga():
    fake = FakeRun({})
    ready = prepare_container(_docker(), run=fake)
    # En Windows (Docker Desktop) no hay UID que pasar y no se consulta «info».
    expected = ["image", "info"] if hasattr(os, "getuid") else ["image"]
    assert [c[1] for c in fake.calls] == expected
    if hasattr(os, "getuid"):
        assert ready.user_args == ("--user", f"{os.getuid()}:{os.getgid()}")


def test_preparar_descarga_la_imagen_una_vez_y_avisa():
    fake = FakeRun({"image": 1})
    notes: list[str] = []
    prepare_container(_docker(), run=fake, notify=notes.append)
    assert ["/usr/bin/docker", "pull", DEFAULT_IMAGE] in fake.calls
    assert "solo la primera vez" in notes[0]


def test_preparar_explica_si_no_se_puede_descargar():
    with pytest.raises(SandboxError) as info:
        prepare_container(_docker(), run=FakeRun({"image": 1, "pull": 1}))
    assert "docker pull" in str(info.value) and "fallo raro" in str(info.value)


def test_preparar_explica_si_docker_no_responde():
    def slow(cmd, **_kwargs):
        raise subprocess.TimeoutExpired(cmd, 60)

    with pytest.raises(SandboxError, match="no responde"):
        prepare_container(_docker(), run=slow)
    if hasattr(os, "getuid"):
        with pytest.raises(SandboxError, match="Docker no responde"):
            prepare_container(_docker(), run=FakeRun({"info": 1}))


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="Windows no tiene UID")
def test_usuario_segun_el_motor():
    rootless = prepare_container(_docker(), run=FakeRun({}, info='["name=rootless"]'))
    assert rootless.user_args == ()
    podman = Sandbox(kind="podman", executable="/usr/bin/podman")
    assert prepare_container(podman, run=FakeRun({})).user_args == ("--userns=keep-id",)


# ---------------------------------------------------------------- ejecución con un docker falso

# El «docker» falso es ``python`` (así funciona igual en Windows): la orden queda
# ``python run --rm …`` o ``python rm -f …`` y Python ejecuta los archivos «run» y «rm» de la
# carpeta actual, que son este script.
FAKE_DOCKER = r'''
"""docker falso: ejecuta en local lo que iría en el contenedor (solo para tests)."""
import os, subprocess, sys
args = [os.path.basename(sys.argv[0]), *sys.argv[1:]]
log = os.environ["FAKE_DOCKER_LOG"]
with open(log, "a") as fh:
    fh.write(" ".join(args[:2]) + "\n")
if args[0] != "run":
    sys.exit(0)
if os.environ.get("FAKE_DOCKER_HANG"):
    import time
    time.sleep(30)
forced = os.environ.get("FAKE_DOCKER_EXIT")
if forced:
    print("docker: Error response from daemon: algo falló")
    sys.exit(int(forced))
root = None
for i, part in enumerate(args):
    if part == "--mount" and args[i + 1].endswith("target=/sandbox"):
        root = args[i + 1].split("source=")[1].split(",target=")[0]
image_at = args.index(os.environ["FAKE_DOCKER_IMAGE"])
_, _, seconds, _python, *rest = args[image_at + 1:]
rest = [part.replace("/sandbox", root) for part in rest]
try:
    proc = subprocess.run([sys.executable, *rest], cwd=os.path.join(root, "work"),
                          timeout=float(seconds))
except subprocess.TimeoutExpired:
    sys.exit(124)
sys.exit(proc.returncode)
'''


@pytest.fixture
def fake_docker(tmp_path, monkeypatch):
    folder = tmp_path / "docker-falso"
    folder.mkdir()
    for verb in ("run", "rm"):
        (folder / verb).write_text(FAKE_DOCKER, encoding="utf-8")
    monkeypatch.chdir(folder)
    log = tmp_path / "docker.log"
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log))
    monkeypatch.setenv("FAKE_DOCKER_IMAGE", DEFAULT_IMAGE)
    return Sandbox(kind="docker", executable=sys.executable), log


def test_contenedor_falso_resuelve_y_limpia(make_task, fake_docker):
    box, log = fake_docker
    result = run_tests(GOOD, make_task(ADD_TESTS), timeout=20, sandbox=box)
    assert result.solved, result.output
    assert result.passed == 3
    assert "/sandbox" not in result.output
    assert log.read_text().splitlines() == ["run --rm"]  # terminó bien: sin rm -f


def test_contenedor_falso_agota_el_tiempo(make_task, fake_docker):
    box, _log = fake_docker
    slow = "import time\n\ndef add(a, b):\n    time.sleep(30)\n"
    result = run_tests(slow, make_task(ADD_TESTS), timeout=1, sandbox=box)
    assert result.status == "timeout"


def test_contenedor_que_no_arranca_es_un_error_claro(make_task, fake_docker, monkeypatch):
    box, _log = fake_docker
    monkeypatch.setenv("FAKE_DOCKER_EXIT", "125")
    result = run_tests(GOOD, make_task(ADD_TESTS), timeout=10, sandbox=box)
    assert result.status == "error" and not result.solved
    assert "docker no pudo ejecutar los tests" in result.message


def test_contenedor_matado_por_memoria_no_cuenta(make_task, fake_docker, monkeypatch):
    box, _log = fake_docker
    monkeypatch.setenv("FAKE_DOCKER_EXIT", "137")
    result = run_tests(GOOD, make_task(ADD_TESTS), timeout=10, sandbox=box)
    assert not result.solved
    assert "memoria" in result.message


def test_si_el_cliente_no_vuelve_se_borra_el_contenedor(make_task, fake_docker, monkeypatch):
    box, log = fake_docker
    monkeypatch.setattr(runner, "CONTAINER_GRACE_S", 0.0)
    monkeypatch.setenv("FAKE_DOCKER_HANG", "1")  # el cliente se cuelga y no vuelve
    result = run_tests(GOOD, make_task(ADD_TESTS), timeout=0.5, sandbox=box)
    assert result.status == "timeout"
    assert any(line.startswith("rm -f") for line in log.read_text().splitlines())


def test_run_con_sandbox_docker_falso_de_principio_a_fin(
    examples_dir, tmp_path, monkeypatch, capsys, fake_docker
):
    box, _log = fake_docker
    monkeypatch.setattr("modelduel.cli.resolve_sandbox", lambda *_a, **_k: box)
    monkeypatch.setattr("modelduel.cli.prepare_container", lambda sb, **_k: sb)
    out = tmp_path / "o"
    args = ["run", str(examples_dir / "tasks" / "slugify"), "--a", "replay:alfa"]
    assert main([*args, "--b", "replay:beta", "--sandbox", "docker", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "Aislamiento: contenedor docker sin red" in printed
    data = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert data["tasks"][0]["results"]["a"][0]["solved"]


def test_run_con_docker_ausente_sale_con_error_de_uso(examples_dir, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda _name, *a, **k: None)
    args = ["run", str(examples_dir / "tasks" / "slugify"), "--a", "replay:alfa"]
    code = main([*args, "--b", "replay:beta", "--sandbox", "docker", "--out", str(tmp_path / "o")])
    assert code == 2
    assert "no encuentro «docker»" in capsys.readouterr().err


# ---------------------------------------------------------------- red cortada en Linux

needs_netns = pytest.mark.skipif(
    not network_isolation_available(), reason="este sistema no permite espacios de nombres"
)

NET_TESTS = textwrap.dedent(
    """\
    import os
    import socket

    import pytest

    from solution import add


    def test_solo_hay_loopback():
        assert [name for _, name in socket.if_nameindex()] == ["lo"]


    def test_no_hay_salida_a_internet():
        with pytest.raises(OSError):
            socket.create_connection(("1.1.1.1", 53), timeout=2)


    def test_mismo_usuario_sin_root():
        assert os.getuid() != 0 or os.environ.get("MODELDUEL_ROOT_OK")
        assert add(1, 1) == 2
    """
)


@needs_netns
def test_la_red_esta_cortada_por_defecto_en_linux(make_task):
    result = run_tests(GOOD, make_task(NET_TESTS))
    assert result.solved, result.output


@needs_netns
def test_con_sandbox_ninguno_la_red_no_se_toca(make_task):
    result = run_tests(GOOD, make_task(NET_TESTS), sandbox=Sandbox())
    # Sin espacio de nombres se ven las interfaces reales de la máquina (al menos una más).
    assert not result.solved


def test_fallo_al_cortar_la_red_no_ejecuta_nada(make_task, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise runner._SetupFailed("No se pudo cortar la red de los tests")

    monkeypatch.setattr(runner, "_execute", refuse)
    result = run_tests(GOOD, make_task(ADD_TESTS), sandbox=Sandbox(isolate_network=True))
    assert result.status == "error" and not result.solved
    assert "cortar la red" in result.message


def test_sin_supervisor_no_se_ejecuta_con_red_por_sorpresa(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "supervisor_supported", lambda: False)
    with pytest.raises(runner._SetupFailed):
        runner._execute(["true"], tmp_path, {}, tmp_path / "o.log", 5, isolate_network=True)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="supervisor solo en Linux")
def test_supervisor_que_no_puede_cortar_la_red_avisa(make_task, monkeypatch):
    # Simula un kernel que lo prohíbe: el supervisor informa «nonet» y no lanza pytest.
    broken = runner._SUPERVISOR.replace(
        "os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET)", "raise PermissionError(1, 'no')"
    )
    assert broken != runner._SUPERVISOR
    monkeypatch.setattr(runner, "_SUPERVISOR", broken)
    if not runner.supervisor_supported():
        pytest.skip("sin subreaper")
    result = run_tests(GOOD, make_task(ADD_TESTS), sandbox=Sandbox(isolate_network=True))
    assert result.status == "error"
    assert "No se pudo cortar la red" in result.message


# ---------------------------------------------------------------- Windows


@pytest.mark.skipif(ctypes.sizeof(ctypes.c_void_p) != 8, reason="tamaños de 64 bits")
def test_estructura_del_limite_de_memoria_de_windows():
    info = runner.job_memory_limit_info(512 * 1024 * 1024)
    # sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION) en Windows de 64 bits.
    assert ctypes.sizeof(info) == 144
    assert info.ProcessMemoryLimit == 512 * 1024 * 1024
    flags = info.BasicLimitInformation.LimitFlags
    assert flags & runner.JOB_OBJECT_LIMIT_PROCESS_MEMORY
    assert flags & runner.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE


@pytest.mark.skipif(os.name != "nt", reason="Job Object solo en Windows")
def test_windows_no_deja_pasar_de_la_memoria_del_job(make_task):
    greedy = (
        "def add(a, b):\n"
        f"    block = bytearray({runner.WINDOWS_MEMORY_LIMIT_BYTES + 512 * 1024 * 1024})\n"
        "    return a + b + len(block) * 0\n"
    )
    result = run_tests(greedy, make_task(ADD_TESTS), timeout=60)
    assert not result.solved
    assert "MemoryError" in result.output


@pytest.mark.skipif(os.name != "nt", reason="Job Object solo en Windows")
def test_windows_por_debajo_del_limite_funciona(make_task):
    modest = "def add(a, b):\n    block = bytearray(64 * 1024 * 1024)\n    return a + b\n"
    assert run_tests(modest, make_task(ADD_TESTS), timeout=60).solved


# ---------------------------------------------------------------- doctor


def test_doctor_recomienda_el_contenedor_si_lo_hay():
    checks = isolation_checks(tools=["podman"], netns=True)
    texts = [c.text for c in checks]
    assert any(c.status == OK and "podman instalado" in c.text for c in checks)
    assert "recomendado para código no fiable: --sandbox podman" in texts[-1]


def test_doctor_sin_contenedor_ni_espacios_de_nombres_avisa():
    checks = isolation_checks(tools=[], netns=False)
    assert any(c.status == WARN for c in checks)
    assert "--solo-generar" in checks[-1].text
    only_netns = isolation_checks(tools=[], netns=True)
    assert "ya corta la red" in only_netns[-1].text


def test_doctor_falla_si_la_configuracion_pide_un_contenedor_ausente(tmp_path):
    from modelduel.config import Config

    config = Config(path=tmp_path / "m.toml", tasks=tmp_path, models=[], sandbox="docker")
    checks = isolation_checks(tools=[], netns=True, config=config)
    assert checks[-1].status == FAIL and "docker" in checks[-1].text


# ---------------------------------------------------------------- Docker de verdad (solo CI)

real_docker = pytest.mark.skipif(
    os.environ.get("MODELDUEL_TEST_DOCKER") != "1" or shutil.which("docker") is None,
    reason="Docker real solo con MODELDUEL_TEST_DOCKER=1 (lo activa el CI de Ubuntu)",
)

HOSTILE_TESTS = textwrap.dedent(
    """\
    import os
    import socket

    import pytest

    from solution import add


    def test_suma():
        assert add(2, 3) == 5


    def test_sin_red():
        with pytest.raises(OSError):
            socket.create_connection(("1.1.1.1", 53), timeout=2)


    def test_sistema_de_solo_lectura():
        with pytest.raises(OSError):
            open("/usr/modelduel-escrito", "w")


    def test_sin_root_y_sin_secretos():
        assert os.getuid() != 0
        assert "OPENAI_API_KEY" not in os.environ
        assert os.environ["HOME"] == "/tmp"
    """
)


@real_docker
def test_docker_de_verdad(make_task, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-no-debe-llegar")
    box = prepare_container(resolve_sandbox("docker"))
    result = run_tests(GOOD, make_task(HOSTILE_TESTS), timeout=60, sandbox=box)
    assert result.solved, result.output


@real_docker
def test_docker_de_verdad_agota_el_tiempo(make_task):
    box = prepare_container(resolve_sandbox("docker"))
    slow = "import time\n\ndef add(a, b):\n    time.sleep(60)\n"
    result = run_tests(slow, make_task(ADD_TESTS), timeout=3, sandbox=box)
    assert result.status == "timeout"
