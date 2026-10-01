import http.client
import io
import json
import urllib.error

import pytest

from modelduel.providers import ProviderError, base, get_provider, parse_spec
from modelduel.providers.base import post_json, redact
from modelduel.providers.gemini import GeminiProvider, parse_gemini_response
from modelduel.providers.openai_compat import OpenAIProvider, parse_openai_response
from modelduel.providers.replay import ReplayProvider, parse_front_matter


def test_parse_spec():
    assert parse_spec("replay:alfa") == ("replay", "alfa")
    assert parse_spec("openai:org/modelo:free") == ("openai", "org/modelo:free")
    for bad in ("replay", "replay:", "nada:modelo"):
        with pytest.raises(ProviderError):
            parse_spec(bad)


def test_front_matter():
    meta, body = parse_front_matter(
        "---\n# comentario\ninput_tokens: 10\nlatency_s: 1.5\n---\nhola\n"
    )
    assert meta == {"input_tokens": "10", "latency_s": "1.5"}
    assert body == "hola\n"


def test_front_matter_ausente():
    assert parse_front_matter("solo texto") == ({}, "solo texto")


def test_replay_lee_respuestas_grabadas(examples_dir):
    provider = get_provider("replay:alfa", [examples_dir / "replays"])
    response = provider.complete("prompt", task_id="slugify")
    assert "def slugify" in response.text
    assert response.input_tokens == 412
    assert response.output_tokens == 188
    assert response.latency_s == pytest.approx(2.84)


def test_replay_sin_front_matter(tmp_path):
    (tmp_path / "gamma").mkdir()
    (tmp_path / "gamma" / "t.md").write_text("```python\nx = 1\n```", encoding="utf-8")
    response = ReplayProvider("gamma", [tmp_path]).complete("p", task_id="t")
    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.latency_s == 0.0


def test_replay_errores(tmp_path, examples_dir):
    with pytest.raises(ProviderError, match="No encuentro"):
        ReplayProvider("no-existe", [tmp_path])
    provider = ReplayProvider("alfa", [examples_dir / "replays"])
    with pytest.raises(ProviderError, match="No hay respuesta grabada"):
        provider.complete("p", task_id="otra_tarea")
    with pytest.raises(ProviderError):
        provider.complete("p")


def test_gemini_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiProvider("gemini-x")


def test_openai_sin_clave(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        OpenAIProvider("modelo")


def test_openai_local_no_necesita_clave(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1/")
    provider = OpenAIProvider("llama3")
    assert provider.base_url == "http://localhost:11434/v1"


def test_parse_gemini_response():
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "pensando…", "thought": True},
                        {"text": "```python\nx = 1\n```"},
                    ]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 11,
            "candidatesTokenCount": 7,
            "thoughtsTokenCount": 5,
        },
    }
    response = parse_gemini_response(data, 1.25)
    assert response.text == "```python\nx = 1\n```"
    assert (response.input_tokens, response.output_tokens) == (11, 12)
    assert response.latency_s == 1.25


def test_parse_gemini_bloqueado():
    with pytest.raises(ProviderError, match="SAFETY"):
        parse_gemini_response({"promptFeedback": {"blockReason": "SAFETY"}}, 0.1)


