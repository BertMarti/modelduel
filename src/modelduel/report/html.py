"""Informe HTML autocontenido: ``string.Template``, CSS en línea, SVG en línea y sin JavaScript."""

from __future__ import annotations

from datetime import datetime
from html import escape
from importlib import resources
from string import Template

from modelduel import __version__
from modelduel.results import costs_comparable, decide, sides_of

STATUS_LABELS = {
    "ok": "tests ejecutados",
    "no_code": "sin bloque de código",
    "import_error": "no se pudo importar",
    "timeout": "tiempo agotado",
    "error": "error al ejecutar",
    "provider_error": "error del proveedor",
}

# Duelo de dos: A a la izquierda, B a la derecha. Con más contendientes se usa la liga.
VERSUS = ("a", "b")

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


# ---------------------------------------------------------------- formato


def e(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def fmt_int(value: int | None) -> str:
    if value is None:
        return "sin datos"
    return f"{value:,}".replace(",", ".")


def fmt_seconds(value: float | None) -> str:
    if value is None:
        return "sin datos"
    value = round(value, 1)  # sin esto, 119,97 s salía como «1 min 60,0 s»
    if value >= 60:
        minutes, seconds = divmod(value, 60)
        return f"{int(minutes)} min {seconds:04.1f} s".replace(".", ",")
    return f"{value:.1f} s".replace(".", ",")


def fmt_cost(value: float | None, currency: str | None) -> str:
    if value is None:
        return "sin datos"
    currency = currency or ""
    if value == 0:
        text = "0"
    elif value < 0.0001:
        text = "<0,0001"
    elif value < 1:
        text = f"{value:.4f}".replace(".", ",")
    else:
        text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {currency}".strip()


def fmt_tokens(inp: int | None, out: int | None) -> str:
    if inp is None and out is None:
        return "sin datos"
    return f"{fmt_int(inp)} / {fmt_int(out)}"


def fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)  # texto plano: lo escapa quien lo inserta
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year} · {dt:%H:%M} UTC"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ---------------------------------------------------------------- SVG


def svg_versus_bar(value_a: float | None, value_b: float | None, label: str) -> str:
    """Barras enfrentadas desde el centro: A crece a la izquierda, B a la derecha."""
    a = value_a or 0.0
    b = value_b or 0.0
    top = max(a, b) or 1.0
    half = 200
    gap = 2
    len_a = (half - gap) * a / top
    len_b = (half - gap) * b / top
    return (
        f'<svg viewBox="0 0 400 6" preserveAspectRatio="none" role="img" aria-label="{e(label)}">'
        f"<title>{e(label)}</title>"
        f'<rect class="track" x="0" y="2.5" width="400" height="1" fill="#2a2a2f"/>'
        f'<rect class="fill-a" x="{half - gap - len_a:.2f}" y="0" width="{len_a:.2f}" height="6"/>'
        f'<rect class="fill-b" x="{half + gap:.2f}" y="0" width="{len_b:.2f}" height="6"/>'
        "</svg>"
    )


def svg_ratio_bar(ratio: float, side: str, label: str) -> str:
    """Barra fina horizontal (0-100 %) sobre una pista de 1 px."""
    width = max(0.0, min(ratio, 1.0)) * 100
    return (
        f'<svg viewBox="0 0 100 6" preserveAspectRatio="none" role="img" aria-label="{e(label)}">'
        f"<title>{e(label)}</title>"
        '<rect class="track" x="0" y="2.5" width="100" height="1" fill="#2a2a2f"/>'
        f'<rect class="fill-{side}" x="0" y="0" width="{width:.2f}" height="6"/>'
        "</svg>"
    )


def task_chart(tasks: list[dict]) -> str:
    """Una fila por tarea con dos barras finas (A arriba, B abajo) de tests superados."""
    rows = []
    for task in tasks:
        lines = []
        for side in VERSUS:
            attempts = task["results"].get(side, [])
            passed = sum(a["passed"] for a in attempts)
            total = sum(a["total"] for a in attempts)
            ratio = passed / total if total else 0.0
            label = f"{side.upper()}: {passed} de {total} tests superados"
            lines.append(
                f'<div class="bar-line">{svg_ratio_bar(ratio, side, label)}'
                f'<span class="{side}">{passed}/{total}</span></div>'
            )
        diff = f"<span>{e(task.get('difficulty'))}</span>" if task.get("difficulty") else ""
        rows.append(
            f'<div class="bar-row"><div class="bar-title">{e(task["title"])}{diff}</div>'
            + "".join(lines)
            + "</div>"
        )
    return '<div class="bars">' + "".join(rows) + "</div>"


# ---------------------------------------------------------------- bloques


def _winner(a: float | None, b: float | None, lower_is_better: bool) -> str | None:
    if a is None or b is None or a == b:
        return None
    if lower_is_better:
        return "a" if a < b else "b"
    return "a" if a > b else "b"


