"""Proveedor ``replay``: respuestas grabadas en ``<replays>/<nombre>/<tarea>.md``.

Cada archivo puede empezar con un front-matter sencillo::

    ---
    input_tokens: 312
    output_tokens: 188
    latency_s: 2.41
    ---
    Texto de la respuesta del modelo...
"""

from __future__ import annotations

from pathlib import Path

from modelduel.providers.base import ProviderError, Response, as_int


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    text = text.replace("\r\n", "\n").lstrip("﻿")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() and not key.strip().startswith("#"):
            meta[key.strip()] = value.strip()
    body = text[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


class ReplayProvider:
    def __init__(self, name: str, search_dirs: list[Path] | None = None) -> None:
        if not name:
            raise ProviderError("replay necesita un nombre: replay:<nombre>.")
        self.name = name
        self.spec = f"replay:{name}"
        self.directory = self._resolve(name, search_dirs or [Path("examples/replays")])

    @staticmethod
    def _resolve(name: str, search_dirs: list[Path]) -> Path:
        direct = Path(name)
        if direct.is_dir():
            return direct
        for base in search_dirs:
            candidate = Path(base) / name
            if candidate.is_dir():
                return candidate
        places = ", ".join(str(Path(b) / name) for b in search_dirs)
        raise ProviderError(
            f"No encuentro las respuestas grabadas de «{name}» (busqué en {places})."
        )

    def complete(self, prompt: str, *, task_id: str | None = None) -> Response:
        if not task_id:
            raise ProviderError("replay necesita saber la tarea para leer su respuesta grabada.")
        path = self.directory / f"{task_id}.md"
        if not path.is_file():
            raise ProviderError(f"No hay respuesta grabada para la tarea «{task_id}» en {path}.")
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        try:
            latency = float(meta.get("latency_s", "0").replace(",", "."))
        except ValueError:
            latency = 0.0
        return Response(
            text=body,
            input_tokens=as_int(meta.get("input_tokens")),
            output_tokens=as_int(meta.get("output_tokens")),
            latency_s=latency,
        )
