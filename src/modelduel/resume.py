"""Reanudación de un duelo interrumpido: qué intentos de ``results.json`` se reutilizan."""

from __future__ import annotations

import hashlib

from modelduel.tasks import Task, read_text

Key = tuple[str, str, int]  # (id de la tarea, contendiente, número de ejecución)


class ResumeError(Exception):
    """El ``results.json`` previo no se puede reanudar con la configuración actual."""


def task_fingerprint(task: Task) -> str:
    """Huella del enunciado y de los tests: si cambian, los intentos previos ya no valen."""
    digest = hashlib.sha256()
    digest.update(task.statement.encode("utf-8"))
    digest.update(b"\0")
    digest.update(read_text(task.test_path).replace("\r\n", "\n").encode("utf-8"))
    return digest.hexdigest()[:16]


def plan_resume(
    previous: dict, tasks: list[Task], specs: dict[str, str], runs: int, timeout: float
) -> tuple[dict[Key, dict], list[str]]:
    """Intentos reutilizables de ``previous`` y avisos sobre lo que no coincide.

    Se reutilizan los intentos ya terminados (no los ``provider_error``, que se repiten) de
    tareas que no han cambiado. Si los contendientes no son los mismos se lanza ``ResumeError``:
    mezclar modelos distintos en un mismo duelo daría un marcador sin sentido.
    """
    old_specs = {side: (c or {}).get("spec") for side, c in previous.get("contenders", {}).items()}
    if old_specs != specs:
        detail = "; ".join(
            f"{side.upper()}: antes {old_specs.get(side) or '(nadie)'}, "
            f"ahora {specs.get(side) or '(nadie)'}"
            for side in sorted(set(old_specs) | set(specs))
            if old_specs.get(side) != specs.get(side)
        )
        raise ResumeError(
            f"los contendientes no coinciden con los del results.json previo ({detail}). "
            "Usa la misma configuración o elige otra carpeta --out."
        )
    warnings: list[str] = []
    old_timeout = previous.get("timeout_s")
    if old_timeout is not None and old_timeout != timeout:
        warnings.append(
            f"el límite de los tests era {old_timeout:g} s y ahora es {timeout:g} s: "
            "se conservan los intentos ya hechos."
        )
    old_runs = previous.get("runs", 1)
    if old_runs > runs:
        warnings.append(
            f"antes eran {old_runs} ejecuciones por tarea y ahora {runs}: "
            "se descartan las sobrantes."
        )
    by_id = {t["id"]: t for t in previous.get("tasks", []) if isinstance(t, dict)}
    reusable: dict[Key, dict] = {}
    for task in tasks:
        old = by_id.get(task.id)
        if old is None:
            continue
        old_print = old.get("fingerprint")
        if old_print is not None and old_print != task_fingerprint(task):
            warnings.append(
                f"la tarea «{task.id}» ha cambiado desde el duelo anterior: se repite entera."
            )
            continue
        for side in specs:
            for attempt in (old.get("results") or {}).get(side, []):
                run = attempt.get("run")
                if (
                    isinstance(run, int)
                    and 1 <= run <= runs
                    and attempt["status"] != "provider_error"
                ):
                    reusable[(task.id, side, run)] = attempt
    for task_id in sorted(set(by_id) - {t.id for t in tasks}):
        warnings.append(f"la tarea «{task_id}» ya no está en la carpeta de tareas: se descarta.")
    return reusable, warnings
