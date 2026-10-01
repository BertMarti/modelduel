"""Proveedor omniroute: un preset de openai. Sin red: ``urlopen`` se simula."""

import io
import json
import urllib.error

import pytest

from modelduel.providers import PROVIDERS, ProviderError, base, get_provider, parse_spec
from modelduel.providers.openai_compat import OmniRouteProvider, OpenAIProvider

OK = json.dumps(
    {
        "choices": [{"message": {"content": "```python\nx = 1\n```"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }
).encode()


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def _fake(monkeypatch, *, body=OK, raises=None):
    seen = []

    def urlopen(request, timeout=None):
        seen.append(request)
        if raises:
            raise raises
        return _Resp(body)

    monkeypatch.setattr(base.urllib.request, "urlopen", urlopen)
    return seen


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for name in ("OMNIROUTE_BASE_URL", "OMNIROUTE_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_la_especificacion_es_valida():
    assert "omniroute" in PROVIDERS
    assert parse_spec("omniroute:openai/gpt-4o") == ("omniroute", "openai/gpt-4o")
    provider = get_provider("omniroute:modelo")
    assert provider.spec == "omniroute:modelo"
    assert isinstance(provider, OpenAIProvider)


def test_url_por_defecto_y_sin_clave(monkeypatch):
    seen = _fake(monkeypatch)
    response = get_provider("omniroute:modelo").complete("hola")
    assert seen[0].full_url == "http://localhost:20128/v1/chat/completions"
    assert seen[0].get_header("Authorization") is None
    assert json.loads(seen[0].data)["model"] == "modelo"
    assert (response.input_tokens, response.output_tokens) == (3, 4)


def test_url_y_clave_por_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://otro:9999/v1/")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-omni")
    seen = _fake(monkeypatch)
    get_provider("omniroute:modelo").complete("hola")
    assert seen[0].full_url == "http://otro:9999/v1/chat/completions"
    assert seen[0].get_header("Authorization") == "Bearer sk-omni"


def test_no_usa_las_variables_de_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    seen = _fake(monkeypatch)
    get_provider("omniroute:modelo").complete("hola")
    assert seen[0].full_url.startswith("http://localhost:20128")
    assert seen[0].get_header("Authorization") is None


def test_servidor_apagado_explica_como_arrancarlo(monkeypatch):
    _fake(monkeypatch, raises=urllib.error.URLError(ConnectionRefusedError(10061, "rechazada")))
    with pytest.raises(ProviderError) as info:
        get_provider("omniroute:modelo").complete("hola")
    message = str(info.value)
    assert "omniroute serve" in message
    assert "http://localhost:20128/v1" in message
    assert "OMNIROUTE_BASE_URL" in message


def test_error_http_sigue_el_camino_de_openai_y_redacta_la_clave(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-omni")
    body = json.dumps({"error": {"message": "clave sk-omni no válida"}}).encode()
    error = urllib.error.HTTPError("http://x", 401, "No", {}, io.BytesIO(body))
    _fake(monkeypatch, raises=error)
    with pytest.raises(ProviderError) as info:
        get_provider("omniroute:modelo").complete("hola")
    assert "HTTP 401" in str(info.value)
    assert "sk-omni" not in str(info.value)
    assert "omniroute serve" not in str(info.value)


def test_modelo_obligatorio():
    with pytest.raises(ProviderError, match="omniroute necesita un modelo"):
        OmniRouteProvider("")


def test_openai_sigue_igual_ante_un_servidor_apagado(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    _fake(monkeypatch, raises=urllib.error.URLError(ConnectionRefusedError(10061, "rechazada")))
    with pytest.raises(ProviderError) as info:
        get_provider("openai:llama3").complete("hola")
    assert "No se pudo conectar" in str(info.value)
    assert "omniroute" not in str(info.value)
