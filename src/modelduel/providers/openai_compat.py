"""Proveedor ``openai:<modelo>``: cualquier API compatible con Chat Completions de OpenAI.

Sirve para OpenAI, OpenRouter, Ollama y similares cambiando ``OPENAI_BASE_URL``.
``omniroute:<modelo>`` es el mismo proveedor con otro prefijo, otras variables y otra URL.
"""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Callable

from modelduel.providers.base import (
    DEFAULT_RETRIES,
    ConnectionFailed,
    ProviderError,
    Response,
    RetryPolicy,
    as_int,
    post_json,
)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class OpenAIProvider:
    # Preset: OmniRouteProvider solo cambia estos valores.
    PREFIX = "openai"
    BASE_URL_ENV = "OPENAI_BASE_URL"
    KEY_ENV = "OPENAI_API_KEY"
    DEFAULT_BASE_URL = DEFAULT_BASE_URL
    KEY_REQUIRED = True  # salvo que la URL sea local (Ollama)
    DOWN_HINT = ""

    def __init__(
        self,
        model: str,
        retries: int = DEFAULT_RETRIES,
        on_retry: Callable[[str], None] | None = None,
    ) -> None:
        if not model:
            raise ProviderError(f"{self.PREFIX} necesita un modelo: {self.PREFIX}:<modelo>.")
        self.model = model
        self._on_retry = on_retry
        self.retry = RetryPolicy(retries=retries, notify=self._notify)
        self.spec = f"{self.PREFIX}:{model}"
        self.base_url = (os.environ.get(self.BASE_URL_ENV) or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_key = os.environ.get(self.KEY_ENV, "").strip()
        host = urllib.parse.urlparse(self.base_url).hostname or ""
        if self.KEY_REQUIRED and not self.api_key and host not in _LOCAL_HOSTS:
            raise ProviderError(
                f"Falta la variable de entorno {self.KEY_ENV} "
                f"(necesaria para {self.base_url}; los servidores locales como Ollama no la piden)."
            )

    def _notify(self, message: str) -> None:
        if self._on_retry:
            self._on_retry(f"{self.spec}: {message}")

    def complete(self, prompt: str, *, task_id: str | None = None) -> Response:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        try:
            data, latency = post_json(
                f"{self.base_url}/chat/completions",
                payload,
                headers,
                secrets=(self.api_key,),
                retry=self.retry,
            )
        except ConnectionFailed as exc:
            if not self.DOWN_HINT:
                raise
            raise ConnectionFailed(f"{exc} {self.DOWN_HINT}") from None
        return parse_openai_response(data, latency)


class OmniRouteProvider(OpenAIProvider):
    """``omniroute:<modelo>``: OmniRoute, un router local compatible con OpenAI."""

    PREFIX = "omniroute"
    BASE_URL_ENV = "OMNIROUTE_BASE_URL"
    KEY_ENV = "OMNIROUTE_API_KEY"
    DEFAULT_BASE_URL = "http://localhost:20128/v1"
    KEY_REQUIRED = False
    DOWN_HINT = (
        "¿Está en marcha? Arranca OmniRoute con `omniroute serve` (o fija OMNIROUTE_BASE_URL)."
    )


def parse_openai_response(data: object, latency: float) -> Response:
    if not isinstance(data, dict):
        raise ProviderError("La API devolvió una respuesta con un formato inesperado.")
    choices = data.get("choices") or []
    if not choices:
        error = data.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or "sin opciones"
        else:
            detail = error if isinstance(error, str) and error.strip() else "sin opciones"
        raise ProviderError(f"La API no devolvió respuesta ({detail}).")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ProviderError("La API devolvió una opción con un formato inesperado.")
    message = choice.get("message")
    message = message if isinstance(message, dict) else {}
    content = message.get("content") or ""
    if isinstance(content, list):  # algunos servidores devuelven partes
        content = "".join(str(p.get("text") or "") for p in content if isinstance(p, dict))
    if not isinstance(content, str):
        content = ""
    if not content.strip():
        if message.get("refusal"):
            raise ProviderError(f"El modelo rechazó la petición: {message['refusal']}")
        reason = choice.get("finish_reason") or "sin texto"
        raise ProviderError(f"La API no devolvió texto (finish_reason: {reason}).")
    usage = data.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return Response(
        text=content,
        input_tokens=as_int(usage.get("prompt_tokens")),
        output_tokens=as_int(usage.get("completion_tokens")),
        latency_s=latency,
    )
