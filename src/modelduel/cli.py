"""Interfaz de línea de órdenes de modelduel."""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from modelduel import __version__
from modelduel.duel import run_duel
from modelduel.pricing import PricingError, load_prices
from modelduel.providers import ProviderError, get_provider
from modelduel.providers.base import DEFAULT_RETRIES
from modelduel.report import write_report
from modelduel.report.html import fmt_cost, fmt_int, fmt_seconds, plural
from modelduel.results import ResultsError, load_results, save_results, summarize
from modelduel.resume import ResumeError, plan_resume
from modelduel.runner import DEFAULT_TIMEOUT, RunnerError, ensure_pytest_available
from modelduel.tasks import TaskError, discover_tasks, is_task_dir

# Códigos de salida: 0 duelo completado (aunque los modelos fallen tests), 1 no se pudieron
# escribir los resultados, 2 error de uso o de configuración, 130 interrumpido con Ctrl+C.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


class OutputError(Exception):
    """No se pudo escribir en la carpeta de salida."""


# argparse no trae traducciones: se traducen sus mensajes de error más habituales.
_ARGPARSE_ES = [
    (r"the following arguments are required: (.+)", r"faltan argumentos obligatorios: \1"),
    (
        r"argument orden: invalid choice: (.+?) \(choose from (.+)\)",
        r"orden no válida: \1 (elige entre \2)",
    ),
    (
        r"argument (.+?): invalid choice: (.+?) \(choose from (.+)\)",
        r"argumento \1: valor no válido: \2 (elige entre \3)",
    ),
    (r"argument (.+?): invalid \w+ value: (.+)", r"argumento \1: valor no válido: \2"),
    (r"argument (.+?): expected one argument", r"argumento \1: necesita un valor"),
    (r"unrecognized arguments: (.+)", r"argumentos no reconocidos: \1"),
    (r"ambiguous option: (.+?) could match (.+)", r"opción ambigua: \1 puede ser \2"),
]


def translate_argparse(message: str) -> str:
    for pattern, replacement in _ARGPARSE_ES:
        translated, n = re.subn(f"^{pattern}$", replacement, message)
        if n:
            return translated
    return message


class _SpanishHelpFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix="uso: " if prefix is None else prefix)


