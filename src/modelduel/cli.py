"""Interfaz de línea de órdenes de modelduel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from modelduel import __version__
from modelduel.duel import run_duel
from modelduel.pricing import PricingError, load_prices
from modelduel.providers import ProviderError, get_provider
from modelduel.report import write_report
from modelduel.report.html import fmt_cost, fmt_int, fmt_seconds, plural
from modelduel.results import ResultsError, load_results, save_results
from modelduel.runner import DEFAULT_TIMEOUT, RunnerError, ensure_pytest_available
from modelduel.tasks import TaskError, discover_tasks, is_task_dir

EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelduel",
        description="Dos modelos, una tarea, los mismos tests.",
        epilog="Aviso: el código generado por los modelos se ejecuta en tu máquina.",
    )
    parser.add_argument("--version", action="version", version=f"modelduel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="orden")

    run = sub.add_parser("run", help="enfrenta a dos modelos y genera el informe")
    run.add_argument("tasks", type=Path, help="carpeta de tareas o carpeta de una tarea")
    run.add_argument("--a", required=True, metavar="PROVEEDOR:MODELO", help="contendiente A")
    run.add_argument("--b", required=True, metavar="PROVEEDOR:MODELO", help="contendiente B")
    run.add_argument("--runs", type=int, default=1, metavar="N", help="ejecuciones por tarea (1)")
    run.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="S",
        help=f"límite en segundos para los tests de cada respuesta ({DEFAULT_TIMEOUT:g})",
    )
    run.add_argument("--prices", type=Path, metavar="F.json", help="tabla de precios adicional")
    run.add_argument(
        "--replays", type=Path, metavar="DIR", help="carpeta de respuestas grabadas para replay"
    )
    run.add_argument("--out", type=Path, required=True, metavar="DIR", help="carpeta de salida")

    report = sub.add_parser("report", help="regenera el informe HTML desde results.json")
    report.add_argument("results", type=Path, help="ruta a results.json")
    report.add_argument("--out", type=Path, required=True, metavar="DIR", help="carpeta de salida")

    lst = sub.add_parser("list-tasks", help="lista las tareas de una carpeta")
    lst.add_argument("tasks", type=Path, help="carpeta de tareas")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "report":
            return cmd_report(args)
        return cmd_list_tasks(args)
    except (TaskError, ProviderError, PricingError, ResultsError, RunnerError) as exc:
        print(f"modelduel: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("\nmodelduel: interrumpido.", file=sys.stderr)
        return 130


def cmd_run(args: argparse.Namespace) -> int:
    if args.runs < 1:
        raise TaskError("--runs debe ser 1 o más.")
    if args.timeout <= 0:
        raise TaskError("--timeout debe ser mayor que 0.")
    tasks = discover_tasks(args.tasks)
    prices = load_prices(args.prices)
    # examples/tasks[/<tarea>] -> examples/replays
    tasks_root = args.tasks.parent if is_task_dir(args.tasks) else args.tasks
    replay_dirs = [
        d
        for d in (args.replays, tasks_root.parent / "replays", Path("examples/replays"))
        if d is not None
    ]
    providers = {"a": get_provider(args.a, replay_dirs), "b": get_provider(args.b, replay_dirs)}
    ensure_pytest_available()

    print(
        f"modelduel {__version__} · {plural(len(tasks), 'tarea', 'tareas')} · "
        f"{plural(args.runs, 'ejecución', 'ejecuciones')} por tarea"
    )
    print(f"  A  {providers['a'].spec}")
    print(f"  B  {providers['b'].spec}")
    print("  Aviso: el código de los modelos se ejecuta en esta máquina (temporal + límite).")
    print()
    results = run_duel(
        tasks,
        providers,
        prices,
        runs=args.runs,
        timeout=args.timeout,
        progress=lambda line: print(line, flush=True),
    )
    save_results(results, args.out / "results.json")
    html_path = write_report(results, args.out)
    print()
    print(scoreboard(results))
    print()
    print(f"  Resultados  {args.out / 'results.json'}")
    print(f"  Informe     {html_path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    results = load_results(args.results)
    html_path = write_report(results, args.out)
    print(f"Informe regenerado: {html_path}")
    return 0


def cmd_list_tasks(args: argparse.Namespace) -> int:
    tasks = discover_tasks(args.tasks)
    width = max(len(t.id) for t in tasks)
    for task in tasks:
        extra = f"  [{task.difficulty}]" if task.difficulty else ""
        print(f"{task.id:<{width}}  {task.expected_tests:>2} tests  {task.title}{extra}")
    return 0


def scoreboard(results: dict) -> str:
    s = results["summary"]
    a, b = s["a"], s["b"]
    specs = (results["contenders"]["a"]["spec"], results["contenders"]["b"]["spec"])
    rows = [
        ("", f"A {specs[0]}", f"B {specs[1]}"),
        (
            "Tests superados",
            f"{a['tests_passed']}/{a['tests_total']}",
            f"{b['tests_passed']}/{b['tests_total']}",
        ),
        (
            "Tareas resueltas",
            f"{a['tasks_solved']}/{a['tasks_total']}",
            f"{b['tasks_solved']}/{b['tasks_total']}",
        ),
        ("Tiempo del modelo", fmt_seconds(a["latency_s"]), fmt_seconds(b["latency_s"])),
        (
            "Tokens entrada/salida",
            f"{fmt_int(a['input_tokens'])}/{fmt_int(a['output_tokens'])}",
            f"{fmt_int(b['input_tokens'])}/{fmt_int(b['output_tokens'])}",
        ),
        ("Coste estimado", fmt_cost(a["cost"], a["currency"]), fmt_cost(b["cost"], b["currency"])),
    ]
    w0 = max(len(r[0]) for r in rows)
    w1 = max(len(r[1]) for r in rows)
    w2 = max(len(r[2]) for r in rows)
    lines = [f"  {r[0]:<{w0}}   {r[1]:>{w1}}   {r[2]:>{w2}}" for r in rows]
    rule = "  " + "-" * (w0 + w1 + w2 + 6)
    lines.insert(1, rule)
    if a["fictitious_price"] or b["fictitious_price"]:
        lines.append("  (precios ficticios de demostración)")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
