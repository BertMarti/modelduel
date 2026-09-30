"""Estructura de ``results.json`` y resumen tipo marcador."""

from __future__ import annotations

import json
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
        solved_tasks = sum(
            1
            for task in tasks
            if task["results"].get(side) and all(a["solved"] for a in task["results"][side])
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_results(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ResultsError(f"No se pudo leer {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ResultsError(f"{path} no es JSON válido: {exc}") from exc
    if not isinstance(data, dict) or "tasks" not in data or "contenders" not in data:
        raise ResultsError(f"{path} no parece un results.json de modelduel.")
    data["summary"] = summarize(data)
    return data
