"""Informe Markdown: contenido y, sobre todo, contenido hostil (results.json es dato no fiable)."""

from __future__ import annotations

import copy
import re

import pytest

from modelduel.report import render_markdown, write_markdown
from modelduel.report.markdown import md_text
from modelduel.results import ALL_SIDES, summarize
from tests.test_report import RESULTS, _attempt

HOSTILE = [
    "a | b",
    "`code` ``x``",
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "[clic](http://evil.example/x)",
    "![img](http://evil.example/p.png)",
    "[ref]: http://evil.example",
    "@usuario y @org/equipo",
    "cierra #12 y org/repo#3",
    "visita www.evil.example o http://evil.example o https://evil.example",
    "correo a@evil.example mailto:a@evil.example",
    "&amp; &#60;script&#62; &copy;",
    "**negrita** _cursiva_ ~~tachado~~",
    "$\\sqrt{x}$",
    "\\ barra \\\\ doble \\| ya escapada",
    "linea1\nlinea2\r\n# titulo\n---\n- item\n1. uno\n> cita\n    sangrado",
    "# titulo",
    "---",
    "- item",
    "+ item",
    "= igual",
    "1. uno",
    "2) dos",
    "> cita",
    "| fila | extra |",
    "ctrl\x00\x07\x1b[31m rojo",
    "bidi ‮⁦ texto",
    "salto   unicode  ",
    "```\nfence\n```",
    "~~~\nfence\n~~~",
    "<!-- comentario -->",
    "GH-1 gh-2 Gh-33",
    "commit 3f786850e387550fdab836ed7e6dc881de23001b y 3f78685 y abcdef1234",
    "x" * 5000,
]


def _hostile_results(payload: str, n_sides: int = 2) -> dict:
    """Un results.json de ``n_sides`` contendientes con ``payload`` en todos los textos."""
    r = copy.deepcopy(RESULTS)
    r["version"] = payload
    r["created_at"] = payload
    r["contenders"]["a"]["spec"] = "x:" + payload
    r["contenders"]["b"]["spec"] = "y:" + payload
    r["contenders"]["a"]["price"] = {"currency": payload, "fictitious": False}
    r["tasks"][0]["title"] = payload
    r["tasks"][0]["id"] = payload
    r["tasks"][0]["difficulty"] = payload
    r["tasks"][0]["statement"] = payload
    for side in ALL_SIDES[2:n_sides]:
        r["contenders"][side] = {"spec": f"z{side}:" + payload, "price": None}
        r["tasks"][0]["results"][side] = copy.deepcopy(r["tasks"][0]["results"]["b"])
    for side in ALL_SIDES[:n_sides]:
        r["tasks"][0]["results"][side][0]["status"] = payload
        r["tasks"][0]["results"][side][0]["message"] = payload
        r["tasks"][0]["results"][side][0]["code"] = payload
        r["tasks"][0]["results"][side][0]["output"] = payload
    r["summary"] = summarize(r)
    return r


def _structure(md: str) -> list[str]:
    """Líneas que Markdown leería como título, lista, cita, bloque de código o regla."""
    block = r"\s*(#|>|[-+*] |\d+[.)] |```|~~~|=+$|-{3,}$)"
    return [line[:14] for line in md.splitlines() if re.match(block, line)]


def _sin_referencias_de_github(text: str) -> None:
    """GitHub enlaza GH-1 y los SHA (7 a 40 hexadecimales) tras leer el Markdown."""
    assert not re.search(r"(?i)\bgh-\d", text)
    assert not re.search("(?<!" + chr(0x200B) + r")\b[0-9a-fA-F]{7,40}\b", text)


def _stripped(text: str) -> str:
    """El texto sin los pares ``\\x`` (lo escapado ya no es sintaxis)."""
    return re.sub(r"\\.", "", text, flags=re.DOTALL)


# ---------------------------------------------------------------- md_text