def metric_row(
    label: str,
    shown: tuple[str, str],
    raw: tuple[float | None, float | None],
    lower_is_better: bool = False,
    subs: tuple[str, str] = ("", ""),
    hint: str = "",
) -> str:
    winner = _winner(raw[0], raw[1], lower_is_better)
    cells = []
    for idx, side in enumerate(VERSUS):
        classes = ["val", side]
        if side == "b":
            classes.append("b-side")
        mark = ""
        if winner == side:
            classes.append("win")
            mark = (
                '<span class="mark" aria-hidden="true">●</span><span class="sr-only">(mejor)</span>'
            )
        elif winner is not None:
            classes.append("lose")
        sub = f'<span class="sub">{e(subs[idx])}</span>' if subs[idx] else ""
        num = f'<span class="num">{e(shown[idx])}</span>'
        value = f"{mark}{num}" if side == "b" else f"{num}{mark}"
        cells.append(f'<div class="{" ".join(classes)}">{value}{sub}</div>')
    hint_html = f'<div class="hint">{e(hint)}</div>' if hint else ""
    bar = svg_versus_bar(raw[0], raw[1], f"{label}: A {shown[0]}, B {shown[1]}")
    return (
        f'<div class="metric">{cells[0]}'
        f'<div class="mid"><div class="label">{e(label)}</div>{bar}{hint_html}</div>'
        f"{cells[1]}</div>"
    )


def build_metrics(summary: dict, runs: int = 1) -> str:
    sa, sb = summary["a"], summary["b"]
    summed = f"suma de {runs} ejecuciones" if runs > 1 else ""
    rows = [
        metric_row(
            "Tareas resueltas",
            (
                f"{sa['tasks_solved']}/{sa['tasks_total']}",
                f"{sb['tasks_solved']}/{sb['tasks_total']}",
            ),
            (sa["tasks_solved"], sb["tasks_solved"]),
            hint="todos los tests en todas las ejecuciones",
        ),
        metric_row(
            "Tests superados",
            (
                f"{sa['tests_passed']}/{sa['tests_total']}",
                f"{sb['tests_passed']}/{sb['tests_total']}",
            ),
            (sa["tests_passed"], sb["tests_passed"]),
            hint=summed,
        ),
        metric_row(
            "Tiempo del modelo",
            (fmt_seconds(sa["latency_s"]), fmt_seconds(sb["latency_s"])),
            (sa["latency_s"], sb["latency_s"]),
            lower_is_better=True,
            subs=(
                f"tests: {fmt_seconds(sa['test_time_s'])}",
                f"tests: {fmt_seconds(sb['test_time_s'])}",
            ),
            hint="menos es mejor" + (f" · {summed}" if summed else ""),
        ),
        metric_row(
            "Tokens",
            (fmt_int(_total_tokens(sa)), fmt_int(_total_tokens(sb))),
            (_total_tokens(sa), _total_tokens(sb)),
            lower_is_better=True,
            subs=(
                f"entrada {fmt_int(sa['input_tokens'])} · salida {fmt_int(sa['output_tokens'])}",
                f"entrada {fmt_int(sb['input_tokens'])} · salida {fmt_int(sb['output_tokens'])}",
            ),
            hint="menos es mejor",
        ),
    ]
    if runs > 1:
        rows.insert(
            1,
            metric_row(
                "Intentos resueltos",
                (
                    f"{sa['attempts_solved']}/{sa['attempts_total']}",
                    f"{sb['attempts_solved']}/{sb['attempts_total']}",
                ),
                (sa["attempts_solved"], sb["attempts_solved"]),
                hint="ejecuciones con todos los tests en verde",
            ),
        )
    same_currency = sa["currency"] == sb["currency"]
    cost_hint = "menos es mejor"
    if sa["fictitious_price"] or sb["fictitious_price"]:
        cost_hint = "precios ficticios de demostración"
    elif not same_currency and sa["cost"] is not None and sb["cost"] is not None:
        cost_hint = "monedas distintas: no comparables"
    rows.append(
        metric_row(
            "Coste estimado",
            (fmt_cost(sa["cost"], sa["currency"]), fmt_cost(sb["cost"], sb["currency"])),
            (sa["cost"], sb["cost"]) if same_currency else (None, None),
            lower_is_better=True,
            hint=cost_hint,
        )
    )
    return "\n".join(rows)


def _total_tokens(side: dict) -> int | None:
    if side["input_tokens"] is None and side["output_tokens"] is None:
        return None
    return (side["input_tokens"] or 0) + (side["output_tokens"] or 0)


