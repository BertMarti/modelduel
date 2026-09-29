"""Proveedor ``openai:<modelo>``: cualquier API compatible con Chat Completions de OpenAI.

Sirve para OpenAI, OpenRouter, Ollama y similares cambiando ``OPENAI_BASE_URL``.
"""

from __future__ import annotations

import os
import urllib.parse

from modelduel.providers.base import ProviderError, Response, as_int, post_json

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class OpenAIProvider:
    def __init__(self, model: str) -> None:
        if not model:
            raise ProviderError("openai necesita un modelo: openai:<modelo>.")
        self.model = model
        self.spec = f"openai:{model}"
        self.base_url = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        host = urllib.parse.urlparse(self.base_url).hostname or ""
        if not self.api_key and host not in _LOCAL_HOSTS:
            raise ProviderError(
                "Falta la variable de entorno OPENAI_API_KEY "
                f"(necesaria para {self.base_url}; los servidores locales como Ollama no la piden)."
            )

    def complete(self, prompt: str, *, task_id: str | None = None) -> Response:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        data, latency = post_json(
            f"{self.base_url}/chat/completions", payload, headers, secrets=(self.api_key,)
        )
        return parse_openai_response(data, latency)


def parse_openai_response(data: dict, latency: float) -> Response:
    choices = data.get("choices") or []
    if not choices:
        error = data.get("error")
        detail = error.get("message") if isinstance(error, dict) else "sin opciones"
        raise ProviderError(f"La API no devolvió respuesta ({detail}).")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):  # algunos servidores devuelven partes
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    usage = data.get("usage") or {}
    return Response(
        text=content,
        input_tokens=as_int(usage.get("prompt_tokens")),
        output_tokens=as_int(usage.get("completion_tokens")),
        latency_s=latency,
    )
