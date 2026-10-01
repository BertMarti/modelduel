"""Informe Markdown (``informe.md``) para pegar en un PR o un issue de GitHub.

Todo texto que viene de ``results.json`` es dato no fiable: pasa por ``md_text``. El informe no
copia el código ni la salida de los modelos (para eso está el HTML).
"""

from __future__ import annotations

import re

from modelduel import __version__
from modelduel.report.html import (
    STATUS_LABELS,
    _short_label,
    fmt_cost,
    fmt_date,
    fmt_seconds,
    fmt_tokens,
    plural,
)
from modelduel.results import costs_comparable, decide, rank_sides, sides_of, summarize

SITE_URL = "https://bertmarti.github.io/modelduel/"

# Todo lo que Markdown de GitHub (GFM) interpreta dentro de una línea, más ``@`` (menciones y
# correos), ``#`` (referencias a issues) y ``$`` (fórmulas).
_SPECIAL = re.compile(r"[\\`*_~\[\]()<>|&!#@$]")
# Caracteres de control y de dirección Unicode (los de "Trojan Source"); el espacio ya se aplanó.
_INVISIBLE = re.compile(r"[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\u2060]")


BACKSLASH = chr(92)
ZWSP = chr(0x200B)  # espacio de ancho cero


def _escape_start(match: re.Match) -> str:
    return BACKSLASH + match[1] if match[1] else match[2] + BACKSLASH + "."


def md_text(value: object, limit: int = 200) -> str:
    """Texto de ``results.json`` (no fiable) listo para ir en una línea de Markdown o en una celda.

    Aplana saltos de línea, quita controles, recorta con «…» y escapa con barra invertida todo lo
    que sería sintaxis: no deja enlaces, imágenes, HTML, entidades, menciones, referencias ni
    barras de tabla.
    """
    text = "" if value is None else str(value)
    text = _INVISIBLE.sub("", re.sub(r"\s+", " ", text)).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    text = _SPECIAL.sub(r"\\\g<0>", text)
    text = re.sub(r":(?=/)", r"\\:", text)  # http://… y https://… dejan de ser autoenlace
    text = re.sub(r"(?i)\bwww\.", lambda m: m.group()[:-1] + "\\.", text)
    # GitHub enlaza menciones, correos y referencias DESPUÉS de leer el Markdown, así que la
    # barra no basta: un espacio de ancho cero tras «@» y «#» les quita el sentido.
    text = text.replace("@", "@" + ZWSP).replace("#", "#" + ZWSP)
    # Y GH-1 (referencia) y los SHA de commit (7 a 40 hexadecimales), que GitHub también enlaza.
    text = re.sub(r"(?i)\b(GH-)(?=\d)", lambda m: m[1] + ZWSP, text)
    text = re.sub(r"\b([0-9a-fA-F]{3})(?=[0-9a-fA-F]{4,37}\b)", lambda m: m[1] + ZWSP, text)
    # Al empezar una línea, «- », «+ », «= » o «1. » serían lista o subrayado de título.
    return re.sub(r"^(?:([-+=])|(\d+)\.(?=\s))", _escape_start, text)


def _table(header: list[str], rows: list[list[str]], right: set[int] = frozenset()) -> list[str]:
    align = ["---:" if i in right else "---" for i in range(len(header))]
    lines = [f"| {' | '.join(header)} |", f"| {' | '.join(align)} |"]
    lines += [f"| {' | '.join(row)} |" for row in rows]
    return lines


def _label(results: dict, side: str) -> str:
    return f"**{side.upper()}** {md_text(results['contenders'][side]['spec'])}"


def _verdict(results: dict, summary: dict, runs: int) -> str:
    winner, criterion = decide(summary)
    summed = f" (suma de {runs} ejecuciones)" if runs > 1 else ""
    if winner is None:
        if costs_comparable(summary):
            return "empate en tareas resueltas, tests y coste" + summed
        return "empate en tareas resueltas y tests (sin coste comparable)" + summed
    other = rank_sides(summary)[1][1]
    win, lose = summary[winner], summary[other]
    tasks_w, tasks_l = int(win["tasks_solved"]), int(lose["tasks_solved"])
    tests_w, tests_l = int(win["tests_passed"]), int(lose["tests_passed"])
    who = f"gana {_label(results, winner)}"
    if criterion == "tasks":
        return f"{who} por tareas resueltas ({tasks_w} frente a {tasks_l} de {other.upper()})"
    if criterion == "tests":
        return (
            f"{who} por tests superados ({tests_w} frente a {tests_l} de "
            f"{other.upper()}, con las mismas tareas resueltas){summed}"
        )
    return (
        f"{who} por coste ({md_text(fmt_cost(win['cost'], win['currency']))} frente a "
        f"{md_text(fmt_cost(lose['cost'], lose['currency']))} de {other.upper()}, "
        "con las mismas tareas resueltas y tests)"
    )


