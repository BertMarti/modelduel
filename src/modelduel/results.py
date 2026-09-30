"""Estructura de ``results.json`` y resumen tipo marcador."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

SCHEMA_VERSION = 1
SIDES = ("a", "b")


class ResultsError(Exception):
    """``results.json`` ilegible o con formato inesperado."""


def summarize(results: dict) -> dict[str, dict]:
    """Totales por contendiente a partir de los intentos registrados."""
    summary: dict[str, dict] = {}
    tasks = results.get("tasks", [])
    for side in SIDES:
        attempts = [a for task in tasks for a in task["results"].get(side, [])]
        runs = results.get("runs", 1)
        solved_tasks = sum(
            1
            for task in tasks
            if len(task["results"].get(side, [])) >= runs
            and all(a["solved"] for a in task["results"][side])
        )
        costs = [a.get("cost") for a in attempts]
        inputs = [a.get("input_tokens") for a in attempts]
        outputs = [a.get("output_tokens") for a in attempts]
        price = (results.get("contenders", {}).get(side) or {}).get("price")
        summary[side] = {
            "tests_passed": sum(a["passed"] for a in attempts),
            "tests_total": sum(a["total"] for a in attempts),
            "tasks_solved": solved_tasks,
            "tasks_total": len(tasks),
            "attempts_solved": sum(1 for a in attempts if a["solved"]),
            "attempts_total": len(attempts),
            "latency_s": round(sum(a.get("latency_s") or 0.0 for a in attempts), 3),
            "test_time_s": round(sum(a.get("duration_s") or 0.0 for a in attempts), 3),
            "input_tokens": _sum_known(inputs),
            "output_tokens": _sum_known(outputs),
            "tokens_complete": all(v is not None for v in inputs + outputs),
            "cost": sum(costs) if attempts and all(c is not None for c in costs) else None,
            "currency": price["currency"] if price else None,
            "fictitious_price": bool(price and price.get("fictitious")),
        }
    return summary


def _sum_known(values: list[int | None]) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def save_results(results: dict, path: Path) -> None:
    """Escritura atómica: archivo temporal en la misma carpeta y reemplazo.

    Si el proceso muere a mitad, ``results.json`` sigue siendo la versión anterior completa.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    text = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    try:
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _replace(source: Path, target: Path) -> None:
    # En Windows el reemplazo falla un instante si un antivirus o un visor tiene el archivo abierto.
    for attempt in range(5):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def load_results(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ResultsError(f"No se pudo leer {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ResultsError(f"{path} no es JSON válido: {exc}") from exc
    if not isinstance(data, dict) or "tasks" not in data or "contenders" not in data:
        raise ResultsError(f"{path} no parece un results.json de modelduel.")
    try:
        data["summary"] = summarize(data)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ResultsError(
            f"{path} no parece un results.json de modelduel ({type(exc).__name__}: {exc})."
        ) from exc
    return data
