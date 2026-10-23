"""Endurecimiento de la ejecución del código de los modelos (v0.8.0).

Entorno sin credenciales, ``HOME`` en el temporal y límites ``setrlimit`` en POSIX.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import pytest

from modelduel.runner import (
    FILE_SIZE_LIMIT_BYTES,
    MEMORY_LIMIT_BYTES,
    OPEN_FILES_LIMIT,
    _no_results_message,
    is_sensitive_var,
    resource_limits,
    run_tests,
    safe_env,
)

posix_only = pytest.mark.skipif(os.name == "nt", reason="setrlimit solo existe en POSIX")


@pytest.mark.parametrize(
    "name",
    [
        "SSH_AUTH_SOCK",
        "MYSQL_PASSWD",
        "GPG_PASSPHRASE",
        "AWS_SESSION_TOKEN",
        "DATABASE_URL",
        "docker_host",
        "KUBECONFIG",
        "SENTRY_DSN",
        "GH_PRIVATE_THING",
        "HTTP_COOKIE",
        "OMNIROUTE_API_KEY",
    ],
)
def test_variables_sensibles(name):
    assert is_sensitive_var(name)


@pytest.mark.parametrize("name", ["PATH", "LANG", "SYSTEMROOT", "COMSPEC", "TERM"])
def test_variables_inofensivas(name):
    assert not is_sensitive_var(name)


def test_safe_env_quita_el_agente_ssh_y_las_bases_de_datos(monkeypatch):
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/user/1000/ssh-agent")
    monkeypatch.setenv("DATABASE_URL", "postgres://usuario:clave@192.168.1.50/db")
    env = safe_env()
    assert "SSH_AUTH_SOCK" not in env and "DATABASE_URL" not in env
    assert "PATH" in env


def test_safe_env_redirige_los_directorios_personales(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/alguien/.config")
    monkeypatch.delenv("PYTHONUSERBASE", raising=False)
    env = safe_env(home=tmp_path)
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME"):
        assert env[name] == str(tmp_path)
    # El pytest instalado con «pip install --user» tiene que seguir cargando.
    assert env["PYTHONUSERBASE"]
    assert "/home/alguien" not in env.values()


def test_sin_home_no_se_tocan_los_directorios_personales(monkeypatch):
    monkeypatch.setenv("HOME", "/home/alguien")
    assert safe_env()["HOME"] == "/home/alguien"


def test_la_solucion_ve_el_home_del_temporal(make_task):
    tests = "from solution import home\n\ndef test_home():\n    assert 'modelduel-' in home()\n"
    code = "import os\n\ndef home():\n    return os.path.expanduser('~')\n"
    assert run_tests(code, make_task(tests)).solved


def test_limites_por_defecto():
    limits = resource_limits(20)
    assert limits["RLIMIT_AS"] == MEMORY_LIMIT_BYTES == 1024**3
    assert limits["RLIMIT_FSIZE"] == FILE_SIZE_LIMIT_BYTES == 64 * 1024**2
    assert limits["RLIMIT_NOFILE"] == OPEN_FILES_LIMIT
    assert limits["RLIMIT_CORE"] == 0
    # La CPU nunca corta antes que el límite de tiempo de pared.
    assert limits["RLIMIT_CPU"] > 20
    assert resource_limits(0.5)["RLIMIT_CPU"] >= 1


@posix_only
def test_la_solucion_corre_con_los_limites_aplicados(make_task):
    tests = """\
import resource

from solution import limit


def test_core():
    assert limit("RLIMIT_CORE") == 0


def test_fsize():
    assert limit("RLIMIT_FSIZE") <= 64 * 1024 * 1024


def test_nofile():
    assert limit("RLIMIT_NOFILE") <= 256


def test_cpu():
    assert limit("RLIMIT_CPU") <= 20 + 5 + 1
"""
    code = (
        "import resource\n\n"
        "def limit(name):\n"
        "    return resource.getrlimit(getattr(resource, name))[1]\n"
    )
    result = run_tests(code, make_task(tests))
    assert result.solved, result.output


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="RLIMIT_AS se respeta en Linux")
def test_la_memoria_esta_acotada_en_linux(make_task):
    tests = """\
from solution import limit


def test_as():
    assert 0 < limit() <= 1024 ** 3
"""
    code = "import resource\n\ndef limit():\n    return resource.getrlimit(resource.RLIMIT_AS)[1]\n"
    assert run_tests(code, make_task(tests)).solved


@posix_only
def test_un_proceso_matado_por_senal_lo_explica(make_task):
    code = "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n"
    from tests.conftest import ADD_TESTS

    result = run_tests(code, make_task(ADD_TESTS))
    assert result.status == "error"
    assert "SIGKILL" in result.message


@posix_only
@pytest.mark.parametrize(
    ("sig", "fragment"),
    [("SIGXCPU", "límite de CPU"), ("SIGXFSZ", "64 MiB"), ("SIGTERM", "SIGTERM")],
)
def test_mensajes_de_senales(sig, fragment):
    assert fragment in _no_results_message(-getattr(signal, sig))


def test_mensaje_de_codigo_normal():
    assert "código 1" in _no_results_message(1)


def test_mensaje_de_senal_desconocida():
    assert "señal" in _no_results_message(-250)


def test_el_arranque_no_usa_preexec_fn():
    # preexec_fn no es seguro con hilos (la señal de vida usa uno): los límites van en el hijo.
    source = Path(__file__).resolve().parent.parent / "src" / "modelduel" / "runner.py"
    assert "preexec_fn" not in source.read_text(encoding="utf-8").replace("``preexec_fn``", "")
