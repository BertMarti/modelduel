"""Informe de liga (3 a 6 contendientes): clasificación, comparativa y matriz por tarea."""

from __future__ import annotations

from collections.abc import Callable
from importlib import resources
from string import Template

from modelduel import __version__
from modelduel.report.html import (
    STATUS_LABELS,
    _short_label,
    _total_tokens,
    build_details,
    build_incomplete,
    build_warning,
    e,
    fmt_cost,
    fmt_date,
    fmt_int,
    fmt_seconds,
    fmt_tokens,
    plural,
    svg_ratio_bar,
)
from modelduel.results import rank_sides, sides_of

Row = tuple[str, str, str, float | None, str]  # letra, nombre, texto, valor, subtexto


def tag(side: str) -> str:
    """Letra del contendiente: el color nunca es la única pista."""
    return f'<span class="tag {side}">{side.upper()}</span>'


def best_sides(raw: dict[str, float | None], lower_is_better: bool) -> set[str]:
    """Contendientes con el mejor valor; ninguno si hay menos de dos datos o todos empatan."""
    known = {side: value for side, value in raw.items() if value is not None}
    if len(known) < 2:
        return set()
    best = min(known.values()) if lower_is_better else max(known.values())
    winners = {side for side, value in known.items() if value == best}
    return set() if len(winners) == len(known) else winners


def mark(winner: bool, text: bool = False) -> str:
    """Glifo del mejor; con ``text`` lleva también la palabra (nunca solo color ni solo forma)."""
    if not winner:
        return ""
    shown = "▲ mejor" if text else "▲"
    return (
        f'<span class="mark" aria-hidden="true">{shown}</span><span class="sr-only">(mejor)</span>'
    )


def metric_block(label: str, hint: str, rows: list[Row], lower_is_better: bool = False) -> str:
    """Un bloque por métrica con una barra fina por contendiente."""
    raw = {side: value for side, _name, _shown, value, _sub in rows}
    winners = best_sides(raw, lower_is_better)
    top = max((value for value in raw.values() if value is not None), default=0.0)
    lines = []
    for side, name, shown, value, sub in rows:
        text = f"{label}: {side.upper()} {name}, {shown}"
        ratio = (value or 0.0) / top if top else 0.0
        sub_html = f'<span class="sub">{e(sub)}</span>' if sub else ""
        lines.append(
            f'<div class="lg-row">{tag(side)}<span class="lg-name">{e(name)}</span>'
            f"{svg_ratio_bar(ratio, side, text)}"
            f'<span class="lg-val"><span class="num">{e(shown)}</span>'
            f"{mark(side in winners, text=True)}"
            f"{sub_html}</span></div>"
        )
    hint_html = f'<p class="hint">{e(hint)}</p>' if hint else ""
    return f'<div class="lg-metric"><h3>{e(label)}</h3>{hint_html}{"".join(lines)}</div>'


