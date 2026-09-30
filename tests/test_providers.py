import pytest

from modelduel.providers import ProviderError, get_provider, parse_spec
from modelduel.providers.base import redact
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
