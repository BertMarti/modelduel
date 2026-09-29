"""Orquesta el duelo: pide el código a cada modelo y ejecuta los tests de cada tarea."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from modelduel import __version__
from modelduel.extract import extract_code
from modelduel.pricing import Price, compute_cost, find_price
from modelduel.providers import Provider, ProviderError
from modelduel.results import SCHEMA_VERSION, SIDES, summarize
from modelduel.runner import DEFAULT_TIMEOUT, TestRun, build_prompt, run_tests
from modelduel.tasks import Task

Progress = Callable[[str], None]


def run_duel(
    tasks: list[Task],
    providers: dict[str, Provider],
    prices: dict[str, Price],
    runs: int = 1,
    timeout: float = DEFAULT_TIMEOUT,
    progress: Progress | None = None,
) -> dict:
    progress = progress or (lambda _msg: None)
    contender_prices = {side: find_price(providers[side].spec, prices) for side in SIDES}
    results: dict = {
        "schema": SCHEMA_VERSION,
        "tool": "modelduel",
        "version": __version__,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runs": runs,
        "timeout_s": timeout,
        "contenders": {
            side: {
                "spec": providers[side].spec,
                "price": contender_prices[side].to_dict() if contender_prices[side] else None,
            }
            for side in SIDES
        },
        "tasks": [],
    }
    for task in tasks:
        prompt = build_prompt(task)
        entry = {
            "id": task.id,
            "title": task.title,
            "difficulty": task.difficulty,
            "statement": task.statement,
            "tests_expected": task.expected_tests,
            "results": {side: [] for side in SIDES},
        }
        for run in range(1, runs + 1):
            for side in SIDES:
                attempt = run_attempt(
                    task, prompt, providers[side], contender_prices[side], timeout
                )
                attempt["run"] = run
                entry["results"][side].append(attempt)
                progress(_progress_line(task, side, run, runs, attempt))
        results["tasks"].append(entry)
    results["summary"] = summarize(results)
    return results


def run_attempt(
    task: Task, prompt: str, provider: Provider, price: Price | None, timeout: float
) -> dict:
    try:
        response = provider.complete(prompt, task_id=task.id)
    except ProviderError as exc:
        test_run = TestRun(status="provider_error", total=task.expected_tests, message=str(exc))
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
    code = extract_code(response.text)
    test_run = run_tests(code, task, timeout=timeout)
    attempt = test_run.to_dict()
    attempt.update(
        latency_s=round(response.latency_s, 3),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost=compute_cost(price, response.input_tokens, response.output_tokens),
        code=code,
        response=response.text if code is None else "",
    )
    return attempt


def _progress_line(task: Task, side: str, run: int, runs: int, attempt: dict) -> str:
    run_label = f" #{run}" if runs > 1 else ""
    mark = "ok" if attempt["solved"] else "--"
    detail = f"{attempt['passed']}/{attempt['total']}"
    if attempt["status"] not in ("ok",):
        detail += f" ({attempt['status']})"
    return f"  {mark}  {task.id + run_label:<24} {side.upper()}  {detail}"
