"""Extracción del bloque de código Python de la respuesta de un modelo."""

from __future__ import annotations

import re
import textwrap

_FENCE_RE = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<lang>[\w+#.-]*)[^\n]*\n"
    r"(?P<body>.*?)"
    r"(?:^[ \t]*(?P=fence)[`~]*[ \t]*$|\Z)",
    re.DOTALL | re.MULTILINE,
)

PYTHON_LANGS = {"python", "py", "python3", "py3"}


def find_code_blocks(text: str) -> list[tuple[str, str]]:
    """Devuelve ``(lenguaje, código)`` de cada bloque delimitado por ``` o ~~~."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    for match in _FENCE_RE.finditer(text):
        body = match.group("body")
        if body.endswith("\n"):
            body = body[:-1]
        # Un bloque dentro de una lista viene sangrado entero: se quita la sangría común.
        blocks.append((match.group("lang").lower(), textwrap.dedent(body)))
    return blocks


def extract_code(text: str) -> str | None:
    """Primer bloque ``python``; si no hay, el único bloque; si no, el primero sin lenguaje.

    Devuelve ``None`` si la respuesta no contiene ningún bloque de código utilizable.
    """
    if not text:
        return None
    blocks = [(lang, body) for lang, body in find_code_blocks(text) if body.strip()]
    code: str | None = None
    for lang, body in blocks:
        if lang in PYTHON_LANGS:
            code = body
            break
    else:
        if len(blocks) == 1:
            code = blocks[0][1]
        else:
            code = next((body for lang, body in blocks if not lang), None)
    if code is None or not code.strip():
        return None
    return code.strip("\n") + "\n"