class SpanishArgumentParser(argparse.ArgumentParser):
    """ArgumentParser con ayuda y errores en español y código de salida ``EXIT_USAGE``."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs["add_help"] = False
        kwargs.setdefault("formatter_class", _SpanishHelpFormatter)
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos posicionales"
        self._optionals.title = "opciones"
        self.add_argument("-h", "--help", action="help", help="muestra esta ayuda y sale")

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {translate_argparse(message)}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = SpanishArgumentParser(
        prog="modelduel",
        description="Dos modelos, una tarea, los mismos tests.",
        epilog="Aviso: el código generado por los modelos se ejecuta en tu máquina.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"modelduel {__version__}",
        help="muestra la versión y sale",
    )
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
    run.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        metavar="N",
        help=f"reintentos ante HTTP 429/5xx y cortes de conexión ({DEFAULT_RETRIES})",
    )
    run.add_argument(
        "--resume",
        action="store_true",
        help="continúa el duelo de --out saltando los intentos ya terminados",
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
    except (TaskError, ProviderError, PricingError, ResultsError, RunnerError, ResumeError) as exc:
        print(f"modelduel: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OutputError as exc:
        print(f"modelduel: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nmodelduel: interrumpido.", file=sys.stderr)
        return EXIT_INTERRUPTED


def cmd_run(args: argparse.Namespace) -> int:
    if args.runs < 1:
        raise TaskError("--runs debe ser 1 o más.")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise TaskError("--timeout debe ser un número de segundos mayor que 0.")
    if args.retries < 0:
        raise TaskError("--retries debe ser 0 o más.")
    tasks = discover_tasks(args.tasks)
    prices = load_prices(args.prices)
    # examples/tasks[/<tarea>] -> examples/replays
    tasks_root = args.tasks.parent if is_task_dir(args.tasks) else args.tasks
    replay_dirs = [
        d
        for d in (args.replays, tasks_root.parent / "replays", Path("examples/replays"))
        if d is not None
    ]

    def on_retry(message: str) -> None:
        print(f"  ~~  {message}", flush=True)

    providers = {
        side: get_provider(spec, replay_dirs, retries=args.retries, on_retry=on_retry)
        for side, spec in (("a", args.a), ("b", args.b))
    }
    ensure_pytest_available()
    # Antes de gastar llamadas a las APIs: la carpeta de salida tiene que poder crearse.
    _prepare_out(args.out)
    results_path = args.out / "results.json"
    previous = _load_previous(results_path, args.resume)
    reuse: dict = {}
    warnings: list[str] = []
    if previous is not None:
        specs = {side: provider.spec for side, provider in providers.items()}
        reuse, warnings = plan_resume(previous, tasks, specs, args.runs, args.timeout)

    print(
        f"modelduel {__version__} · {plural(len(tasks), 'tarea', 'tareas')} · "
        f"{plural(args.runs, 'ejecución', 'ejecuciones')} por tarea"
    )
    for side, provider in providers.items():
        print(f"  {side.upper()}  {provider.spec}")
    print("  Aviso: el código de los modelos se ejecuta en esta máquina (temporal + límite).")
    if args.resume:
        total = len(tasks) * args.runs * len(providers)
        if previous is None:
            print(f"  Reanudar: no hay {results_path}; se empieza de cero.")
        else:
            print(
                f"  Reanudando: {plural(len(reuse), 'intento', 'intentos')} ya hecho"
                f"{'' if len(reuse) == 1 else 's'} de {total}; "
                f"quedan {total - len(reuse)}."
            )
        for warning in warnings:
            print(f"  Aviso: {warning}")
    print()

    latest: dict = {}
    save_failed = False

    def on_update(current: dict) -> None:
        """Guarda ``results.json`` tras cada intento sin tumbar el duelo si falla el disco."""
        nonlocal save_failed
        latest["results"] = current
        try:
            save_results(current, results_path)
        except OSError as exc:
            if not save_failed:
                save_failed = True
                print(f"  Aviso: no se pudo guardar {results_path}: {exc.strerror or exc}.")

    try:
        results = run_duel(
            tasks,
            providers,
            prices,
            runs=args.runs,
            timeout=args.timeout,
            progress=lambda line: print(line, flush=True),
            on_update=on_update,
            reuse=reuse,
            created_at=(previous or {}).get("created_at"),
        )
    except KeyboardInterrupt:
        return _interrupted(latest.get("results"), args.out)
    html_path = _write_outputs(results, args.out, with_json=True)
    print()
    print(scoreboard(results))
    print()
    print(f"  Resultados  {results_path}")
    print(f"  Informe     {html_path}")
    return 0


def _load_previous(results_path: Path, resume: bool) -> dict | None:
    """``results.json`` previo de la carpeta de salida (o ``None``).

    Sin ``--resume`` solo importa para no machacar por descuido un duelo a medias, que puede
    haber costado dinero.
    """
    if not results_path.is_file():
        return None
    if resume:
        return load_results(results_path)
    try:
        previous = load_results(results_path)
    except ResultsError:
        return None
    if previous.get("status") == "in_progress":
        raise ResumeError(
            f"{results_path} es un duelo incompleto. Continúalo con --resume o bórralo, "
            "o elige otra carpeta --out."
        )
    return None


def _interrupted(results: dict | None, out: Path) -> int:
    """Ctrl+C: lo hecho ya está en ``results.json``; se deja también el informe parcial."""
    print("\nmodelduel: interrumpido.", file=sys.stderr)
    if results is not None:
        try:
            results["summary"] = summarize(results)
            write_report(results, out)
        except (OSError, KeyError, TypeError, ValueError, AttributeError):
            pass
        print(
            f"Lo hecho hasta ahora está en {out / 'results.json'}. "
            "Continúa con la misma orden añadiendo --resume.",
            file=sys.stderr,
        )
    return EXIT_INTERRUPTED


def cmd_report(args: argparse.Namespace) -> int:
    results = load_results(args.results)
    _prepare_out(args.out)
    try:
        html_path = _write_outputs(results, args.out, with_json=False)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ResultsError(
            f"{args.results} no parece un results.json de modelduel ({type(exc).__name__}: {exc})."
        ) from exc
    print(f"Informe regenerado: {html_path}")
    return 0


def _prepare_out(out: Path) -> None:
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"no se pudo escribir en {out}: {exc.strerror or exc}.") from exc


def _write_outputs(results: dict, out: Path, with_json: bool) -> Path:
    try:
        if with_json:
            save_results(results, out / "results.json")
        return write_report(results, out)
    except OSError as exc:
        raise OutputError(f"no se pudo escribir en {out}: {exc.strerror or exc}.") from exc


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
