from __future__ import annotations

from pathlib import Path

import pytest

from modelduel.tasks import Task, load_task

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def make_task(tmp_path: Path):
    """Crea una tarea mínima en ``tmp_path`` con los tests indicados."""

    def _make(
        tests: str,
        name: str = "demo",
        statement: str = "# Demo\n\nEscribe `def add(a, b)`.",
        meta: str | None = None,
    ) -> Task:
        folder = tmp_path / "tasks" / name
        folder.mkdir(parents=True)
        (folder / "task.md").write_text(statement, encoding="utf-8")
        (folder / "test_task.py").write_text(tests, encoding="utf-8")
        if meta is not None:
            (folder / "meta.toml").write_text(meta, encoding="utf-8")
        return load_task(folder)

    return _make


ADD_TESTS = """\
from solution import add


def test_positivos():
    assert add(2, 3) == 5


def test_negativos():
    assert add(-2, -3) == -5


def test_cero():
    assert add(0, 0) == 0
"""


@pytest.fixture(autouse=True)
def _sin_esperas_reales_en_reintentos(monkeypatch):
    """Ningún test debe esperar de verdad entre reintentos: hay que inyectar ``sleep``."""
    from modelduel.providers import base

    def boom(seconds: float) -> None:
        raise AssertionError(f"un test intentó esperar {seconds} s de verdad en un reintento")

    monkeypatch.setattr(base, "_real_sleep", boom)