def build_metrics(results: dict, summary: dict, runs: int) -> str:
    sides = sides_of(results)
    names = {side: _short_label(results["contenders"][side]["spec"]) for side in sides}
    summed = f"suma de {runs} ejecuciones" if runs > 1 else ""

    def rows(
        shown: Callable[[dict], str],
        raw: Callable[[dict], float | None],
        sub: Callable[[dict], str] = lambda _d: "",
    ) -> list[Row]:
        return [
            (side, names[side], shown(summary[side]), raw(summary[side]), sub(summary[side]))
            for side in sides
        ]

    blocks = [
        metric_block(
            "Tareas resueltas",
            "todos los tests en todas las ejecuciones",
            rows(lambda d: f"{d['tasks_solved']}/{d['tasks_total']}", lambda d: d["tasks_solved"]),
        )
    ]
    if runs > 1:
        blocks.append(
            metric_block(
                "Intentos resueltos",
                "ejecuciones con todos los tests en verde",
                rows(
                    lambda d: f"{d['attempts_solved']}/{d['attempts_total']}",
                    lambda d: d["attempts_solved"],
                ),
            )
        )
    blocks.append(
        metric_block(
            "Tests superados",
            summed,
            rows(lambda d: f"{d['tests_passed']}/{d['tests_total']}", lambda d: d["tests_passed"]),
        )
    )
    blocks.append(
        metric_block(
            "Tiempo del modelo",
            "menos es mejor" + (f" · {summed}" if summed else ""),
            rows(
                lambda d: fmt_seconds(d["latency_s"]),
                lambda d: d["latency_s"],
                lambda d: f"tests: {fmt_seconds(d['test_time_s'])}",
            ),
            lower_is_better=True,
        )
    )
    blocks.append(
        metric_block(
            "Tokens",
            "menos es mejor",
            rows(
                lambda d: fmt_int(_total_tokens(d)),
                _total_tokens,
                lambda d: (
                    f"entrada {fmt_int(d['input_tokens'])} · salida {fmt_int(d['output_tokens'])}"
                ),
            ),
            lower_is_better=True,
        )
    )
    currencies = {summary[side]["currency"] for side in sides}
    cost_hint = "menos es mejor"
    if any(summary[side]["fictitious_price"] for side in sides):
        cost_hint = "precios ficticios de demostración"
    elif len(currencies) > 1 and all(summary[side]["cost"] is not None for side in sides):
        cost_hint = "monedas distintas: no comparables"
    blocks.append(
        metric_block(
            "Coste estimado",
            cost_hint,
            rows(
                lambda d: fmt_cost(d["cost"], d["currency"]),
                (lambda d: d["cost"]) if len(currencies) == 1 else (lambda _d: None),
            ),
            lower_is_better=True,
        )
    )
    return "\n".join(blocks)


def build_ranking(results: dict, summary: dict) -> str:
    """Filas de la clasificación: tareas resueltas, luego tests y luego coste."""
    rows = []
    for position, side in rank_sides(summary):
        data = summary[side]
        spec = results["contenders"][side]["spec"]
        ratio = data["tests_passed"] / data["tests_total"] if data["tests_total"] else 0.0
        label = f"{side.upper()}: {data['tests_passed']} de {data['tests_total']} tests superados"
        first = position == 1
        cells = [
            f'<th scope="row" class="rk">{position}{mark(first)}</th>',
            f'<td class="who">{tag(side)}{e(_short_label(spec))}'
            f'<span class="spec">{e(spec)}</span></td>',
            f"<td>{e(data['tasks_solved'])}/{e(data['tasks_total'])}</td>",
            f"<td>{e(data['tests_passed'])}/{e(data['tests_total'])}"
            f"{svg_ratio_bar(ratio, side, label)}</td>",
            f"<td>{e(fmt_seconds(data['latency_s']))}</td>",
            f"<td>{e(fmt_tokens(data['input_tokens'], data['output_tokens']))}</td>",
            f"<td>{e(fmt_cost(data['cost'], data['currency']))}</td>",
        ]
        css_class = ' class="first"' if first else ""
        rows.append(f"    <tr{css_class}>{''.join(cells)}</tr>")
    return "\n".join(rows)


def build_podium(results: dict, summary: dict) -> str:
    leaders = [side for position, side in rank_sides(summary) if position == 1]

    def name(side: str) -> str:
        label = e(_short_label(results["contenders"][side]["spec"]))
        return f'{tag(side)}<strong class="{side}">{label}</strong>'

    if len(leaders) > 1:
        return f"Empate en cabeza: {', '.join(name(side) for side in leaders)}"
    data = summary[leaders[0]]
    return (
        f"Primero: {name(leaders[0])} · "
        f"{e(data['tasks_solved'])}/{e(data['tasks_total'])} tareas · "
        f"{e(data['tests_passed'])}/{e(data['tests_total'])} tests"
    )


