"""Interfaz común de los proveedores y utilidades HTTP con ``urllib``."""

from __future__ import annotations

import http.client
import json
import math
import os
import random
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

from modelduel.report.html import fmt_seconds

DEFAULT_HTTP_TIMEOUT = 180.0
DEFAULT_RETRIES = 3
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "modelduel (+https://github.com/BertMarti/modelduel)"


def _real_sleep(seconds: float) -> None:
    """Espera de verdad; los tests la sustituyen para no esperar nunca."""
    time.sleep(seconds)


class ProviderError(Exception):
    """Error de un proveedor (configuración, red o respuesta inesperada)."""


@dataclass
class Response:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_s: float


@dataclass
class RetryPolicy:
    """Reintentos con espera exponencial y jitter ante errores pasajeros.

    ``sleep`` y ``rng`` son inyectables para que los tests sean deterministas y no esperen.
    """

    retries: int = DEFAULT_RETRIES
    base_delay: float = 1.0
    max_delay: float = 30.0
    max_retry_after: float = 120.0  # si el servidor pide esperar más, no se espera: se rinde
    notify: Callable[[str], None] | None = None
    sleep: Callable[[float], None] = field(default=lambda s: _real_sleep(s), repr=False)
    rng: Callable[[], float] = field(default=random.random, repr=False)

    def delay(self, attempt: int, retry_after: float | None) -> float:
        """Espera antes del reintento número ``attempt + 1`` (``attempt`` empieza en 0).

        Sin ``Retry-After``: ``base × 2^attempt`` acotado por ``max_delay`` y con jitter entre el
        50 % y el 100 %. Con ``Retry-After`` se espera como mínimo eso.
        """
        exponential = min(self.max_delay, self.base_delay * 2 ** min(attempt, 62))  # sin desbordar
        jittered = exponential * (0.5 + 0.5 * self.rng())
        return max(jittered, retry_after) if retry_after is not None else jittered


