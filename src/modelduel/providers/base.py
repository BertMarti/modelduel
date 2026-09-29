"""Interfaz común de los proveedores y utilidades HTTP con ``urllib``."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

HTTP_TIMEOUT = float(os.environ.get("MODELDUEL_HTTP_TIMEOUT", "180"))
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


def post_json(
    url: str, payload: dict, headers: dict[str, str], secrets: tuple[str, ...] = ()
) -> tuple[dict, float]:
    """POST JSON y devuelve ``(respuesta, latencia_s)``. Nunca incluye secretos en los errores."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers},
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ProviderError(redact(f"HTTP {exc.code} en {url}: {detail}", secrets)) from None
    except urllib.error.URLError as exc:
        raise ProviderError(
            redact(f"No se pudo conectar con {url}: {exc.reason}", secrets)
        ) from None
    except TimeoutError:
        raise ProviderError(f"La petición a {url} superó {HTTP_TIMEOUT:g} s.") from None
    latency = time.perf_counter() - start
    try:
        return json.loads(raw.decode("utf-8")), latency
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Respuesta no JSON de {url}: {exc}") from None


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