def build_matrix(results: dict, summary: dict, runs: int) -> str:
    """Tabla tarea x contendiente con los tests superados y el estado, no solo el color."""
    sides = sides_of(results)
    head = "".join(
        f'<th scope="col" class="contender {side}">{tag(side)}'
        f'<span class="spec">{e(_short_label(results["contenders"][side]["spec"]))}</span></th>'
        for side in sides
    )
    body = []
    for task in results["tasks"]:
        diff = f"<span>{e(task.get('difficulty'))}</span>" if task.get("difficulty") else ""
        cells = [f'<th scope="row" class="task">{e(task["title"])}{diff}</th>']
        for side in sides:
            attempts = task["results"].get(side, [])
            passed = sum(a["passed"] for a in attempts)
            total = sum(a["total"] for a in attempts)
            if not attempts:
                status = "sin hacer"
            elif len(attempts) >= runs and all(a["solved"] for a in attempts):
                status = "resuelta"
            else:
                other = {a["status"] for a in attempts} - {"ok"}
                status = ", ".join(STATUS_LABELS.get(x, x) for x in sorted(other)) or "no resuelta"
            label = f"{side.upper()}: {passed} de {total} tests superados en {task['title']}"
            ratio = passed / total if total else 0.0
            cells.append(
                f'<td class="cell"><span class="v {side}">{e(passed)}/{e(total)}</span>'
                f'<span class="status">{e(status)}</span>{svg_ratio_bar(ratio, side, label)}</td>'
            )
        body.append("    <tr>" + "".join(cells) + "</tr>")
    foot = "".join(
        f'<td class="cell"><span class="v {side}">{e(summary[side]["tests_passed"])}/'
        f"{e(summary[side]['tests_total'])}</span>"
        f'<span class="status">{e(summary[side]["tasks_solved"])}/'
        f"{e(summary[side]['tasks_total'])} tareas</span></td>"
        for side in sides
    )
    return (
        f'<thead><tr><th scope="col">Tarea</th>{head}</tr></thead>\n'
        f"<tbody>\n{chr(10).join(body)}\n</tbody>\n"
        f'<tfoot><tr><th scope="row">Total</th>{foot}</tr></tfoot>'
    )


def render_league(results: dict, summary: dict) -> str:
    sides = sides_of(results)
    runs = int(results.get("runs", 1))
    n_tasks = len(results["tasks"])
    labels = [_short_label(results["contenders"][side]["spec"]) for side in sides]
    fictitious = any(
        ((results["contenders"][side] or {}).get("price") or {}).get("fictitious") for side in sides
    )
    price_note = (
        "Precios ficticios de demostración, no reales."
        if fictitious
        else "Coste = entrada/1e6 × tarifa + salida/1e6 × tarifa · «sin datos» si no hay precio."
    )
    title = ' <span class="vs">vs</span> '.join(
        f'<span class="{side}">{e(label)}</span>' for side, label in zip(sides, labels, strict=True)
    )
    package = resources.files("modelduel.report")
    template = Template(package.joinpath("league.html").read_text("utf-8"))
    return template.substitute(
        css=package.joinpath("style.css").read_text("utf-8"),
        version=e(results.get("version", __version__)),
        page_title=e(" vs ".join(labels) + " · liga · modelduel"),
        date_human=e(fmt_date(results.get("created_at", ""))),
        date_iso=e(results.get("created_at", "")),
        title=title,
        lede=e(
            f"{len(sides)} contendientes · {plural(n_tasks, 'tarea', 'tareas')} · "
            f"{plural(runs, 'ejecución', 'ejecuciones')} por tarea · "
            f"límite de {results.get('timeout_s', 20):g} s por ejecución de tests"
        ),
        podium=build_podium(results, summary),
        ranking_caption=e(
            "Orden: tareas resueltas, después tests superados y después coste (menos es mejor). "
            "Los empates comparten posición. El tiempo es el que tarda el modelo en responder."
        ),
        ranking_rows=build_ranking(results, summary),
        metrics=build_metrics(results, summary, runs),
        warning=build_incomplete(results) + build_warning(runs),
        matrix_caption=e(
            "Tests superados por tarea" + (f", sumando {runs} ejecuciones." if runs > 1 else ".")
        ),
        matrix=build_matrix(results, summary, runs),
        details=build_details(results),
        price_note=e(price_note),
    )
