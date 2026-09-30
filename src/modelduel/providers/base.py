"""Interfaz común de los proveedores y utilidades HTTP con ``urllib``."""

from __future__ import annotations

import http.client
import json
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

DEFAULT_HTTP_TIMEOUT = 180.0
USER_AGENT = "modelduel (+https://github.com/BertMarti/modelduel)"


class ProviderError(Exception):
    """Error de un proveedor (configuración, red o respuesta inesperada)."""


@dataclass
class Response:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_s: float


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
    url: str, payload: dict, headers: dict[str, str], secrets: tuple[str, ...] = ()
) -> tuple[dict, float]:
    """POST JSON y devuelve ``(respuesta, latencia_s)``. Nunca incluye secretos en los errores.

    Cualquier fallo de red o de protocolo se convierte en ``ProviderError`` para que el duelo
    lo registre como «error del proveedor» y siga con el resto de intentos.
    """
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
        raise ProviderError(redact(f"HTTP {exc.code} en {url}{hint}: {detail}", secrets)) from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise ProviderError(f"La petición a {url} superó {timeout:g} s.") from None
        raise ProviderError(
            redact(f"No se pudo conectar con {url}: {exc.reason}", secrets)
        ) from None
    except TimeoutError:
        raise ProviderError(f"La petición a {url} superó {timeout:g} s.") from None
    except (OSError, http.client.HTTPException) as exc:
        # p. ej. RemoteDisconnected, ConnectionResetError o IncompleteRead al leer la respuesta.
        name = type(exc).__name__
        raise ProviderError(redact(f"Se cortó la conexión con {url} ({name}).", secrets)) from None
    latency = time.perf_counter() - start
    try:
        return json.loads(raw.decode("utf-8")), latency
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Respuesta no JSON de {url}: {exc}") from None


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