@pytest.mark.parametrize("payload", HOSTILE)
def test_md_text_no_deja_sintaxis_activa(payload):
    out = md_text(payload)
    assert "\n" not in out and "\r" not in out
    bare = _stripped(out)
    for char in "<>[]!@$|`*_~&#()":
        assert char not in bare, (char, out)
    assert not re.search(r"www\.", bare, re.I)
    assert "://" not in bare
    _sin_referencias_de_github(out)
    # GitHub enlaza menciones, correos y referencias tras leer el Markdown: la barra no basta.
    assert not re.search("[@#](?!" + chr(0x200B) + ")", out)
    assert not any(
        ch in out for ch in map(chr, [*range(0, 9), *range(11, 32), 127, 0x202E, 0x2066])
    )
    assert not re.match(r"[-+=]|\d+[.)]\s", out)  # no empieza como lista, setext o título


def test_md_text_ida_y_vuelta():
    # Quitar el escapado devuelve el texto aplanado: no se pierde ni se inventa nada.
    for payload in ("a | b", "[x](http://y)", "@a #1 www.b.c", "1. uno", "- x", "a_b*c"):
        flat = re.sub(r"\s+", " ", payload).strip()
        assert re.sub(r"\\(.)", r"\1", md_text(payload).replace(chr(0x200B), "")) == flat


def test_md_text_recorta_sin_romper_un_escape():
    out = md_text("|" * 500, limit=10)
    assert out.endswith("…")
    assert _stripped(out[:-1]) == ""


def test_md_text_acepta_none_y_numeros():
    assert md_text(None) == ""
    assert md_text(12) == "12"


def test_md_text_conserva_texto_normal():
    assert md_text("Sumar números (fácil)") == "Sumar números \\(fácil\\)"
    assert md_text("0,0012 USD") == "0,0012 USD"


# ---------------------------------------------------------------- contenido


def test_informe_de_duelo_tiene_las_secciones():
    md = render_markdown({**RESULTS, "summary": summarize(RESULTS)})
    assert md.startswith("# Informe modelduel: alfa vs modelo-b")
    for section in ("## Marcador", "## Por tarea", "## Avisos"):
        assert section in md
    assert "**Veredicto:** gana **A**" in md
    assert "por tareas resueltas" in md
    assert "Una sola ejecución es una señal débil" in md
    assert "Precios ficticios de demostración" in md
    assert "| 1 | **A** replay:alfa |" in md
    assert md.endswith("\n")


def test_la_tabla_por_tarea_lleva_estado_y_tests_por_contendiente():
    r = copy.deepcopy(RESULTS)
    r["tasks"][0]["results"]["b"] = [_attempt(0, 0, status="timeout")]
    md = render_markdown(r)
    row = next(line for line in md.splitlines() if line.startswith("| Sumar"))
    assert "4/4" in row
    assert "0/0" in row and "tiempo agotado" in row


def test_veredicto_por_tests_y_empate():
    r = copy.deepcopy(RESULTS)
    r["tasks"][0]["results"]["b"] = [_attempt(4, 4, cost=None)]
    md = render_markdown(r)
    assert "empate en tareas resueltas y tests" in md
    r["tasks"][0]["results"]["a"] = [_attempt(2, 4)]
    r["tasks"][0]["results"]["b"] = [_attempt(3, 4)]
    assert "gana **B**" in render_markdown(r)
    assert "por tests superados (3 frente a 2 de A" in render_markdown(r)


def test_varias_ejecuciones_cambian_el_aviso():
    r = copy.deepcopy(RESULTS)
    r["runs"] = 3
    r["tasks"][0]["results"]["a"] = [_attempt(4, 4, run=i) for i in (1, 2, 3)]
    r["tasks"][0]["results"]["b"] = [_attempt(1, 4, run=i) for i in (1, 2, 3)]
    md = render_markdown(r)
    assert "Pocas ejecuciones siguen siendo una señal débil" in md
    assert "Una sola ejecución" not in md


def test_duelo_incompleto_se_avisa():
    r = copy.deepcopy(RESULTS)
    r["status"] = "in_progress"
    r["tasks"].append({**copy.deepcopy(r["tasks"][0]), "id": "dos", "results": {"a": [], "b": []}})
    md = render_markdown(r)
    assert "Duelo incompleto" in md and "--resume" in md


def test_liga_de_seis_con_una_columna_por_contendiente():
    r = copy.deepcopy(RESULTS)
    r["contenders"] = {
        side: {"spec": f"fake:m{side}", "price": None}
        for side in ALL_SIDES  # seis
    }
    r["tasks"][0]["results"] = {side: [_attempt(i, 4)] for i, side in enumerate(ALL_SIDES)}
    md = render_markdown(r)
    assert md.startswith("# Informe de liga modelduel")
    header = next(line for line in md.splitlines() if line.startswith("| Tarea"))
    assert header.count("|") == 8  # Tarea + seis letras
    assert "6 contendientes" in md