def _scoreboard(results: dict, summary: dict) -> list[str]:
    rows = []
    for rank, side in rank_sides(summary):
        s = summary[side]
        rows.append(
            [
                str(rank),
                _label(results, side),
                f"{int(s['tasks_solved'])}/{int(s['tasks_total'])}",
                f"{int(s['tests_passed'])}/{int(s['tests_total'])}",
                fmt_seconds(s["latency_s"]),
                fmt_tokens(s["input_tokens"], s["output_tokens"]),
                md_text(fmt_cost(s["cost"], s["currency"])),
            ]
        )
    header = ["#", "Contendiente", "Tareas", "Tests", "Tiempo", "Tokens (ent/sal)", "Coste"]
    return _table(header, rows, right={0, 2, 3, 4, 5, 6})


def _task_cell(attempts: list[dict]) -> str:
    passed = sum(int(a["passed"]) for a in attempts)
    total = sum(int(a["total"]) for a in attempts)
    statuses = {a["status"] for a in attempts} - {"ok"}
    notes = ", ".join(md_text(STATUS_LABELS.get(s, s), 60) for s in sorted(map(str, statuses)))
    return f"{passed}/{total}" + (f" · {notes}" if notes else "")


def _task_table(results: dict, sides: list[str]) -> list[str]:
    rows = []
    for task in results["tasks"]:
        title = md_text(task.get("title") or task.get("id"))
        rows.append([title] + [_task_cell(task["results"][side]) for side in sides])
    return _table(["Tarea"] + [s.upper() for s in sides], rows)


def _incomplete(results: dict, sides: list[str]) -> str:
    if results.get("status") != "in_progress":
        return ""
    expected = len(results["tasks"]) * int(results.get("runs", 1)) * len(sides)
    done = sum(len(t["results"].get(side, [])) for t in results["tasks"] for side in sides)
    return (
        f"> **Duelo incompleto: {done} de {expected} intentos.** El marcador solo cuenta lo hecho "
        "hasta ahora. Continúa con `--resume` y la misma configuración."
    )


def _warnings(results: dict, summary: dict, runs: int) -> list[str]:
    if runs <= 1:
        weak = (
            "**Una sola ejecución es una señal débil.** Los modelos no son deterministas: la "
            "misma pregunta puede dar otra respuesta mañana. Repite el duelo con `--runs N` y "
            "con tareas de tu propio trabajo antes de sacar conclusiones."
        )
    else:
        weak = (
            "**Pocas ejecuciones siguen siendo una señal débil.** "
            f"Aquí hay {runs} ejecuciones por tarea, mejor que una, pero sigue siendo una "
            "muestra pequeña. Usa tareas de tu propio trabajo y mira el código, no solo el "
            "marcador."
        )
    notes = [weak]
    if any(s["fictitious_price"] for s in summary.values()):
        notes.append("Precios ficticios de demostración, no reales.")
    elif not costs_comparable(summary):
        notes.append("El coste no entra en el veredicto: falta el precio o las monedas difieren.")
    else:
        notes.append("Coste = entrada/1e6 × tarifa + salida/1e6 × tarifa.")
    return [f"- {note}" for note in notes]


def render_markdown(results: dict) -> str:
    """Informe de un duelo de dos o de una liga (3 a 6) en Markdown de GitHub."""
    summary = results.get("summary") or summarize(results)
    sides = sides_of(results)
    runs = int(results.get("runs", 1))
    n_tasks = len(results["tasks"])
    if len(sides) > 2:
        title = f"Informe de liga modelduel ({len(sides)} contendientes)"
    else:
        names = " vs ".join(md_text(_short_label(results["contenders"][s]["spec"])) for s in sides)
        title = f"Informe modelduel: {names}"
    lede = (
        f"{plural(n_tasks, 'tarea', 'tareas')} · {plural(runs, 'ejecución', 'ejecuciones')} por "
        f"tarea · límite de {float(results.get('timeout_s', 20)):g} s por ejecución de tests"
    )
    lines = [f"# {title}", "", lede, ""]
    incomplete = _incomplete(results, sides)
    if incomplete:
        lines += [incomplete, ""]
    lines += ["## Marcador", "", *_scoreboard(results, summary), ""]
    lines += [f"**Veredicto:** {_verdict(results, summary, runs)}.", ""]
    lines += ["## Por tarea", "", *_task_table(results, sides), ""]
    lines += ["Tests superados por cada contendiente en cada tarea.", ""]
    lines += ["## Avisos", "", *_warnings(results, summary, runs), ""]
    version = md_text(results.get("version", __version__))
    date = md_text(fmt_date(results.get("created_at", "")))
    lines += [f"Generado con modelduel {version} · {date} · {SITE_URL}", ""]
    return "\n".join(lines)
