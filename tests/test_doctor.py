"""``modelduel doctor`` (fase 2): nunca muestra claves y solo sale a la red con ``--red``."""

from __future__ import annotations

import shutil

import pytest

from modelduel import doctor
from modelduel.cli import main
from modelduel.doctor import FAIL, OK, WARN, collect_checks, render

SENTINEL = "sk-centinela-NO-DEBE-SALIR-1234567890"


def _text(checks) -> str:
    return render(checks)[0]


def _no_network(*_args):
    raise AssertionError("doctor salió a la red sin --red")


def test_sin_configuracion_ni_claves_no_hay_fallos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    checks = collect_checks(env={}, request=_no_network)
    text, code = render(checks)
    assert code == 0, text
    assert "GEMINI_API_KEY: no definida" in text
    assert "modelduel init" in text and "--red" in text


def test_una_clave_definida_no_se_muestra(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = {"OPENAI_API_KEY": SENTINEL, "GEMINI_API_KEY": f'"{SENTINEL}"'}
    text = _text(collect_checks(env=env, request=_no_network))
    assert SENTINEL not in text and SENTINEL[:8] not in text
    assert "OPENAI_API_KEY: definida (no se muestra)" in text
    assert "comillas o espacios de más" in text  # la de Gemini lleva comillas


def test_url_base_sin_credenciales(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = {"OPENAI_BASE_URL": f"https://usuario:{SENTINEL}@proxy.ejemplo.test/v1"}
    text = _text(collect_checks(env=env, request=_no_network))
    assert "https://proxy.ejemplo.test/v1" in text
    assert SENTINEL not in text and "usuario" not in text


def test_timeout_http_invalido_es_un_fallo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _text_, code = render(collect_checks(env={"MODELDUEL_HTTP_TIMEOUT": "rápido"}))
    assert code == 1


@pytest.fixture
def proyecto(tmp_path, examples_dir, monkeypatch):
    shutil.copytree(examples_dir / "tasks", tmp_path / "tasks")
    monkeypatch.chdir(tmp_path)

    def write(models: str):
        (tmp_path / "modelduel.toml").write_text(
            f'tareas = "tasks"\nmodelos = [{models}]\n', encoding="utf-8"
        )

    return write


def test_configuracion_con_gemini_sin_clave_falla(proyecto):
    proyecto('"gemini:m", "replay:alfa"')
    text, code = render(collect_checks(env={}, request=_no_network))
    assert code == 1
    assert f"{FAIL} gemini:m necesita GEMINI_API_KEY" in text
    assert 'export GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"' in text


def test_openai_local_no_necesita_clave(proyecto):
    proyecto('"openai:llama3", "replay:alfa"')
    checks = collect_checks(env={"OPENAI_BASE_URL": "http://localhost:11434/v1"})
    assert render(checks)[1] == 0


def test_marcador_y_proveedor_desconocido_fallan(proyecto):
    proyecto('"gemini:CAMBIA-ESTO", "foo:bar"')
    text, code = render(collect_checks(env={"GEMINI_API_KEY": SENTINEL}))
    assert code == 1
    assert "cambia «gemini:CAMBIA-ESTO»" in text and "desconocido" in text
    assert SENTINEL not in text


def test_configuracion_rota_falla(proyecto, tmp_path):
    (tmp_path / "modelduel.toml").write_text("modelos = [", encoding="utf-8")
    text, code = render(collect_checks(env={}))
    assert code == 1 and "no es un TOML válido" in text


def test_red_simulada(proyecto):
    proyecto('"gemini:m", "openai:n"')
    calls = []

    def fake(url, headers, timeout):
        calls.append((url, headers))
        return 200 if "googleapis" in url else 401

    env = {"GEMINI_API_KEY": SENTINEL, "OPENAI_API_KEY": SENTINEL + "x"}
    text, code = render(collect_checks(network=True, env=env, request=fake))
    assert code == 1
    assert f"{OK} gemini: https://generativelanguage.googleapis.com/v1beta/models responde" in text
    assert "HTTP 401: la clave no es válida" in text
    assert SENTINEL not in text
    # La clave viaja en cabeceras, nunca en la URL.
    assert all(SENTINEL not in url for url, _ in calls)
    assert calls[0][1] == {"x-goog-api-key": SENTINEL}
    assert calls[1][1] == {"Authorization": f"Bearer {SENTINEL}x"}


def test_red_sin_conexion_da_una_pista(proyecto):
    proyecto('"omniroute:m", "replay:alfa"')

    def refused(url, headers, timeout):
        raise ConnectionRefusedError(111, "Connection refused")

    text, code = render(collect_checks(network=True, env={}, request=refused))
    assert code == 1
    assert "¿está en marcha el servicio" in text


def test_red_tiempo_agotado(proyecto):
    proyecto('"openai:m", "replay:alfa"')

    def slow(url, headers, timeout):
        raise TimeoutError

    text, _ = render(collect_checks(network=True, env={"OPENAI_API_KEY": "k"}, request=slow))
    assert "no respondió" in text


def test_red_sin_configuracion_solo_proveedores_definidos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seen = []

    def fake(url, headers, timeout):
        seen.append(url)
        return 200

    collect_checks(network=True, env={"OPENAI_BASE_URL": "http://localhost:11434/v1"}, request=fake)
    assert seen == ["http://localhost:11434/v1/models"]


def test_gemini_sin_clave_no_se_consulta(proyecto):
    proyecto('"gemini:m", "replay:alfa"')
    text = _text(collect_checks(network=True, env={}, request=_no_network))
    assert f"{WARN} gemini: se omite" in text


def test_orden_doctor(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor, "http_get_status", _no_network)
    for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "OMNIROUTE_API_KEY", "MODELDUEL_HTTP_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "Instalación" in out and "pytest" in out and "Todo listo" in out
