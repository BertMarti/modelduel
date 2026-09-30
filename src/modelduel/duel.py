"""Orquesta el duelo: pide el código a cada modelo y ejecuta los tests de cada tarea."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from modelduel import __version__
from modelduel.extract import extract_code
from modelduel.pricing import Price, compute_cost, find_price
from modelduel.providers import Provider, ProviderError
from modelduel.results import SCHEMA_VERSION, summarize
from modelduel.resume import Key, task_fingerprint
from modelduel.runner import DEFAULT_TIMEOUT, TestRun, build_prompt, run_tests
from modelduel.tasks import Task

Progress = Callable[[str], None]
Update = Callable[[dict], None]


def run_duel(
    tasks: list[Task],
    providers: dict[str, Provider],
    prices: dict[str, Price],
    runs: int = 1,
    timeout: float = DEFAULT_TIMEOUT,
    progress: Progress | None = None,
    on_update: Update | None = None,
    reuse: dict[Key, dict] | None = None,
    created_at: str | None = None,
) -> dict:
    """Enfrenta a los contendientes. ``on_update`` recibe los resultados tras cada intento.

    ``reuse`` son intentos ya hechos (de ``plan_resume``) que se copian en lugar de repetirse.
    """
    progress = progress or (lambda _msg: None)
    on_update = on_update or (lambda _results: None)
    reuse = reuse or {}
    sides = list(providers)
    contender_prices = {side: find_price(providers[side].spec, prices) for side in sides}
    results: dict = {
        "schema": SCHEMA_VERSION,
        "tool": "modelduel",
        "version": __version__,
        "created_at": created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "in_progress",
        "runs": runs,
        "timeout_s": timeout,
        "contenders": {
            side: {
                "spec": providers[side].spec,
                "price": contender_prices[side].to_dict() if contender_prices[side] else None,
            }
            for side in sides
        },
        "tasks": [],
    }
    entries = {}
    for task in tasks:
        entry = {
            "id": task.id,
            "title": task.title,
            "difficulty": task.difficulty,
            "statement": task.statement,
            "fingerprint": task_fingerprint(task),
            "tests_expected": task.expected_tests,
            "results": {side: [] for side in sides},
        }
        results["tasks"].append(entry)
        entries[task.id] = entry
    # Los intentos reutilizables entran ya en el primer guardado: una interrupción temprana
    # no debe hacer perder lo que se había conseguido antes.
    for (task_id, side, _run), attempt in sorted(reuse.items(), key=lambda kv: kv[0][2]):
        if task_id in entries and side in providers:
            done = _reused(attempt, contender_prices[side])
            entries[task_id]["results"][side].append(done)
    _refresh(results, on_update)

    for task in tasks:
        prompt = build_prompt(task)
        entry = entries[task.id]
        for run in range(1, runs + 1):
            for side in sides:
                key = (task.id, side, run)
                if key in reuse:
                    progress(_progress_line(task, side, run, runs, reuse[key], reused=True))
                    continue
                attempt = run_attempt(
                    task, prompt, providers[side], contender_prices[side], timeout
                )
                attempt["run"] = run
                attempts = entry["results"][side]
                attempts.append(attempt)
                attempts.sort(key=lambda a: a["run"])
                progress(_progress_line(task, side, run, runs, attempt))
                _refresh(results, on_update)
    results["status"] = "complete"
    _refresh(results, on_update)
    return results


def _refresh(results: dict, on_update: Update) -> None:
    results["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    results["summary"] = summarize(results)
    on_update(results)


def _reused(attempt: dict, price: Price | None) -> dict:
    """Copia de un intento anterior con el coste recalculado con la tabla de precios actual."""
    copy = dict(attempt)
    copy["cost"] = compute_cost(price, copy.get("input_tokens"), copy.get("output_tokens"))
    return copy


def run_attempt(
    task: Task, prompt: str, provider: Provider, price: Price | None, timeout: float
) -> dict:
    try:
        response = provider.complete(prompt, task_id=task.id)
    except Exception as exc:  # noqa: BLE001 - un intento fallido no debe tumbar todo el duelo
        message = str(exc) if isinstance(exc, ProviderError) else _unexpected(exc)
        test_run = TestRun(status="provider_error", total=task.expected_tests, message=message)
        attempt = test_run.to_dict()
        attempt.update(
            latency_s=None,
            input_tokens=None,
            output_tokens=None,
            cost=None,
            code=None,
            response="",
        )
        return attempt
    text = clean_text(response.text)
    code = extract_code(text)
    test_run = run_tests(code, task, timeout=timeout)
    attempt = test_run.to_dict()
    attempt.update(
        latency_s=round(response.latency_s, 3),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost=compute_cost(price, response.input_tokens, response.output_tokens),
        code=code,
        response=text if code is None else "",
    )
    return attempt


def clean_text(text: str | None) -> str:
    """Sustituye los sustitutos UTF-16 sueltos (válidos en JSON, no en UTF-8) por «?»."""
    if not text:
        return ""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _unexpected(exc: Exception) -> str:
    return f"Error inesperado del proveedor ({type(exc).__name__}): {exc}"


def _progress_line(
    task: Task, side: str, run: int, runs: int, attempt: dict, reused: bool = False
) -> str:
    run_label = f" #{run}" if runs > 1 else ""
    mark = "==" if reused else ("ok" if attempt["solved"] else "--")
    detail = f"{attempt['passed']}/{attempt['total']}"
    if attempt["status"] not in ("ok",):
        detail += f" ({attempt['status']})"
    if reused:
        detail += " · ya hecho"
    return f"  {mark}  {task.id + run_label:<24} {side.upper()}  {detail}"
