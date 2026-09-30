"""Carga de tareas: una carpeta con ``task.md``, ``test_task.py`` y ``meta.toml`` opcional."""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TASK_FILE = "task.md"
TEST_FILE = "test_task.py"
META_FILE = "meta.toml"


class TaskError(Exception):
    """Error al cargar una tarea."""


@dataclass
class Task:
    id: str
    path: Path
    statement: str
    title: str
    difficulty: str = ""
    order: int = 1000
    meta: dict = field(default_factory=dict)

    @property
    def test_path(self) -> Path:
        return self.path / TEST_FILE

    @property
    def expected_tests(self) -> int:
        return count_tests(self.test_path.read_text(encoding="utf-8"))


def is_task_dir(path: Path) -> bool:
    return (path / TASK_FILE).is_file() and (path / TEST_FILE).is_file()


def load_task(path: Path) -> Task:
    path = Path(path)
    if not is_task_dir(path):
        raise TaskError(f"{path} no es una tarea: necesita {TASK_FILE} y {TEST_FILE}.")
    statement = (path / TASK_FILE).read_text(encoding="utf-8").strip()
    meta: dict = {}
    meta_path = path / META_FILE
    if meta_path.is_file():
        try:
            meta = tomllib.loads(meta_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise TaskError(f"{meta_path} no es TOML válido: {exc}") from exc
    title = str(meta.get("title") or _title_from_statement(statement) or path.name)
    return Task(
        id=path.name,
        path=path,
        statement=statement,
        title=title,
        difficulty=str(meta.get("difficulty", "")),
        order=int(meta.get("order", 1000)),
        meta=meta,
    )


def discover_tasks(path: Path) -> list[Task]:
    """Devuelve la tarea de ``path`` o todas las tareas de sus subcarpetas, ordenadas."""
    path = Path(path)
    if not path.exists():
        raise TaskError(f"No existe la ruta {path}.")
    if is_task_dir(path):
        return [load_task(path)]
    tasks = [load_task(child) for child in sorted(path.iterdir()) if is_task_dir(child)]
    if not tasks:
        raise TaskError(f"No hay tareas en {path}.")
    return sorted(tasks, key=lambda t: (t.order, t.id))


def _title_from_statement(statement: str) -> str:
    for line in statement.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def count_tests(source: str) -> int:
    """Cuenta los tests de un archivo pytest sin ejecutarlo (incluye ``parametrize`` literal)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    def weight(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        total = 1
        for deco in func.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "parametrize"
                and len(deco.args) >= 2
                and isinstance(deco.args[1], ast.List | ast.Tuple)
            ):
                total *= max(len(deco.args[1].elts), 1)
        return total

    count = 0
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            count += weight(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    item.name.startswith("test")
                ):
                    count += weight(item)
    return count
