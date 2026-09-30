"""Ejemplos incluidos en el paquete: ``modelduel demo`` funciona nada más instalarlo."""

from __future__ import annotations

from pathlib import Path

from modelduel.tasks import TaskError

# Contendientes ficticios con respuestas grabadas: sin claves y sin coste.
DEMO_MODELS = ("replay:alfa", "replay:beta", "replay:gamma")


def examples_dir() -> Path:
    """Carpeta con ``tasks/`` y ``replays/``.

    Instalado desde PyPI están dentro del paquete (``modelduel/examples``); en un clon del
    repositorio (también con ``pip install -e .``) están en ``examples/`` junto a ``src/``.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here / "examples", here.parents[1] / "examples"):
        if (candidate / "tasks").is_dir() and (candidate / "replays").is_dir():
            return candidate
    raise TaskError(
        "no encuentro los ejemplos de modelduel. Reinstálalo o clona "
        "https://github.com/BertMarti/modelduel."
    )