def _side_task_totals(attempts: list[dict], currency: str | None) -> dict[str, str]:
    passed = sum(a["passed"] for a in attempts)
    total = sum(a["total"] for a in attempts)
    latencies = [a.get("latency_s") for a in attempts]
    inputs = [a.get("input_tokens") for a in attempts]
    outputs = [a.get("output_tokens") for a in attempts]
    costs = [a.get("cost") for a in attempts]
    statuses = {a["status"] for a in attempts} - {"ok"}
    status = ", ".join(STATUS_LABELS.get(s, s) for s in sorted(statuses))
    return {
        "tests": f"{passed}/{total}",
        "status": status,
        "time": fmt_seconds(sum(x for x in latencies if x is not None))
        if any(x is not None for x in latencies)
        else "sin datos",
        "tokens": fmt_tokens(
            sum(x for x in inputs if x is not None) if any(x is not None for x in inputs) else None,
            sum(x for x in outputs if x is not None)
            if any(x is not None for x in outputs)
            else None,
        ),
        "cost": fmt_cost(sum(costs), currency)
        if costs and all(c is not None for c in costs)
        else "sin datos",
    }


def build_table_rows(results: dict) -> str:
    rows = []
    currencies = {
        side: ((results["contenders"].get(side) or {}).get("price") or {}).get("currency")
        for side in VERSUS
    }
    for task in results["tasks"]:
        t = {side: _side_task_totals(task["results"][side], currencies[side]) for side in VERSUS}
        diff = f"<span>{e(task.get('difficulty'))}</span>" if task.get("difficulty") else ""
        cells = [f'<th scope="row" class="task">{e(task["title"])}{diff}</th>']
        for side in VERSUS:
            status = (
                f'<span class="status">{e(t[side]["status"])}</span>' if t[side]["status"] else ""
            )
            cells.append(f'<td class="mono {side}">{e(t[side]["tests"])}{status}</td>')
        for key in ("time", "tokens", "cost"):
            for side in VERSUS:
                cells.append(f"<td>{e(t[side][key])}</td>")
        rows.append("    <tr>" + "".join(cells) + "</tr>")
    return "\n".join(rows)


def build_details(results: dict) -> str:
    runs = results.get("runs", 1)
    sides = sides_of(results)
    duo_class = "duo" if len(sides) <= 2 else "duo league"
    blocks = []
    for task in results["tasks"]:
        summary_bits = []
        for side in sides:
            attempts = task["results"][side]
            passed = sum(a["passed"] for a in attempts)
            total = sum(a["total"] for a in attempts)
            summary_bits.append(f'<span class="{side}">{side.upper()} {passed}/{total}</span>')
        columns = []
        for side in sides:
            spec = results["contenders"][side]["spec"]
            attempts_html = [_attempt_html(attempt, runs) for attempt in task["results"][side]]
            columns.append(
                f'<div><div class="side-head {side}">{side.upper()} · {e(spec)}</div>'
                + "".join(attempts_html)
                + "</div>"
            )
        blocks.append(
            "<details>"
            f"<summary><span>{e(task['title'])}</span>"
            f'<span class="muted">{e(task["id"])}</span><span class="spacer"></span>'
            + " ".join(summary_bits)
            + "</summary>"
            '<div class="detail-body">'
            f'<div class="statement">{e(task.get("statement", ""))}</div>'
            f'<div class="{duo_class}">{"".join(columns)}</div>'
            "</div></details>"
        )
    return "\n".join(blocks)


def _attempt_html(attempt: dict, runs: int) -> str:
    head = []
    if runs > 1:
        head.append(f"<strong>Ejecución {e(attempt.get('run', '?'))}</strong>")
    head.append(f"{e(attempt['passed'])}/{e(attempt['total'])} tests")
    if attempt["status"] == "ok":
        failing = attempt["failed"] + attempt["errors"]
        head.append("resuelta" if attempt["solved"] else plural(failing, "falla", "fallan"))
    else:
        head.append(e(STATUS_LABELS.get(attempt["status"], attempt["status"])))
    if attempt.get("latency_s") is not None:
        head.append(fmt_seconds(attempt["latency_s"]))
    parts = [f'<div class="attempt"><div class="attempt-head">{" · ".join(head)}</div>']
    if attempt.get("message"):
        parts.append(f'<p class="msg">{e(attempt["message"])}</p>')
    if attempt.get("code"):
        parts.append(f'<pre><code class="language-python">{e(attempt["code"])}</code></pre>')
    elif attempt.get("response"):
        parts.append(f"<pre>{e(attempt['response'])}</pre>")
    if attempt.get("output"):
        parts.append(
            '<details class="out"><summary>Salida de pytest</summary>'
            f"<pre>{e(attempt['output'])}</pre></details>"
        )
    parts.append("</div>")
    return "".join(parts)


