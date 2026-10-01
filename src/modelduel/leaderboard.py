"""Clasificación pública: agrega ``results/*.json`` y genera una página estática sin JavaScript.

Cada archivo es el ``results.json`` de un duelo o una liga. El id de un duelo es el nombre del
archivo sin extensión; la fecha y la versión salen del propio JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from string import Template
from urllib.parse import quote

from modelduel import __version__
from modelduel.report import write_report
from modelduel.report.html import (
    e,
    fmt_cost,
    fmt_date,
    fmt_int,
    plural,
    svg_ratio_bar,
)
from modelduel.results import ResultsError, load_results, rank_sides, sides_of


@dataclass
class Duel:
    id: str
    results: dict


def load_duels(folder: Path) -> list[Duel]:
    """Todos los ``*.json`` de la carpeta, del más antiguo al más reciente."""
    folder = Path(folder)
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not files:
        raise ResultsError(
            f"No hay resultados en {folder}: copia ahí los results.json de tus duelos "
            "(un archivo por duelo o liga)."
        )
    duels = []
    for file in files:
        data = load_results(file)
        if data.get("status") == "in_progress":
            raise ResultsError(
                f"{file} es un duelo incompleto: termínalo con --resume antes de publicarlo."
            )
        duels.append(Duel(file.stem, data))
    return sorted(duels, key=lambda d: (d.results.get("created_at") or "", d.id))


def aggregate(duels: list[Duel]) -> dict[str, dict]:
    """Totales por contendiente (``proveedor:modelo``) sumando todos sus duelos."""
    models: dict[str, dict] = {}
    for duel in duels:
        results = duel.results
        for side in sides_of(results):
            spec = results["contenders"][side]["spec"]
            data = results["summary"][side]
            model = models.setdefault(
                spec,
                {
                    "spec": spec,
                    "duels": 0,
                    "tasks_solved": 0,
                    "tasks_total": 0,
                    "tests_passed": 0,
                    "tests_total": 0,
                    "costs": [],
                    "currencies": set(),
                    "fictitious": False,
                },
            )
            model["duels"] += 1
            for key in ("tasks_solved", "tasks_total", "tests_passed", "tests_total"):
                model[key] += data[key]
            model["costs"].append(data["cost"])
            model["currencies"].add(data["currency"])
            model["fictitious"] |= data["fictitious_price"]
    for model in models.values():
        costs, currencies = model.pop("costs"), model.pop("currencies")
        # El coste solo se suma si todos sus duelos tienen precio y en la misma moneda.
        known = all(c is not None for c in costs) and len(currencies) == 1
        model["cost"] = sum(costs) if known else None
        model["currency"] = next(iter(currencies)) if known else None
    return models


def _rate(part: int, total: int) -> float:
    return part / total if total else 0.0


def rank_models(models: dict[str, dict]) -> list[tuple[int, dict]]:
    """Clasificación ``[(posición, modelo)]`` con el criterio de los informes, pero por tasas.

    Un modelo con más duelos no gana por acumular: se compara la proporción de tareas resueltas,
    después la de tests y después el coste por tarea (solo si es comparable).
    """
    rates = {
        spec: {
            "tasks_solved": _rate(m["tasks_solved"], m["tasks_total"]),
            "tests_passed": _rate(m["tests_passed"], m["tests_total"]),
            "cost": None if m["cost"] is None else _rate(m["cost"], m["tasks_total"]),
            "currency": m["currency"],
        }
        for spec, m in models.items()
    }
    return [(position, models[spec]) for position, spec in rank_sides(rates)]


# ---------------------------------------------------------------- página


def _percent(part: int, total: int) -> str:
    return f"{round(100 * _rate(part, total))} %"


def _leaders(results: dict) -> str:
    leaders = [
        results["contenders"][side]["spec"]
        for position, side in rank_sides(results["summary"])
        if position == 1
    ]
    return leaders[0] if len(leaders) == 1 else "empate"


def build_ranking(models: dict[str, dict]) -> str:
    rows = []
    for position, model in rank_models(models):
        spec = model["spec"]
        tasks, tests = model["tasks_solved"], model["tasks_total"]
        rate = _rate(tasks, tests)
        label = f"{spec}: {tasks} de {tests} tareas resueltas ({_percent(tasks, tests)})"
        first = position == 1
        mark = (
            '<span class="mark" aria-hidden="true">●</span><span class="sr-only">(primero)</span>'
            if first
            else ""
        )
        cost = fmt_cost(model["cost"], model["currency"])
        if model["fictitious"] and model["cost"] is not None:
            cost += " (ficticio)"
        rows.append(
            f"    <tr{' class=first' if first else ''}>"
            f'<th scope="row" class="rk">{position}{mark}</th>'
            f'<td class="who">{e(spec)}</td>'
            f'<td class="rate"><span class="num">{_percent(tasks, tests)}</span>'
            f"{svg_ratio_bar(rate, 'a', label)}"
            f'<span class="sub">{e(tasks)}/{e(tests)} tareas</span></td>'
            f"<td>{e(_percent(model['tests_passed'], model['tests_total']))}"
            f'<span class="sub">{e(fmt_int(model["tests_passed"]))}/'
            f"{e(fmt_int(model['tests_total']))}</span></td>"
            f"<td>{e(model['duels'])}</td>"
            f"<td>{e(cost)}</td></tr>"
        )
    return "\n".join(rows)


def build_history(duels: list[Duel]) -> str:
    rows = []
    for duel in reversed(duels):
        results = duel.results
        specs = [results["contenders"][side]["spec"] for side in sides_of(results)]
        kind = "Duelo" if len(specs) == 2 else f"Liga de {len(specs)}"
        day = fmt_date(results.get("created_at", "")).split(" · ")[0]
        href = f"duelos/{quote(duel.id)}/index.html"
        rows.append(
            f'    <tr><th scope="row" class="when">{e(day)}'
            f'<span class="sub">v{e(results.get("version", "?"))}</span></th>'
            f'<td class="who">{e(duel.id)}<span class="sub">{e(kind)}</span></td>'
            f'<td class="who">{e(", ".join(specs))}</td>'
            f'<td class="who">{e(_leaders(results))}</td>'
            f'<td><a href="{e(href)}">Informe<span class="sr-only"> de {e(duel.id)}</span></a></td>'
            "</tr>"
        )
    return "\n".join(rows)


def render_leaderboard(duels: list[Duel]) -> str:
    models = aggregate(duels)
    ranking = rank_models(models)
    leader_names = [m["spec"] for position, m in ranking if position == 1]
    first = ranking[0][1]
    if len(leader_names) > 1:
        podium = f"Empate en cabeza: {', '.join(leader_names)}"
    else:
        podium = (
            f"Primero: {first['spec']} · {first['tasks_solved']}/{first['tasks_total']} tareas "
            f"({_percent(first['tasks_solved'], first['tasks_total'])})"
        )
    latest = max((d.results.get("created_at") or "") for d in duels)
    fictitious = any(m["fictitious"] for m in models.values())
    package = resources.files("modelduel.report")
    template = Template(package.joinpath("leaderboard.html").read_text("utf-8"))
    return template.substitute(
        css=package.joinpath("style.css").read_text("utf-8"),
        version=e(__version__),
        lede=e(
            f"{plural(len(models), 'modelo', 'modelos')} · {plural(len(duels), 'duelo', 'duelos')} "
            f"publicados · último: {fmt_date(latest).split(' · ')[0]}"
        ),
        podium=e(podium),
        ranking_rows=build_ranking(models),
        history_rows=build_history(duels),
        price_note=e(
            "Los costes de esta página son precios ficticios de demostración, no reales."
            if fictitious
            else "El coste suma los duelos de cada modelo; «sin datos» si falta un precio."
        ),
    )


def build_leaderboard(folder: Path, out: Path) -> Path:
    """Genera ``out/index.html`` y un informe por duelo en ``out/duelos/<id>/``."""
    duels = load_duels(folder)
    out = Path(out)
    for duel in duels:
        write_report(duel.results, out / "duelos" / duel.id)
    index = out / "index.html"
    index.write_text(render_leaderboard(duels), encoding="utf-8")
    return index