def test_write_markdown(tmp_path):
    path = write_markdown(RESULTS, tmp_path / "salida")
    assert path.name == "informe.md"
    assert path.read_text(encoding="utf-8").startswith("# Informe modelduel")


# ---------------------------------------------------------------- hostil


@pytest.mark.parametrize("n_sides", [2, 3, 6])
@pytest.mark.parametrize("payload", HOSTILE)
def test_un_results_hostil_no_inyecta_nada(payload, n_sides):
    md = render_markdown(_hostile_results(payload, n_sides))
    _sin_referencias_de_github(md)
    # Los únicos code spans son los nuestros (opciones de la línea de órdenes).
    bare = _stripped(md).replace("`--runs N`", "").replace("`--resume`", "")
    # Nuestras marcas no usan estos caracteres: si aparecen sin escapar, es inyección.
    for char in "<>[]!@$`":
        assert char not in bare, (char, payload)
    assert "://" not in bare.replace("https://bertmarti.github.io/modelduel/", "")
    assert not re.search(r"www\.", bare, re.I)
    # La estructura (títulos, listas, citas, bloques) es la de un informe con datos normales.
    assert _structure(md) == _structure(render_markdown(_hostile_results("normal", n_sides)))
    # Tablas: mismo número de barras sin escapar en cada fila de un bloque.
    block: list[int] = []
    for line in md.splitlines() + [""]:
        if line.startswith("|"):
            block.append(_stripped(line).count("|"))
        else:
            assert len(set(block)) <= 1, (payload, block)
            block = []


def test_un_titulo_con_barras_no_agrega_columnas():
    r = copy.deepcopy(RESULTS)
    r["tasks"][0]["title"] = "a | b | c"
    md = render_markdown(r)
    row = next(line for line in md.splitlines() if line.startswith("| a"))
    assert row.startswith("| a \\| b \\| c |")
    assert _stripped(row).count("|") == 4  # Tarea, A, B


def test_el_contenido_de_los_modelos_no_viaja_al_informe():
    r = copy.deepcopy(RESULTS)
    r["tasks"][0]["results"]["a"][0]["code"] = "SECRETO_CODIGO"
    r["tasks"][0]["results"]["a"][0]["output"] = "SECRETO_SALIDA"
    r["tasks"][0]["statement"] = "SECRETO_ENUNCIADO"
    md = render_markdown(r)
    assert "SECRETO" not in md


def test_resultados_con_tipos_inesperados_dan_error_no_markdown():
    r = copy.deepcopy(RESULTS)
    r["tasks"][0]["results"]["a"][0]["passed"] = "<b>x</b>"
    with pytest.raises((TypeError, ValueError, KeyError, AttributeError)):
        render_markdown(r)


def test_invisibles_de_direccion_y_juntador_se_quitan():
    for char in (0x061C, 0x2060, 0x202E, 0x2066, 0x200F):
        assert md_text("a" + chr(char) + "b") == "ab"


def test_gh_y_sha_no_se_enlazan_pero_se_leen_igual():
    out = md_text("GH-1 gh-22 3f786850e387550fdab836ed7e6dc881de23001b 3f78685")
    assert (
        out.replace(chr(0x200B), "")
        == "GH-1 gh-22 3f786850e387550fdab836ed7e6dc881de23001b 3f78685"
    )
    assert "1234" in md_text("Coste 1234") and chr(0x200B) not in md_text("Coste 1234")


def test_write_markdown_no_deja_a_cero_el_informe_previo_si_el_render_falla(tmp_path):
    previo = tmp_path / "informe.md"
    previo.write_text("informe bueno\n", encoding="utf-8")
    roto = copy.deepcopy(RESULTS)
    roto["tasks"][0]["results"]["a"][0]["status"] = ["x"]
    with pytest.raises((TypeError, ValueError, KeyError, AttributeError)):
        write_markdown(roto, tmp_path)
    assert previo.read_text(encoding="utf-8") == "informe bueno\n"
