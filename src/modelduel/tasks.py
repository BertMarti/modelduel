"""Carga de tareas: una carpeta con ``task.md``, el archivo de tests y ``meta.toml`` opcional.

El lenguaje de la tarea decide el archivo de tests y el de la solución:

* Python (por defecto): ``test_task.py`` (pytest) y ``solution.py``.
* JavaScript (experimental): ``test_task.mjs`` (``node:test``) y ``solution.mjs``.
* TypeScript (experimental): ``test_task.ts`` (``node:test``, Node >= 22.6) y ``solution.ts``.

Se declara con ``language = "javascript"`` en ``meta.toml``; si no se declara, se deduce del único
archivo de tests que haya.
"""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TASK_FILE = "task.md"
TEST_FILE = "test_task.py"
META_FILE = "meta.toml"


class TaskError(Exception):
    """Error al cargar una tarea."""


@dataclass(frozen=True)
class Language:
    """Lo que cambia de un lenguaje a otro al preparar y ejecutar una tarea."""

    name: str  # python | javascript | typescript (lo que va en meta.toml y en results.json)
    label: str  # para la interfaz
    test_file: str
    solution_file: str
    fence: str  # etiqueta del bloque de código que se pide al modelo
    node: bool = False  # sus tests se ejecutan con Node (node:test) y no con pytest


LANGUAGES: dict[str, Language] = {
    "python": Language("python", "Python", TEST_FILE, "solution.py", "python"),
    "javascript": Language(
        "javascript", "JavaScript", "test_task.mjs", "solution.mjs", "javascript", node=True
    ),
    "typescript": Language(
        "typescript", "TypeScript", "test_task.ts", "solution.ts", "typescript", node=True
    ),
}
LANGUAGE_ALIASES = {"py": "python", "js": "javascript", "ts": "typescript"}
TEST_FILES = tuple(lang.test_file for lang in LANGUAGES.values())


def language_of(name: str | None) -> Language:
    """``Language`` de un nombre de ``results.json`` o de ``meta.toml`` (``None`` = Python)."""
    key = str(name or "python").strip().lower()
    return LANGUAGES.get(LANGUAGE_ALIASES.get(key, key), LANGUAGES["python"])


@dataclass
class Task:
    id: str
    path: Path
    statement: str
    title: str
    difficulty: str = ""
    order: int = 1000
    meta: dict = field(default_factory=dict)
    language: str = "python"

    @property
    def lang(self) -> Language:
        return LANGUAGES[self.language]

    @property
    def test_path(self) -> Path:
        return self.path / self.lang.test_file

    @property
    def expected_tests(self) -> int:
        source = read_text(self.test_path)
        return count_node_tests(source) if self.lang.node else count_tests(source)


def read_text(path: Path) -> str:
    """Lee UTF-8 aceptando el BOM que añaden algunos editores de Windows."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TaskError(f"{path} no está en UTF-8: {exc.reason}.") from exc


def is_task_dir(path: Path) -> bool:
    return (path / TASK_FILE).is_file() and any((path / name).is_file() for name in TEST_FILES)


def _task_language(path: Path, meta: dict, meta_path: Path) -> Language:
    """Lenguaje declarado en ``meta.toml`` o, si no lo hay, el del único archivo de tests."""
    declared = meta.get("language")
    found = [lang for lang in LANGUAGES.values() if (path / lang.test_file).is_file()]
    if declared is not None:
        key = str(declared).strip().lower()
        key = LANGUAGE_ALIASES.get(key, key)
        if not isinstance(declared, str) or key not in LANGUAGES:
            raise TaskError(
                f"{meta_path}: «language» debe ser uno de: {', '.join(LANGUAGES)} "
                f"(tiene «{declared}»)."
            )
        lang = LANGUAGES[key]
        if lang not in found:
            raise TaskError(
                f'{path} declara language = "{lang.name}" pero no tiene {lang.test_file}.'
            )
        return lang
    if len(found) > 1:
        names = " y ".join(lang.test_file for lang in found)
        raise TaskError(
            f'{path} tiene {names}: declara cuál vale con language = "…" en {META_FILE}.'
        )
    return found[0]


def load_task(path: Path) -> Task:
    path = Path(path)
    if not is_task_dir(path):
        raise TaskError(
            f"{path} no es una tarea: necesita {TASK_FILE} y un archivo de tests "
            f"({' o '.join(TEST_FILES)})."
        )
    statement = read_text(path / TASK_FILE).strip()
    meta: dict = {}
    meta_path = path / META_FILE
    if meta_path.is_file():
        try:
            meta = tomllib.loads(read_text(meta_path))
        except tomllib.TOMLDecodeError as exc:
            raise TaskError(f"{meta_path} no es TOML válido: {exc}") from exc
    lang = _task_language(path, meta, meta_path)
    test_path = path / lang.test_file
    source = read_text(test_path)
    if not lang.node:
        try:
            ast.parse(source)
        except SyntaxError as exc:
            # Mejor avisar ahora que atribuir el fallo a los modelos como «no se pudo importar».
            raise TaskError(
                f"{test_path} tiene un error de sintaxis en la línea {exc.lineno}: {exc.msg}."
            ) from exc
    elif count_node_tests(source) == 0:
        raise TaskError(
            f"{test_path} no tiene ninguna llamada test(…) de primer nivel (node:test)."
        )
    title = str(meta.get("title") or _title_from_statement(statement) or path.name)
    return Task(
        id=path.name,
        path=path,
        statement=statement,
        title=title,
        difficulty=str(meta.get("difficulty", "")),
        order=int(meta.get("order", 1000)),
        meta=meta,
        language=lang.name,
    )


def discover_tasks(path: Path) -> list[Task]:
    """Devuelve la tarea de ``path`` o todas las tareas de sus subcarpetas, ordenadas."""
    path = Path(path)
    try:
        return _discover(path)
    except PermissionError as exc:
        where = exc.filename or path
        raise TaskError(
            f"No se puede leer {where}: permiso denegado. Revisa sus permisos "
            "(por ejemplo con `ls -l`) o elige otra carpeta de tareas."
        ) from None


def _discover(path: Path) -> list[Task]:
    if not path.exists():
        raise TaskError(f"No existe la ruta {path}.")
    if is_task_dir(path):
        return [load_task(path)]
    if not path.is_dir():
        raise TaskError(f"{path} no es una carpeta de tareas.")
    tasks = [load_task(child) for child in sorted(path.iterdir()) if is_task_dir(child)]
    if not tasks:
        raise TaskError(
            f"No hay tareas en {path}. Una tarea es una carpeta con task.md y test_task.py "
            "(o test_task.mjs / test_task.ts para JavaScript / TypeScript); crea ejemplos con "
            "`modelduel init`."
        )
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


# Una llamada ``test(…)`` / ``it(…)`` (también ``.skip``/``.todo``/``.only``) al principio de línea.
_NODE_TEST_RE = re.compile(r"^[ \t]*(?:test|it)(?:\.(?:skip|todo|only))?[ \t]*\(", re.MULTILINE)
_JS_COMMENT_RE = re.compile(r"/\*.*?\*/|^[ \t]*//[^\n]*", re.DOTALL | re.MULTILINE)


def count_node_tests(source: str) -> int:
    """Cuenta los tests de un archivo ``node:test`` sin ejecutarlo.

    Es una estimación (solo se usa si no hay resultados reales): una por cada llamada ``test(``
    o ``it(`` que empiece una línea, sin contar las comentadas ni los subtests ``t.test(``.
    """
    return len(_NODE_TEST_RE.findall(_JS_COMMENT_RE.sub("", source)))
