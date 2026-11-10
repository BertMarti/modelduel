"""Enfrentamientos directos (v1.2.0): quién gana a quién, tarea a tarea.

Cálculo puro (``head_to_head``, ``aggregate_head_to_head``) y su HTML: un grafo SVG con un
nodo por modelo y una arista por pareja, más una matriz en tabla con la misma información
(la alternativa accesible y la única vista con más de ``MAX_GRAPH_NODES`` modelos).

Los informes no llevan JavaScript (su CSP no tiene ``script-src``): el resaltado al pasar el
ratón o al enfocar con el teclado y el panel de detalle son CSS (``:hover``, ``:focus`` y
``:has``). ``h2h_css`` genera esas reglas a partir de **índices enteros**, nunca de datos, y van
en el único ``<style>`` de la página, autorizado por su hash. Todo texto de ``results.json``
(títulos, ``spec``) es dato no fiable y pasa por ``_e``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from html import escape
from itertools import combinations
from typing import Literal

from modelduel.results import sides_of

# Con más nodos el grafo deja de leerse: solo se enseña la matriz.
MAX_GRAPH_NODES = 8
# Detalle por pareja en el panel: las primeras tareas y «… y N más».
MAX_MEETINGS_SHOWN = 12
# Largo máximo del nombre bajo cada nodo (el completo va en el panel y en la tabla).
NAME_CHARS = 16

Winner = Literal["i", "j"] | None

H2H_RULE = (
    "Gana la tarea quien la resuelve (todos sus tests en todas las ejecuciones) y, si la "
    "resuelven los dos o ninguno, quien supera más tests."
)


def _e(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def short_label(spec: str) -> str:
    """``proveedor:modelo`` → ``modelo`` (como en el resto del informe)."""
    kind, _, model = spec.partition(":")
    return model or kind


def clip(text: str, length: int) -> str:
    """Recorta a ``length`` caracteres con «…» (``results.py`` ya cambia los sustitutos sueltos)."""
    return text if len(text) <= length else text[: max(0, length - 1)] + "…"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ---------------------------------------------------------------- cálculo


def task_score(attempts: list[dict], runs: int) -> tuple[int, int] | None:
    """Puntuación de un contendiente en una tarea: ``(resuelta, tests superados)``.

    ``None`` si faltan ejecuciones (duelo incompleto): con menos de ``runs`` intentos el lado
    sumaría menos tests y saldría perjudicado, así que esa tarea no cuenta. Resuelta = todas las
    ejecuciones con todos los tests en verde (el mismo criterio que la clasificación); los tests
    se suman entre ejecuciones. Las tuplas se comparan en ese orden: resolver pesa más.
    """
    if not attempts or len(attempts) < runs:
        return None
    return int(all(a["solved"] for a in attempts)), sum(int(a["passed"]) for a in attempts)


@dataclass
class Meeting:
    """Una tarea entre dos modelos: tests de cada uno y quién la gana (``None``: empate)."""

    title: str
    passed_i: int
    total_i: int
    passed_j: int
    total_j: int
    winner: Winner


@dataclass
class Pair:
    """Balance de una pareja (``i < j``) en todas las tareas que han jugado los dos."""

    i: int
    j: int
    wins_i: int = 0
    wins_j: int = 0
    ties: int = 0
    meetings: list[Meeting] = field(default_factory=list)
    unknown: int = 0  # tareas en las que a alguno le faltan intentos: no cuentan

    @property
    def played(self) -> int:
        return self.wins_i + self.wins_j + self.ties

    @property
    def leader(self) -> int | None:
        """Índice del que gana más tareas; ``None`` si empatan o no han jugado."""
        if self.wins_i == self.wins_j:
            return None
        return self.i if self.wins_i > self.wins_j else self.j

    def add(self, title: str, attempts_i: list[dict], attempts_j: list[dict], runs: int) -> None:
        """Suma una tarea; sin intentos de alguno de los dos, solo cuenta como ``unknown``."""
        score_i, score_j = task_score(attempts_i, runs), task_score(attempts_j, runs)
        if score_i is None or score_j is None:
            self.unknown += 1
            return
        winner: Winner = None
        if score_i > score_j:
            winner, self.wins_i = "i", self.wins_i + 1
        elif score_j > score_i:
            winner, self.wins_j = "j", self.wins_j + 1
        else:
            self.ties += 1
        self.meetings.append(
            Meeting(
                title,
                score_i[1],
                sum(int(a["total"]) for a in attempts_i),
                score_j[1],
                sum(int(a["total"]) for a in attempts_j),
                winner,
            )
        )


@dataclass
class Node:
    """Un modelo del grafo: ``badge`` es su letra (informe) o su posición (clasificación) y
    ``css`` la clase de color (``a``…``f``, o ``n`` neutro)."""

    key: str
    label: str
    full: str
    badge: str
    css: str


@dataclass
class HeadToHead:
    nodes: list[Node]
    pairs: dict[tuple[int, int], Pair]

    def pair(self, i: int, j: int) -> Pair:
        return self.pairs[(i, j) if i < j else (j, i)]

    def versus(self, i: int, j: int) -> tuple[int, int, int]:
        """``(ganadas, perdidas, empatadas)`` de ``i`` frente a ``j``."""
        pair = self.pair(i, j)
        if pair.i == i:
            return pair.wins_i, pair.wins_j, pair.ties
        return pair.wins_j, pair.wins_i, pair.ties

    def record(self, i: int) -> tuple[int, int, int]:
        """Balance de ``i`` sumando a todos sus rivales: ``(ganadas, perdidas, empatadas)``."""
        won = lost = tied = 0
        for j in range(len(self.nodes)):
            if j != i:
                w, lo, t = self.versus(i, j)
                won, lost, tied = won + w, lost + lo, tied + t
        return won, lost, tied


def _empty_pairs(n: int) -> dict[tuple[int, int], Pair]:
    return {(i, j): Pair(i, j) for i, j in combinations(range(n), 2)}


def head_to_head(results: dict) -> HeadToHead:
    """Enfrentamientos de un duelo o una liga: un nodo por contendiente (A, B, C…)."""
    sides = sides_of(results)
    nodes = [
        Node(
            side,
            short_label(results["contenders"][side]["spec"]),
            results["contenders"][side]["spec"],
            side.upper(),
            side,
        )
        for side in sides
    ]
    runs = int(results.get("runs", 1))
    pairs = _empty_pairs(len(nodes))
    for task in results.get("tasks", []):
        by_side = task.get("results", {})
        for (i, j), pair in pairs.items():
            pair.add(str(task["title"]), by_side.get(sides[i], []), by_side.get(sides[j], []), runs)
    return HeadToHead(nodes, pairs)


def aggregate_head_to_head(
    duels: Iterable[tuple[str, dict]], specs: list[str], badges: list[str]
) -> HeadToHead:
    """Suma de todos los duelos publicados (clasificación): un nodo por ``spec``.

    ``specs`` da el orden de los nodos (el de la clasificación) y ``badges`` su etiqueta (la
    posición). Si un duelo repite un ``spec`` en dos lados, solo cuenta el primero.
    """
    shorts = [short_label(spec) for spec in specs]
    unique = len(set(shorts)) == len(shorts)  # replay:alfa y openai:alfa → nombre completo
    nodes = [
        Node(spec, short if unique else spec, spec, badge, "n")
        for spec, short, badge in zip(specs, shorts, badges, strict=True)
    ]
    index = {spec: k for k, spec in enumerate(specs)}
    pairs = _empty_pairs(len(nodes))
    for duel_id, results in duels:
        runs = int(results.get("runs", 1))
        # Un mismo spec en dos lados (results.json a mano; la CLI no lo deja) cuenta una vez:
        # solo su primer lado, para no sumar dos veces sus tareas contra un tercero.
        spec_of: dict[str, str] = {}
        for side in sides_of(results):
            spec = results["contenders"][side]["spec"]
            if spec not in spec_of.values():
                spec_of[side] = spec
        for left, right in combinations(spec_of, 2):
            i, j = index.get(spec_of[left]), index.get(spec_of[right])
            if i is None or j is None or i == j:
                continue
            if i > j:
                i, j, left, right = j, i, right, left
            for task in results.get("tasks", []):
                by_side = task.get("results", {})
                pairs[(i, j)].add(
                    f"{duel_id} · {task['title']}",
                    by_side.get(left, []),
                    by_side.get(right, []),
                    runs,
                )
    return HeadToHead(nodes, pairs)


# ---------------------------------------------------------------- textos


def _name(node: Node) -> str:
    """«A alfa» en los informes; en la clasificación «alfa (1.º)», para no leer «1 alfa»."""
    if node.css == "n":
        return f"{node.label} ({node.badge}.º)"
    return f"{node.badge} {node.label}"


def _score(pair: Pair) -> tuple[int, int]:
    """Marcador de la pareja con el que más gana delante («3–1»)."""
    if pair.leader == pair.j:
        return pair.wins_j, pair.wins_i
    return pair.wins_i, pair.wins_j


def _ties(n: int) -> str:
    return _plural(n, "empate", "empates")


def pair_sentence(h2h: HeadToHead, pair: Pair) -> str:
    """«A alfa contra B beta: gana A alfa, 3 tareas a 1, 1 empate»."""
    a, b = h2h.nodes[pair.i], h2h.nodes[pair.j]
    first, second = _score(pair)
    head = f"{_name(a)} contra {_name(b)}: "
    score = f"{_plural(first, 'tarea', 'tareas')} a {second}"
    if pair.leader is None:
        text = head + f"empate, {score}"
    else:
        text = head + f"gana {_name(h2h.nodes[pair.leader])}, {score}"
    return text + (f", {_ties(pair.ties)}" if pair.ties else "")


def _record_text(record: tuple[int, int, int]) -> str:
    won, lost, tied = record
    return f"{won}G · {lost}P · {tied}E"


def _record_sentence(record: tuple[int, int, int]) -> str:
    won, lost, tied = record
    return (
        f"{_plural(won, 'tarea ganada', 'tareas ganadas')}, "
        f"{_plural(lost, 'perdida', 'perdidas')} y {_plural(tied, 'empatada', 'empatadas')}"
    )


def _tag(node: Node) -> str:
    return f'<span class="tag {node.css}">{_e(node.badge)}</span>'


# ---------------------------------------------------------------- SVG

NODE_R = 26


@dataclass
class _Layout:
    """Lienzo del grafo: tamaño del viewBox, centro del polígono y centro de cada nodo."""

    width: int
    height: int
    cx: float
    cy: float
    points: list[tuple[float, float]]


def _layout(n: int) -> _Layout:
    """Dos en fila; de 3 en adelante, un polígono regular desde arriba en sentido horario.

    Con 4 o más los nombres van por fuera del polígono, a los lados, y el lienzo es más ancho.
    """
    if n == 2:
        return _Layout(560, 170, 280.0, 70.0, [(110.0, 70.0), (450.0, 70.0)])
    width, radius = (560, 170.0) if n == 3 else (760, 180.0)
    # Con 4 o más el polígono es mayor: el centro baja para que el nombre del nodo de arriba
    # (línea base en y - 58) quede con margen dentro del lienzo.
    cx, cy = width / 2, (250.0 if n == 3 else 262.0)
    points = []
    for k in range(n):
        angle = -math.pi / 2 + 2 * math.pi * k / n
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    # Alto justo para el nodo más bajo y sus dos líneas de texto (el triángulo no baja tanto).
    height = math.ceil(max(y for _x, y in points) + NODE_R + 64)
    return _Layout(width, height, cx, cy, points)


def _edge(h2h: HeadToHead, pair: Pair, points: list[tuple[float, float]], compact: bool) -> str:
    (x1, y1), (x2, y2) = points[pair.i], points[pair.j]
    length = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    gap = NODE_R + 4
    sx, sy, ex, ey = x1 + ux * gap, y1 + uy * gap, x2 - ux * gap, y2 - uy * gap
    coords = f'x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}"'
    leader = pair.leader
    tip = ""
    if leader is not None:
        # Punta junto al que pierde: la flecha va del que gana más tareas al que gana menos.
        tx, ty, dx, dy = (ex, ey, ux, uy) if leader == pair.i else (sx, sy, -ux, -uy)
        px, py = -dy, dx
        bx, by = tx - dx * 15, ty - dy * 15
        tip = (
            f'<polygon class="tip" points="{tx:.1f},{ty:.1f} {bx + px * 7:.1f},{by + py * 7:.1f} '
            f'{bx - px * 7:.1f},{by - py * 7:.1f}"/>'
        )
    css = "tie" if leader is None else f"win-{h2h.nodes[leader].css}"
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    first, second = _score(pair)
    score = f"{first}–{second}"
    if pair.ties and not compact:
        box_w, box_h, score_y = 124, 48, my - 10
        sub = f'<text class="sub" x="{mx:.1f}" y="{my + 12:.1f}">{_e(_ties(pair.ties))}</text>'
    else:
        # Con muchos modelos, solo el marcador (los empates están en el panel y en la tabla).
        box_w, box_h, score_y, sub = max(50, 13 * len(score) + 14), 30, my, ""
    return (
        f'<g class="h2h-edge h2h-p{pair.i}-{pair.j} x{pair.i} x{pair.j} {css}" tabindex="0" '
        f'role="img" aria-label="{_e(pair_sentence(h2h, pair))}">'
        f'<line class="hit" {coords}/><line class="ln" {coords}/>{tip}'
        f'<g class="lbl"><rect x="{mx - box_w / 2:.1f}" y="{my - box_h / 2:.1f}" '
        f'width="{box_w}" height="{box_h}" rx="3"/>'
        f'<text class="score" x="{mx:.1f}" y="{score_y:.1f}">{_e(score)}</text>{sub}</g></g>'
    )


def _label_place(layout: _Layout, x: float, y: float, n: int) -> tuple[float, float, float, str]:
    """Dónde van el nombre y el balance: ``(x, y del nombre, y del balance, text-anchor)``.

    Siempre por fuera del polígono, donde no pasan aristas: encima de los nodos de arriba,
    debajo de los de abajo y, con 4 o más, a un lado para los que están a los lados.
    """
    if n == 2:
        return x, y + 52, y + 72, "middle"
    dx = (x - layout.cx) / max(abs(x - layout.cx), abs(y - layout.cy), 1.0)
    if n >= 4 and abs(dx) > 0.35:
        side = 1 if dx > 0 else -1
        lift = -8 if y < layout.cy - 1 else 8 if y > layout.cy + 1 else 0
        return x + side * (NODE_R + 12), y - 4 + lift, y + 16 + lift, "start" if side > 0 else "end"
    if y < layout.cy - 1:
        return x, y - 58, y - 38, "middle"
    return x, y + 52, y + 72, "middle"


def _node(h2h: HeadToHead, i: int, layout: _Layout) -> str:
    node = h2h.nodes[i]
    x, y = layout.points[i]
    record = h2h.record(i)
    tx, name_y, rec_y, anchor = _label_place(layout, x, y, len(h2h.nodes))
    label = f"{_name(node)}: {_record_sentence(record)} en enfrentamientos directos"
    text = f'x="{tx:.1f}" text-anchor="{anchor}"'
    chars = NAME_CHARS - 1 if len(h2h.nodes) >= 4 else NAME_CHARS  # letra mayor en el lienzo ancho
    return (
        f'<g class="h2h-node h2h-n{i} c-{node.css}" tabindex="0" role="img" '
        f'aria-label="{_e(label)}">'
        f'<circle class="ring" cx="{x:.1f}" cy="{y:.1f}" r="{NODE_R + 7}"/>'
        f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="{NODE_R}"/>'
        f'<text class="badge" x="{x:.1f}" y="{y:.1f}">{_e(node.badge)}</text>'
        f'<text class="name" {text} y="{name_y:.1f}">{_e(clip(node.label, chars))}</text>'
        f'<text class="rec" {text} y="{rec_y:.1f}">{_e(_record_text(record))}</text></g>'
    )


_GRAPH_LABEL = (
    "Grafo de enfrentamientos directos: un nodo por modelo y una flecha por pareja. "
    "La misma información está en la matriz de enfrentamientos."
)


def _svg(h2h: HeadToHead) -> str:
    n = len(h2h.nodes)
    layout = _layout(n)
    dense = n >= 4  # con 4 o más, las diagonales se cruzan en el centro
    edges = [_edge(h2h, pair, layout.points, dense) for pair in h2h.pairs.values() if pair.played]
    nodes = [_node(h2h, i, layout) for i in range(n)]
    return (
        f'<svg class="h2h-graph{" dense" if dense else ""}" '
        f'viewBox="0 0 {layout.width} {layout.height}" role="group" '
        f'aria-label="{_GRAPH_LABEL}"><title>{_GRAPH_LABEL}</title>'
        + "".join(edges)
        + "".join(nodes)
        + "</svg>"
    )


# Leyenda en HTML y CSS (sin SVG: los iconos son decorativos y el texto lo dice todo).
_LEGEND = (
    '<ul class="h2h-legend">'
    '<li><span class="lg-win" aria-hidden="true"></span>gana más tareas '
    "(la flecha apunta al que pierde)</li>"
    '<li><span class="lg-tie" aria-hidden="true"></span>empate en tareas ganadas</li>'
    '<li><span class="lg-box">3–1</span>tareas ganadas–perdidas de la pareja</li>'
    '<li><span class="lg-box">2G · 1P · 0E</span>balance de cada modelo con todos sus rivales'
    "</li></ul>"
)


def _panel(h2h: HeadToHead) -> str:
    """Detalle que el CSS enseña al pasar el ratón o enfocar (redundante: ``aria-hidden``)."""
    bits = [
        '<p class="h2h-info h2h-hint">Pasa el ratón por un modelo o una flecha, recórrelos '
        "con el tabulador o tócalos para ver el detalle.</p>"
    ]
    for i, node in enumerate(h2h.nodes):
        rivals = []
        for j, other in enumerate(h2h.nodes):
            if i == j:
                continue
            w, lo, t = h2h.versus(i, j)
            if not w + lo + t:
                verdict = "sin enfrentamientos"
            else:
                verb = "gana" if w > lo else "pierde" if lo > w else "empata"
                verdict = f"{verb} {w}–{lo}" + (f" · {_ties(t)}" if t else "")
            rivals.append(f"<li>contra {_tag(other)}{_e(other.label)}: {_e(verdict)}</li>")
        bits.append(
            f'<div class="h2h-info h2h-info-n{i}"><p class="h2h-who">{_tag(node)}'
            f"{_e(node.full)}</p><p>{_e(_record_sentence(h2h.record(i)))}</p>"
            f"<ul>{''.join(rivals)}</ul></div>"
        )
    for (i, j), pair in h2h.pairs.items():
        if not pair.played:
            continue
        a, b = h2h.nodes[i], h2h.nodes[j]
        rows = []
        for meeting in pair.meetings[:MAX_MEETINGS_SHOWN]:
            if meeting.winner is None:
                result = "empate"
            else:
                result = f"gana {(a if meeting.winner == 'i' else b).badge}"
            rows.append(
                f'<li><span class="h2h-task">{_e(meeting.title)}</span> '
                f"{_e(a.badge)} {meeting.passed_i}/{meeting.total_i} · "
                f"{_e(b.badge)} {meeting.passed_j}/{meeting.total_j} · {_e(result)}</li>"
            )
        hidden = len(pair.meetings) - MAX_MEETINGS_SHOWN
        if hidden > 0:
            rows.append(f"<li>… y {_plural(hidden, 'tarea', 'tareas')} más</li>")
        if pair.unknown:
            rows.append(
                f"<li>{_plural(pair.unknown, 'tarea', 'tareas')} sin datos de alguno "
                "(no cuentan)</li>"
            )
        bits.append(
            f'<div class="h2h-info h2h-info-p{i}-{j}"><p class="h2h-who">{_tag(a)}'
            f'{_e(a.label)} <span class="muted">vs</span> {_tag(b)}{_e(b.label)}</p>'
            f"<p>{_e(pair_sentence(h2h, pair))}</p><ul>{''.join(rows)}</ul></div>"
        )
    return '<div class="h2h-panel" aria-hidden="true">' + "".join(bits) + "</div>"


# ---------------------------------------------------------------- tabla


def _cell(h2h: HeadToHead, i: int, j: int) -> str:
    if i == j:
        return (
            '<td class="self"><span aria-hidden="true">—</span>'
            '<span class="sr-only">mismo modelo</span></td>'
        )
    w, lo, t = h2h.versus(i, j)
    if not w + lo + t:
        return (
            '<td class="none"><span aria-hidden="true">·</span>'
            '<span class="sr-only">sin enfrentamientos</span></td>'
        )
    glyph, verb = ("▲", "gana") if w > lo else ("▼", "pierde") if lo > w else ("=", "empata")
    ties = f" · {_ties(t)}" if t else ""
    me, other = h2h.nodes[i].label, h2h.nodes[j].label
    tasks = _plural(w, "tarea", "tareas")
    spoken = f"{me} {verb} frente a {other}: {tasks} a {lo}{', ' + _ties(t) if t else ''}"
    return (
        f'<td class="{verb}"><span class="v" aria-hidden="true">{w}–{lo}</span>'
        f'<span class="st" aria-hidden="true">{glyph} {verb}{_e(ties)}</span>'
        f'<span class="sr-only">{_e(spoken)}</span></td>'
    )


def _matrix(h2h: HeadToHead) -> str:
    heads = "".join(
        f'<th scope="col" class="who">{_tag(node)}<span class="nm">{_e(node.label)}</span></th>'
        for node in h2h.nodes
    )
    body = []
    for i, node in enumerate(h2h.nodes):
        cells = [
            f'<th scope="row" class="who">{_tag(node)}{_e(node.label)}'
            f'<span class="spec">{_e(node.full)}</span></th>'
        ]
        cells += [_cell(h2h, i, j) for j in range(len(h2h.nodes))]
        record = h2h.record(i)
        cells.append(
            f'<td class="bal"><span class="v" aria-hidden="true">{_record_text(record)}</span>'
            f'<span class="sr-only">{_e(_record_sentence(record))}</span></td>'
        )
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="table-wrap" tabindex="0" role="region" '
        'aria-label="Matriz de enfrentamientos, tabla desplazable">'
        '<table class="h2h-matrix"><caption>Matriz de enfrentamientos. Cada celda: tareas que '
        "gana el modelo de la fila frente al de la columna, guion, las que pierde; debajo, ▲ si "
        "gana la pareja, ▼ si la pierde, = si empatan, y los empates de tareas. Balance: "
        "G ganadas, P perdidas y E empatadas con todos sus rivales.</caption>"
        f'<thead><tr><th scope="col">Modelo</th>{heads}<th scope="col">Balance</th></tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


# ---------------------------------------------------------------- API


def render_h2h(h2h: HeadToHead, *, intro: str) -> str:
    """Contenido de la sección «Enfrentamientos directos» (la plantilla pone el título)."""
    n = len(h2h.nodes)
    parts = [f'<p class="h2h-intro">{_e(intro)}</p>']
    if n < 2:
        # Sin parejas no hay nada que enfrentar (p. ej. una clasificación con un solo modelo).
        parts.append(
            '<p class="h2h-many">Hacen falta al menos dos modelos para ver enfrentamientos '
            "directos.</p>"
        )
        return "".join(parts)
    if n <= MAX_GRAPH_NODES:
        parts.append(_LEGEND)
        parts.append(f'<div class="h2h-stage">{_svg(h2h)}{_panel(h2h)}</div>')
    elif n > MAX_GRAPH_NODES:
        parts.append(
            f'<p class="h2h-many">Con más de {MAX_GRAPH_NODES} modelos el grafo no se dibuja '
            "porque no se podría leer: la matriz tiene todos los enfrentamientos.</p>"
        )
    parts.append(_matrix(h2h))
    return "".join(parts)


_ACTIVE = ":is(.h2h-node,.h2h-edge):is(:hover,:focus)"
_ON = "{--h2h-dim:initial;--h2h-w:5;--h2h-lbl:visible}"


def h2h_css(n: int) -> str:
    """Reglas de resaltado y del panel para ``n`` nodos (solo índices; ``""`` sin grafo).

    El color de cada arista sale de ``--h2h-col``; mientras hay algo activo, ``--h2h-dim``
    atenúa el resto (sin ``opacity``, regla del diseño) y lo activo lo anula con ``initial``,
    con lo que ``var()`` vuelve a su alternativa (el color propio). Lo activo va después que
    el atenuado (misma especificidad: gana el orden).
    """
    if not 2 <= n <= MAX_GRAPH_NODES:
        return ""
    rules = [
        "/* Enfrentamientos directos: reglas por índice (generadas en h2h.py) */",
        f".h2h:has({_ACTIVE}) .h2h-hint{{display:none}}",
        f".h2h-graph:has({_ACTIVE}) .h2h-edge{{--h2h-dim:var(--h2h-dimmed)}}",
        f".h2h-graph:has(.h2h-edge:is(:hover,:focus)) .h2h-edge:is(:hover,:focus){_ON}",
    ]
    for i in range(n):
        node = f".h2h-n{i}:is(:hover,:focus)"
        rules.append(f".h2h:has({node}) .h2h-info-n{i}{{display:block}}")
        rules.append(f".h2h-graph:has({node}) .x{i}{_ON}")
    for i, j in combinations(range(n), 2):
        edge = f".h2h-p{i}-{j}:is(:hover,:focus)"
        rules.append(f".h2h:has({edge}) .h2h-info-p{i}-{j}{{display:block}}")
        rules.append(f".h2h-graph:has({edge}) :is(.h2h-n{i},.h2h-n{j}){{--h2h-ring:var(--muted)}}")
    return "\n".join(rules) + "\n"
