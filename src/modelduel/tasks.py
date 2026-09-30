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
        return count_tests(read_text(self.test_path))


def read_text(path: Path) -> str:
    """Lee UTF-8 aceptando el BOM que añaden algunos editores de Windows."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TaskError(f"{path} no está en UTF-8: {exc.reason}.") from exc


def is_task_dir(path: Path) -> bool:
    return (path / TASK_FILE).is_file() and (path / TEST_FILE).is_file()


def load_task(path: Path) -> Task:
    path = Path(path)
    if not is_task_dir(path):
        raise TaskError(f"{path} no es una tarea: necesita {TASK_FILE} y {TEST_FILE}.")
    statement = read_text(path / TASK_FILE).strip()
    test_path = path / TEST_FILE
    try:
        ast.parse(read_text(test_path))
    except SyntaxError as exc:
        # Mejor avisar ahora que atribuir el fallo a los modelos como «no se pudo importar».
        raise TaskError(
            f"{test_path} tiene un error de sintaxis en la línea {exc.lineno}: {exc.msg}."
        ) from exc
    meta: dict = {}
    meta_path = path / META_FILE
    if meta_path.is_file():
        try:
            meta = tomllib.loads(read_text(meta_path))
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
    if not path.is_dir():
        raise TaskError(f"{path} no es una carpeta de tareas.")
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

    # Constantes de módulo (``CASOS = [...]``) usadas en ``parametrize``.
    constants: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List | ast.Tuple):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = len(node.value.elts)

    def n_values(node: ast.expr | None) -> int | None:
        if isinstance(node, ast.List | ast.Tuple):
            return len(node.elts)
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    def weight(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        total = 1
        for deco in func.decorator_list:
            if not (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "parametrize"
            ):
                continue
            values = deco.args[1] if len(deco.args) >= 2 else None
            for kw in deco.keywords:
                if kw.arg == "argvalues":
                    values = kw.value
            n = n_values(values)
            if n is not None:
                total *= max(n, 1)
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