def test_parse_openai_response():
    data = {
        "choices": [{"message": {"content": "hola"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }
    response = parse_openai_response(data, 0.5)
    assert (response.text, response.input_tokens, response.output_tokens) == ("hola", 3, 4)


def test_parse_openai_sin_uso_ni_opciones():
    response = parse_openai_response({"choices": [{"message": {"content": "x"}}]}, 0.5)
    assert response.input_tokens is None
    with pytest.raises(ProviderError, match="cuota"):
        parse_openai_response({"error": {"message": "cuota agotada"}}, 0.1)


def test_redact_oculta_claves():
    assert redact("fallo con sk-123 en la url", ("sk-123",)) == "fallo con *** en la url"


# ---------------------------------------------------------------- red simulada (qa)


class _FakeResponse:
    def __init__(self, body: bytes, error: Exception | None = None):
        self.body = body
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        if self.error:
            raise self.error
        return self.body


def _fake_urlopen(monkeypatch, *, body=b"{}", raises=None, read_error=None, seen=None):
    def fake(request, timeout=None):
        if seen is not None:
            seen.append((request, timeout))
        if raises is not None:
            raise raises
        return _FakeResponse(body, read_error)

    monkeypatch.setattr(base.urllib.request, "urlopen", fake)


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x.test", code, "Error", {}, io.BytesIO(body))


def test_error_http_de_openai_muestra_el_mensaje_y_no_el_json(monkeypatch):
    body = json.dumps({"error": {"message": "Incorrect API key", "type": "invalid_request"}})
    _fake_urlopen(monkeypatch, raises=_http_error(401, body.encode()))
    with pytest.raises(ProviderError) as info:
        post_json("https://x.test/v1/chat/completions", {}, {}, secrets=("sk-secreta",))
    message = str(info.value)
    assert "HTTP 401" in message and "Incorrect API key" in message
    assert '{"error"' not in message
    assert "clave" in message  # pista en español


def test_error_http_de_gemini_con_estado(monkeypatch):
    body = {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    _fake_urlopen(monkeypatch, raises=_http_error(429, json.dumps(body).encode()))
    with pytest.raises(ProviderError, match="RESOURCE_EXHAUSTED: Quota exceeded"):
        post_json("https://x.test", {}, {})


def test_error_http_redacta_la_clave_devuelta(monkeypatch):
    body = json.dumps({"error": {"message": "clave sk-secreta no válida"}}).encode()
    _fake_urlopen(monkeypatch, raises=_http_error(401, body))
    with pytest.raises(ProviderError) as info:
        post_json("https://x.test", {}, {}, secrets=("sk-secreta",))
    assert "sk-secreta" not in str(info.value)


def test_error_http_con_cuerpo_no_json(monkeypatch):
    _fake_urlopen(monkeypatch, raises=_http_error(502, b"<html>Bad gateway</html>"))
    with pytest.raises(ProviderError, match="HTTP 502.*Bad gateway"):
        post_json("https://x.test", {}, {})


@pytest.mark.parametrize(
    "raises",
    [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))],
)
def test_tiempo_de_espera_de_red_en_espanol(monkeypatch, raises):
    monkeypatch.delenv("MODELDUEL_HTTP_TIMEOUT", raising=False)
    _fake_urlopen(monkeypatch, raises=raises)
    with pytest.raises(ProviderError, match="superó 90 s"):
        post_json("https://x.test", {}, {})


@pytest.mark.parametrize(
    ("raises", "read_error"),
    [
        (http.client.RemoteDisconnected("Remote end closed connection"), None),
        (None, ConnectionResetError(10054, "reset")),
        (None, http.client.IncompleteRead(b"")),
    ],
)
def test_cortes_de_conexion_son_errores_del_proveedor(monkeypatch, raises, read_error):
    # Antes se escapaban como excepciones sin capturar y se perdía todo el duelo.
    _fake_urlopen(monkeypatch, raises=raises, read_error=read_error)
    with pytest.raises(ProviderError, match="x.test"):
        post_json("https://x.test", {}, {})


def test_respuesta_no_json(monkeypatch):
    _fake_urlopen(monkeypatch, body=b"\xff\xfe no es json")
    with pytest.raises(ProviderError, match="no JSON"):
        post_json("https://x.test", {}, {})


def test_timeout_http_configurable_y_validado(monkeypatch):
    seen = []
    _fake_urlopen(monkeypatch, body=b"{}", seen=seen)
    monkeypatch.setenv("MODELDUEL_HTTP_TIMEOUT", "7,5")
    post_json("https://x.test", {}, {})
    assert seen[0][1] == 7.5
    for bad in ("abc", "0", "-3", "nan"):
        monkeypatch.setenv("MODELDUEL_HTTP_TIMEOUT", bad)
        with pytest.raises(ProviderError, match="MODELDUEL_HTTP_TIMEOUT"):
            post_json("https://x.test", {}, {})


def test_gemini_completo_con_clave_en_cabecera(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa")
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    seen = []
    body = {"candidates": [{"content": {"parts": [{"text": "hola"}]}}], "usageMetadata": {}}
    _fake_urlopen(monkeypatch, body=json.dumps(body).encode(), seen=seen)
    response = GeminiProvider("gemini-x").complete("p")
    request = seen[0][0]
    assert response.text == "hola"
    assert "clave-falsa" not in request.full_url
    assert request.get_header("X-goog-api-key") == "clave-falsa"


@pytest.mark.parametrize("data", [[], "texto", None, {"candidates": ["raro"]}])
def test_gemini_formato_inesperado(data):
    with pytest.raises(ProviderError):
        parse_gemini_response(data, 0.1)


def test_gemini_sin_texto_explica_el_motivo():
    data = {"candidates": [{"finishReason": "SAFETY"}], "usageMetadata": {}}
    with pytest.raises(ProviderError, match="SAFETY"):
        parse_gemini_response(data, 0.1)


def test_gemini_partes_con_texto_nulo():
    data = {"candidates": [{"content": {"parts": [{"text": None}, {"text": "x"}]}}]}
    assert parse_gemini_response(data, 0.1).text == "x"


@pytest.mark.parametrize("data", [[], "texto", None, {"choices": ["raro"]}])
def test_openai_formato_inesperado(data):
    with pytest.raises(ProviderError):
        parse_openai_response(data, 0.1)


def test_openai_sin_contenido_explica_el_motivo():
    data = {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
    with pytest.raises(ProviderError, match="length"):
        parse_openai_response(data, 0.1)
    data = {"choices": [{"message": {"content": None, "refusal": "No puedo ayudar"}}]}
    with pytest.raises(ProviderError, match="No puedo ayudar"):
        parse_openai_response(data, 0.1)


def test_openai_partes_con_texto_nulo_y_error_como_texto():
    data = {"choices": [{"message": {"content": [{"text": None}, {"text": "y"}]}}]}
    assert parse_openai_response(data, 0.1).text == "y"
    with pytest.raises(ProviderError, match="sobrecargado"):
        parse_openai_response({"error": "sobrecargado"}, 0.1)
