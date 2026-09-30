"""Reintentos con espera exponencial ante 429/5xx y cortes de conexión (sin red ni esperas)."""

from __future__ import annotations

import email.message
import http.client
import io
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from modelduel.cli import main
from modelduel.providers import ProviderError, base, get_provider
from modelduel.providers.base import RetryPolicy, parse_retry_after, post_json
from modelduel.providers.gemini import GeminiProvider
from modelduel.providers.openai_compat import OpenAIProvider

OK_BODY = json.dumps({"choices": [{"message": {"content": "hola"}}]}).encode()


class _Ok:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return OK_BODY


def _http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    body = json.dumps({"error": {"message": f"fallo {code}"}}).encode()
    return urllib.error.HTTPError("https://x.test", code, "Error", headers, io.BytesIO(body))


def _script(monkeypatch, outcomes):
    """``urlopen`` que devuelve o lanza, en orden, cada elemento de ``outcomes``."""
    calls = []
    queue = list(outcomes)

    def fake(request, timeout=None):
        calls.append(request)
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(base.urllib.request, "urlopen", fake)
    return calls


def _policy(retries=3, **kwargs):
    sleeps: list[float] = []
    notes: list[str] = []
    policy = RetryPolicy(
        retries=retries,
        notify=notes.append,
        sleep=sleeps.append,
        rng=lambda: 1.0,  # jitter máximo: la espera es exactamente base x 2^n
        **kwargs,
    )
    return policy, sleeps, notes


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_reintenta_los_codigos_transitorios(monkeypatch, code):
    calls = _script(monkeypatch, [_http_error(code), _Ok()])
    policy, sleeps, notes = _policy()
    data, _latency = post_json("https://x.test", {}, {}, retry=policy)
    assert data["choices"][0]["message"]["content"] == "hola"
    assert len(calls) == 2
    assert sleeps == [1.0]
    assert f"HTTP {code}" in notes[0]


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_no_reintenta_errores_del_cliente(monkeypatch, code):
    calls = _script(monkeypatch, [_http_error(code), _Ok()])
    policy, sleeps, _notes = _policy()
    with pytest.raises(ProviderError, match=f"HTTP {code}"):
        post_json("https://x.test", {}, {}, retry=policy)
    assert len(calls) == 1 and sleeps == []


def test_espera_exponencial_y_se_rinde_tras_los_reintentos(monkeypatch):
    calls = _script(monkeypatch, [_http_error(503)] * 4)
    policy, sleeps, notes = _policy(retries=3)
    with pytest.raises(ProviderError) as info:
        post_json("https://x.test", {}, {}, retry=policy)
    assert len(calls) == 4  # 1 intento + 3 reintentos
    assert sleeps == [1.0, 2.0, 4.0]
    assert "HTTP 503" in str(info.value) and "tras 3 reintentos" in str(info.value)
    assert [n.split(":")[0] for n in notes] == [
        "reintento 1/3 en 1.0 s",
        "reintento 2/3 en 2.0 s",
        "reintento 3/3 en 4.0 s",
    ]


def test_un_solo_reintento_en_singular(monkeypatch):
    _script(monkeypatch, [_http_error(500)] * 2)
    policy, _sleeps, _notes = _policy(retries=1)
    with pytest.raises(ProviderError, match=r"tras 1 reintento\)"):
        post_json("https://x.test", {}, {}, retry=policy)


def test_sin_reintentos_no_espera_ni_avisa(monkeypatch):
    calls = _script(monkeypatch, [_http_error(429)])
    policy, sleeps, notes = _policy(retries=0)
    with pytest.raises(ProviderError) as info:
        post_json("https://x.test", {}, {}, retry=policy)
    assert len(calls) == 1 and sleeps == [] and notes == []
    assert "tras" not in str(info.value)


def test_jitter_entre_la_mitad_y_el_total_y_tope():
    policy = RetryPolicy(base_delay=1.0, max_delay=8.0, rng=lambda: 0.0)
    assert [policy.delay(n, None) for n in range(6)] == [0.5, 1.0, 2.0, 4.0, 4.0, 4.0]
    policy = RetryPolicy(base_delay=1.0, max_delay=8.0, rng=lambda: 1.0)
    assert [policy.delay(n, None) for n in range(6)] == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_respeta_retry_after(monkeypatch):
    _script(monkeypatch, [_http_error(429, "7"), _Ok()])
    policy, sleeps, _notes = _policy()
    post_json("https://x.test", {}, {}, retry=policy)
    assert sleeps == [7.0]  # mayor que los 1,0 s del exponencial


def test_retry_after_menor_que_el_exponencial_no_acorta_la_espera():
    policy, _s, _n = _policy()
    assert policy.delay(2, 0.5) == 4.0


