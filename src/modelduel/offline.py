"""Modo «solo generar» y reproducción (``run --solo-generar`` y ``run --replay``).

Generar pide el código a los modelos y lo guarda en ``respuestas.json`` (más una copia de las
tareas en ``tareas/``) SIN ejecutar nada; reproducir ejecuta después los tests sobre esas
respuestas, en otra máquina o en un contenedor, sin llamar a ninguna API. ``respuestas.json`` es
un dato no fiable (puede venir de otra máquina): se valida entero antes de usarlo.
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modelduel import __version__
from modelduel.duel import _unexpected, clean_text
from modelduel.providers import ProviderError, Response
from modelduel.results import ALL_SIDES, ResultsError, save_results
from modelduel.resume import task_fingerprint
from modelduel.runner import build_prompt
from modelduel.tasks import Task, TaskError

MAX_RESPONSES_SIZE = 50 * 1024 * 1024
RESPONSES_FILE = "respuestas.json"
RESPONSES_TASKS_DIR = "tareas"
RESPONSES_SCHEMA = 1


class RecordedProvider:
    """Proveedor que devuelve la respuesta grabada de cada (tarea, ejecución)."""

    recorded = True

    def __init__(self, spec: str, attempts: dict[str, list[dict]]) -> None:
        self.spec = spec
        self.attempts = attempts

    def complete(self, prompt: str, *, task_id: str | None = None, run: int = 1) -> Response:
        del prompt
        entries = self.attempts.get(task_id or "", [])
        entry = next((item for item in entries if item.get("run") == run), None)
        if entry is None:
            raise ProviderError(
                f"No hay respuesta grabada para la tarea {task_id or '(desconocida)'} "
                f"(ejecución {run})."
            )
        if "error" in entry:
            raise ProviderError(str(entry["error"]))
        return Response(
            text=str(entry.get("response", "")),
            latency_s=_finite_float(entry.get("latency_s"), 0.0),
            input_tokens=_nonnegative_int(entry.get("input_tokens")),
            output_tokens=_nonnegative_int(entry.get("output_tokens")),
        )


def responses_path(source: Path) -> Path:
    """``CARPETA`` o ``CARPETA/respuestas.json`` -> ruta del archivo."""
    source = Path(source)
    return source / RESPONSES_FILE if source.is_dir() else source


def generate_responses(
    tasks: list[Task],
    providers: dict[str, Any],
    runs: int,
    out: Path,
    progress: Callable[[str], None] = lambda _line: None,
    heartbeat: Callable[[str], AbstractContextManager] | None = None,
) -> Path:
    """Pide las respuestas, las guarda tras cada intento y NO ejecuta código.

    Devuelve la ruta de ``respuestas.json``. Una generación a medias (``in_progress``) no se
    sobrescribe: puede haber costado dinero.
    """
    path = out / RESPONSES_FILE
    copied = out / RESPONSES_TASKS_DIR
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict) and raw.get("status") == "in_progress":
            raise TaskError(
                f"{path} es una generación incompleta (se cortó). Bórrala o elige otra carpeta "
                "--out."
            )
    elif copied.exists():
        raise TaskError(
            f"{copied} ya existe y no es de una generación anterior: elige otra carpeta --out."
        )
    out.mkdir(parents=True, exist_ok=True)
    if copied.exists():
        shutil.rmtree(copied)  # copia de una generación anterior completa en esta carpeta
    copy_tasks(tasks, copied)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    data: dict[str, Any] = {
        "schema": RESPONSES_SCHEMA,
        "tool": "modelduel",
        "kind": "responses",
        "version": __version__,
        "created_at": now,
        "updated_at": now,
        "status": "in_progress",
        "runs": runs,
        "contenders": {side: {"spec": provider.spec} for side, provider in providers.items()},
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "fingerprint": task_fingerprint(task),
                "attempts": {side: [] for side in providers},
            }
            for task in tasks
        ],
    }
    save_results(data, path)
    by_id = {task.id: task for task in tasks}
    for task_data in data["tasks"]:
        task = by_id[task_data["id"]]
        for run in range(1, runs + 1):
            prompt = build_prompt(task)
            for side, provider in providers.items():
                try:
                    label = f"{provider.spec} (tarea {task.id})"
                    live = heartbeat is not None and not provider.spec.startswith("replay:")
                    with heartbeat(label) if heartbeat is not None and live else nullcontext():
                        response = provider.complete(prompt, task_id=task.id)
                    attempt = {
                        "run": run,
                        "response": clean_text(response.text),
                        "latency_s": _finite_float(response.latency_s, 0.0),
                        "input_tokens": _nonnegative_int(response.input_tokens),
                        "output_tokens": _nonnegative_int(response.output_tokens),
                    }
                    seconds = f"{attempt['latency_s']:.1f}".replace(".", ",")
                    progress(f"  ok  {task.id:<24} {side.upper()}  guardada ({seconds} s)")
                except Exception as exc:  # noqa: BLE001
                    message = clean_text(
                        str(exc) if isinstance(exc, ProviderError) else _unexpected(exc)
                    )
                    attempt = {"run": run, "error": message}
                    progress(f"  --  {task.id:<24} {side.upper()}  error: {message[:120]}")
                task_data["attempts"][side].append(attempt)
                data["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
                save_results(data, path)
    data["status"] = "complete"
    data["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    save_results(data, path)
    return path


def recorded_providers(
    recorded: dict, tasks: list[Task], source: Path
) -> tuple[dict[str, RecordedProvider], list[str]]:
    """Proveedores grabados por letra y avisos (tareas cambiadas desde que se generaron)."""
    by_id = {task["id"]: task for task in recorded["tasks"]}
    missing = [task.id for task in tasks if task.id not in by_id]
    if missing:
        raise ResultsError(
            f"la tarea «{missing[0]}» no está en {source}: genera de nuevo con esas tareas o "
            "reproduce solo las que se generaron."
        )
    warnings = [
        f"la tarea {task.id} cambió desde que se generaron las respuestas: los tests pueden no "
        "corresponder al enunciado que vio el modelo."
        for task in tasks
        if by_id[task.id].get("fingerprint") != task_fingerprint(task)
    ]
    providers = {
        side: RecordedProvider(
            item["spec"],
            {task_id: entry["attempts"][side] for task_id, entry in by_id.items()},
        )
        for side, item in recorded["contenders"].items()
    }
    return providers, warnings


def load_responses(path: Path) -> dict:
    path = Path(path)
    try:
        if path.stat().st_size > MAX_RESPONSES_SIZE:
            raise ResultsError(f"{path} supera el límite de 50 MiB.")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ResultsError:
        raise
    except FileNotFoundError:
        raise ResultsError(
            f"no existe {path}. Genera las respuestas con `modelduel run … --solo-generar "
            "--out CARPETA`."
        ) from None
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ResultsError(f"{path} no es un respuestas.json válido: {exc}") from None
    if (
        not isinstance(data, dict)
        or data.get("kind") != "responses"
        or data.get("schema") != RESPONSES_SCHEMA
    ):
        raise ResultsError(f"{path} no es un respuestas.json de modelduel (kind/schema inválidos).")
    contenders = data.get("contenders")
    if not isinstance(contenders, dict) or not 2 <= len(contenders) <= 6:
        raise ResultsError(f"{path} debe tener entre 2 y 6 contendientes.")
    if list(contenders) != list(ALL_SIDES[: len(contenders)]):
        raise ResultsError(f"{path} tiene contendientes en un orden o con letras no válidos.")
    specs = []
    for side in contenders:
        spec = contenders[side].get("spec") if isinstance(contenders[side], dict) else None
        if not isinstance(spec, str) or not spec.strip() or spec in specs:
            raise ResultsError(f"{path} tiene specs vacíos o repetidos.")
        specs.append(spec)
    runs = data.get("runs")
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise ResultsError(f"{path} tiene un número de ejecuciones inválido.")
    if data.get("status") != "complete":
        raise ResultsError(f"{path}: la generación se cortó; vuelve a generarla.")
    if not isinstance(data.get("tasks"), list):
        raise ResultsError(f"{path} no contiene una lista de tareas válida.")
    seen_tasks: set[str] = set()
    for task in data["tasks"]:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str):
            raise ResultsError(f"{path} contiene una tarea inválida.")
        if task["id"] in seen_tasks:
            raise ResultsError(f"{path} contiene tareas repetidas.")
        seen_tasks.add(task["id"])
        attempts = task.get("attempts")
        if not isinstance(attempts, dict):
            raise ResultsError(f"{path} contiene intentos inválidos.")
        for side in contenders:
            if not isinstance(attempts.get(side), list):
                raise ResultsError(f"{path} contiene intentos inválidos para {side.upper()}.")
            for attempt in attempts[side]:
                if (
                    not isinstance(attempt, dict)
                    or not isinstance(attempt.get("run"), int)
                    or isinstance(attempt.get("run"), bool)
                    or attempt["run"] < 1
                    or ("error" not in attempt and not isinstance(attempt.get("response"), str))
                    or ("error" in attempt and not isinstance(attempt.get("error"), str))
                ):
                    raise ResultsError(f"{path} contiene un intento inválido.")
    return data


def copy_tasks(tasks: list[Task], out: Path) -> None:
    """Copia cada tarea (sin ``__pycache__``) a ``out/<id>`` para llevarla con las respuestas."""
    out.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        shutil.copytree(
            task.path,
            out / task.id,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def _finite_float(value: object, default: float) -> float:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    ):
        return float(value)
    return default


def _nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