class TransientError(ProviderError):
    """Error pasajero (429, 5xx, corte de conexión): merece la pena reintentar."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class Provider(Protocol):
    spec: str

    def complete(self, prompt: str, *, task_id: str | None = None) -> Response:
        """Envía ``prompt`` al modelo. ``task_id`` solo lo usan los proveedores grabados."""
        ...


def require_env(name: str, hint: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProviderError(f"Falta la variable de entorno {name}. {hint}")
    return value


def http_timeout() -> float:
    """Límite de las peticiones HTTP (``MODELDUEL_HTTP_TIMEOUT``), validado al usarlo."""
    raw = os.environ.get("MODELDUEL_HTTP_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_HTTP_TIMEOUT
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        raise ProviderError(
            f"MODELDUEL_HTTP_TIMEOUT debe ser un número de segundos mayor que 0 (vale «{raw}»)."
        )
    return value


_HTTP_HINTS = {
    400: "petición rechazada: revisa el nombre del modelo",
    401: "revisa la clave de la API",
    403: "revisa la clave y los permisos de la API",
    404: "¿existe el modelo y es correcta la URL base?",
    429: "límite de peticiones o cuota agotada: espera o revisa tu plan",
}


def post_json(
    url: str,
    payload: dict,
    headers: dict[str, str],
    secrets: tuple[str, ...] = (),
    retry: RetryPolicy | None = None,
) -> tuple[dict, float]:
    """POST JSON y devuelve ``(respuesta, latencia_s)``. Nunca incluye secretos en los errores.

    Cualquier fallo de red o de protocolo se convierte en ``ProviderError`` para que el duelo
    lo registre como «error del proveedor» y siga con el resto de intentos. Con ``retry`` se
    reintentan los errores pasajeros (HTTP 429/500/502/503/504 y cortes de conexión).
    """
    retry = retry or RetryPolicy(retries=0)
    attempt = 0
    while True:
        try:
            return _post_once(url, payload, headers, secrets)
        except TransientError as exc:
            if attempt >= retry.retries:
                suffix = f" (tras {plural_retries(attempt)})" if attempt else ""
                raise ProviderError(f"{exc}{suffix}") from None
            if exc.retry_after is not None and exc.retry_after > retry.max_retry_after:
                asked = (
                    "un tiempo excesivo"
                    if math.isinf(exc.retry_after)
                    else f"{exc.retry_after:g} s"
                )
                raise ProviderError(
                    f"{exc} (el servidor pide esperar {asked}: no se reintenta)"
                ) from None
            wait = retry.delay(attempt, exc.retry_after)
            attempt += 1
            if retry.notify:
                retry.notify(f"reintento {attempt}/{retry.retries} en {fmt_seconds(wait)}: {exc}")
            retry.sleep(wait)


def plural_retries(n: int) -> str:
    return "1 reintento" if n == 1 else f"{n} reintentos"


_SECONDS = re.compile(r"\+?\d+(?:\.\d+)?", re.ASCII)


def parse_retry_after(value: str | None) -> float | None:
    """``Retry-After`` en segundos o como fecha HTTP; ``None`` si falta o no se entiende.

    Un valor absurdo (cientos de dígitos) devuelve ``inf``: «espera una eternidad» no
    es lo mismo que «no he dicho nada», y quien llama se rinde en vez de reintentar ya.
    """
    if not value:
        return None
    value = value.strip()
    if _SECONDS.fullmatch(value):
        return float(value)  # un literal enorme da inf
    if re.fullmatch(r"-\d+(?:\.\d+)?", value, re.ASCII):
        return 0.0  # negativo: no hay que esperar más de lo habitual
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    try:
        return max(0.0, (when - datetime.now(UTC)).total_seconds())
    except OverflowError:
        return math.inf


def _post_once(
    url: str, payload: dict, headers: dict[str, str], secrets: tuple[str, ...]
) -> tuple[dict, float]:
    timeout = http_timeout()
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers},
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = error_detail(exc)
        hint = _HTTP_HINTS.get(exc.code) or ("error del servidor" if exc.code >= 500 else "")
        hint = f" ({hint})" if hint else ""
        message = redact(f"HTTP {exc.code} en {url}{hint}: {detail}", secrets)
        if exc.code in RETRY_STATUS:
            retry_after = parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
            raise TransientError(message, retry_after) from None
        raise ProviderError(message) from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise ProviderError(f"La petición a {url} superó {timeout:g} s.") from None
        message = redact(f"No se pudo conectar con {url}: {exc.reason}", secrets)
        if _is_connection_cut(exc.reason):
            raise TransientError(message) from None
        raise ProviderError(message) from None
    except TimeoutError:
        raise ProviderError(f"La petición a {url} superó {timeout:g} s.") from None
    except (OSError, http.client.HTTPException) as exc:
        # p. ej. RemoteDisconnected, ConnectionResetError o IncompleteRead al leer la respuesta.
        name = type(exc).__name__
        message = redact(f"Se cortó la conexión con {url} ({name}).", secrets)
        if _is_connection_cut(exc):
            raise TransientError(message) from None
        raise ProviderError(message) from None
    latency = time.perf_counter() - start
    try:
        return json.loads(raw.decode("utf-8")), latency
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Respuesta no JSON de {url}: {exc}") from None


def _is_connection_cut(reason: object) -> bool:
    """Corte de una conexión ya abierta (reintentable); un servidor apagado no lo es."""
    if isinstance(reason, ConnectionRefusedError):
        return False
    return isinstance(reason, ConnectionError | http.client.HTTPException)


def error_detail(exc: urllib.error.HTTPError, limit: int = 300) -> str:
    """Mensaje legible de un error HTTP: el ``error.message`` del JSON si lo hay."""
    try:
        text = exc.read().decode("utf-8", errors="replace")
    except (OSError, http.client.HTTPException):
        return str(exc.reason or "sin detalle")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list) and data:  # Gemini a veces envuelve el error en una lista
        data = data[0]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, str) and error.strip():
        return error.strip()[:limit]
    if isinstance(error, dict) and error.get("message"):
        status = error.get("status") or error.get("type") or error.get("code")
        message = str(error["message"]).strip()
        return (f"{status}: {message}" if status else message)[:limit]
    return " ".join(text.split())[:limit] or str(exc.reason or "sin detalle")


def redact(message: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message


def as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