def test_retry_after_excesivo_no_se_espera(monkeypatch):
    calls = _script(monkeypatch, [_http_error(429, "3600"), _Ok()])
    policy, sleeps, _notes = _policy()
    with pytest.raises(ProviderError, match="3600 s: no se reintenta"):
        post_json("https://x.test", {}, {}, retry=policy)
    assert len(calls) == 1 and sleeps == []


def test_parse_retry_after():
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("mañana") is None
    assert parse_retry_after("-4") == 0.0
    assert parse_retry_after("nan") is None
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    assert 20 < parse_retry_after(future) <= 30
    past = format_datetime(datetime.now(UTC) - timedelta(seconds=30), usegmt=True)
    assert parse_retry_after(past) == 0.0
    assert parse_retry_after("Wed, 21 Oct 2099 07:28:00") > 1e6  # sin zona horaria -> UTC


@pytest.mark.parametrize(
    "failure",
    [
        http.client.RemoteDisconnected("cerrada"),
        ConnectionResetError(10054, "reset"),
        urllib.error.URLError(ConnectionResetError(104, "reset")),
        http.client.IncompleteRead(b""),
    ],
)
def test_reintenta_cortes_de_conexion(monkeypatch, failure):
    calls = _script(monkeypatch, [failure, _Ok()])
    policy, sleeps, notes = _policy()
    post_json("https://x.test", {}, {}, retry=policy)
    assert len(calls) == 2 and sleeps == [1.0]
    assert "x.test" in notes[0]


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out"),
        urllib.error.URLError(TimeoutError("timed out")),
        urllib.error.URLError(ConnectionRefusedError(111, "rechazada")),
        urllib.error.URLError("nombre desconocido"),
        OSError("otra cosa"),
    ],
)
def test_no_reintenta_timeouts_ni_servidores_apagados(monkeypatch, failure):
    calls = _script(monkeypatch, [failure, _Ok()])
    policy, sleeps, _notes = _policy()
    with pytest.raises(ProviderError):
        post_json("https://x.test", {}, {}, retry=policy)
    assert len(calls) == 1 and sleeps == []


def test_reintentos_no_filtran_la_clave(monkeypatch):
    def secret_error():
        body = json.dumps({"error": {"message": "clave sk-secreta"}}).encode()
        return urllib.error.HTTPError(
            "https://x.test", 503, "Error", email.message.Message(), io.BytesIO(body)
        )

    _script(monkeypatch, [secret_error(), secret_error()])
    policy, _sleeps, notes = _policy(retries=1)
    with pytest.raises(ProviderError) as info:
        post_json("https://x.test", {}, {}, secrets=("sk-secreta",), retry=policy)
    assert "sk-secreta" not in str(info.value)
    assert all("sk-secreta" not in n for n in notes)


def test_la_latencia_solo_cuenta_el_intento_bueno(monkeypatch):
    _script(monkeypatch, [_http_error(500), _Ok()])
    policy, _s, _n = _policy()
    _data, latency = post_json("https://x.test", {}, {}, retry=policy)
    assert latency < 1.0  # la espera simulada no se mide


def test_proveedores_reciben_reintentos_y_avisan(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "clave-falsa")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)
    notes: list[str] = []
    provider = get_provider("openai:m", retries=2, on_retry=notes.append)
    assert isinstance(provider, OpenAIProvider) and provider.retry.retries == 2
    provider.retry.sleep = lambda _s: None
    _script(monkeypatch, [_http_error(429), _http_error(502), _Ok()])
    assert provider.complete("p").text == "hola"
    assert len(notes) == 2 and all(n.startswith("openai:m: reintento") for n in notes)

    gemini = get_provider("gemini:g", retries=0)
    assert isinstance(gemini, GeminiProvider) and gemini.retry.retries == 0
    gemini.retry.notify("sin destino")  # sin callback no falla
    assert GeminiProvider("g").retry.retries == 3  # valor por defecto


def test_cli_retries_por_defecto_y_validacion(monkeypatch, capsys, examples_dir, tmp_path):
    seen = {}

    def fake_get(spec, replay_dirs=None, retries=3, on_retry=None):
        seen[spec] = retries
        on_retry("aviso de prueba")
        return get_provider(spec, replay_dirs)

    monkeypatch.setattr("modelduel.cli.get_provider", fake_get)
    base_args = [
        "run",
        str(examples_dir / "tasks" / "slugify"),
        "--a",
        "replay:alfa",
        "--b",
        "replay:beta",
        "--out",
        str(tmp_path / "out"),
    ]
    assert main([*base_args, "--retries", "5"]) == 0
    assert seen == {"replay:alfa": 5, "replay:beta": 5}
    assert "~~  aviso de prueba" in capsys.readouterr().out
    assert main(base_args) == 0
    assert seen["replay:alfa"] == 3
    assert main([*base_args, "--retries", "-1"]) == 2
    assert "--retries" in capsys.readouterr().err