def build_warning(runs: int) -> str:
    if runs <= 1:
        return (
            "<strong>Una sola ejecución es una señal débil.</strong> "
            "Los modelos no son deterministas: la misma pregunta puede dar otra respuesta mañana. "
            "Repite el duelo con <code>--runs N</code> y con tareas de tu propio trabajo antes de "
            "sacar conclusiones."
        )
    return (
        "<strong>Pocas ejecuciones siguen siendo una señal débil.</strong> "
        f"Aquí hay {runs} ejecuciones por tarea, mejor que una, pero sigue siendo una muestra "
        "pequeña. Usa tareas de tu propio trabajo y mira el código, no solo el marcador."
    )


def build_incomplete(results: dict) -> str:
    """Aviso de un duelo cortado a medias (vacío si está completo)."""
    if results.get("status") != "in_progress":
        return ""
    sides = sides_of(results)
    expected = len(results["tasks"]) * int(results.get("runs", 1)) * len(sides)
    done = sum(len(t["results"].get(side, [])) for t in results["tasks"] for side in sides)
    return (
        f"<strong>Duelo incompleto: {done} de {expected} intentos.</strong> "
        "El marcador solo cuenta lo hecho hasta ahora. Continúa con <code>--resume</code> "
        "y la misma configuración.<br><br>"
    )


def _verdict(summary: dict, runs: int = 1) -> str:
    """Quién gana y qué criterio decide: el mismo orden que la clasificación (``decide``)."""
    winner, criterion = decide(summary)
    summed = f" (suma de {runs} ejecuciones)" if runs > 1 else ""
    if winner is None:
        if costs_comparable(summary):
            return "empate en tareas resueltas, tests y coste" + summed
        return "empate en tareas resueltas y tests (sin coste comparable)" + summed
    loser = "b" if winner == "a" else "a"
    win, lose = summary[winner], summary[loser]
    who = f'gana <strong class="{winner}">{winner.upper()}</strong>'
    if criterion == "tasks":
        return f"{who} por tareas resueltas ({win['tasks_solved']} frente a {lose['tasks_solved']})"
    if criterion == "tests":
        return (
            f"{who} por tests superados ({win['tests_passed']} frente a {lose['tests_passed']}, "
            f"con las mismas tareas resueltas){summed}"
        )
    return (
        f"{who} por coste ({fmt_cost(win['cost'], win['currency'])} frente a "
        f"{fmt_cost(lose['cost'], lose['currency'])}, con las mismas tareas resueltas y tests)"
    )


def _short_label(spec: str) -> str:
    kind, _, model = spec.partition(":")
    return model or kind


# ---------------------------------------------------------------- API


def render_versus(results: dict, summary: dict) -> str:
    """Informe de un duelo de dos: A a la izquierda y B a la derecha."""
    spec_a = results["contenders"]["a"]["spec"]
    spec_b = results["contenders"]["b"]["spec"]
    runs = int(results.get("runs", 1))
    n_tasks = len(results["tasks"])
    fictitious = [
        side
        for side in VERSUS
        if ((results["contenders"][side] or {}).get("price") or {}).get("fictitious")
    ]
    price_note = (
        "Precios ficticios de demostración, no reales."
        if fictitious
        else "Coste = entrada/1e6 × tarifa + salida/1e6 × tarifa · «sin datos» si no hay precio."
    )
    template = Template(
        resources.files("modelduel.report").joinpath("template.html").read_text("utf-8")
    )
    return template.substitute(
        css=resources.files("modelduel.report").joinpath("style.css").read_text("utf-8"),
        version=e(results.get("version", __version__)),
        page_title=e(f"{_short_label(spec_a)} vs {_short_label(spec_b)} · modelduel"),
        date_human=e(fmt_date(results.get("created_at", ""))),
        date_iso=e(results.get("created_at", "")),
        label_a=e(_short_label(spec_a)),
        label_b=e(_short_label(spec_b)),
        spec_a=e(spec_a),
        spec_b=e(spec_b),
        lede=e(
            f"{plural(n_tasks, 'tarea', 'tareas')} · "
            f"{plural(runs, 'ejecución', 'ejecuciones')} por tarea · "
            f"límite de {results.get('timeout_s', 20):g} s por ejecución de tests"
        ),
        score_a=summary["a"]["tests_passed"],
        score_b=summary["b"]["tests_passed"],
        score_total_a=summary["a"]["tests_total"],
        score_total_b=summary["b"]["tests_total"],
        verdict=_verdict(summary, runs),
        metrics=build_metrics(summary, runs),
        warning=build_incomplete(results) + build_warning(runs),
        chart=task_chart(results["tasks"]),
        table_caption=e(
            "Totales por tarea"
            + (f" sumando {runs} ejecuciones." if runs > 1 else ".")
            + " El tiempo es el que tarda el modelo en responder."
        ),
        table_rows=build_table_rows(results),
        details=build_details(results),
        price_note=e(price_note),
    )
