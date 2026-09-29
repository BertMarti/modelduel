import time

from modelduel.runner import MAX_OUTPUT_CHARS, build_prompt, parse_junit, run_tests, safe_env
from tests.conftest import ADD_TESTS

CORRECT = "def add(a, b):\n    return a + b\n"


def test_prompt_incluye_enunciado_e_instrucciones(make_task):
    task = make_task(ADD_TESTS)
    prompt = build_prompt(task)
    assert task.statement in prompt
    assert "```python" in prompt


def test_solucion_correcta(make_task):
    result = run_tests(CORRECT, make_task(ADD_TESTS))
    assert result.status == "ok"
    assert (result.passed, result.failed, result.errors, result.total) == (3, 0, 0, 3)
    assert result.solved


def test_solucion_incorrecta(make_task):
    code = "def add(a, b):\n    return abs(a) + abs(b)\n"
    result = run_tests(code, make_task(ADD_TESTS))
    assert result.status == "ok"
    assert (result.passed, result.failed, result.total) == (2, 1, 3)
    assert not result.solved
    assert "test_negativos" in result.output


def test_error_de_import(make_task):
    result = run_tests("def sumar(a, b):\n    return a + b\n", make_task(ADD_TESTS))
    assert result.status == "import_error"
    assert result.passed == 0
    assert result.total == 3
    assert not result.solved
    assert "ImportError" in result.output or "cannot import" in result.output


def test_error_de_sintaxis(make_task):
    result = run_tests("def add(a, b)\n    return a + b\n", make_task(ADD_TESTS))
    assert result.status == "import_error"
    assert result.total == 3


def test_excepcion_al_importar(make_task):
    result = run_tests("raise RuntimeError('boom')\n", make_task(ADD_TESTS))
    assert result.status == "import_error"


def test_solucion_que_se_cuelga_respeta_el_limite(make_task):
    code = "while True:\n    pass\n"
    result = run_tests(code, make_task(ADD_TESTS), timeout=3)
    assert result.status == "timeout"
    assert result.passed == 0
    assert result.duration_s < 20
    assert "3 s" in result.message


def test_sin_codigo(make_task):
    result = run_tests(None, make_task(ADD_TESTS))
    assert result.status == "no_code"
    assert result.total == 3


def test_la_salida_no_expone_el_directorio_temporal(make_task):
    code = "def add(a, b):\n    return 0\n"
    result = run_tests(code, make_task(ADD_TESTS))
    assert "modelduel-" not in result.output


def test_entorno_sin_secretos(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-no-real")
    monkeypatch.setenv("GEMINI_API_KEY", "no-real")
    monkeypatch.setenv("MY_SECRET", "x")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-x")
    env = safe_env()
    assert "OPENAI_API_KEY" not in env
    assert "GEMINI_API_KEY" not in env
    assert "MY_SECRET" not in env
    assert "PYTEST_ADDOPTS" not in env


def test_la_solucion_no_ve_las_claves(make_task, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-no-real")
    tests = (
        "import os\nfrom solution import leak\n\ndef test_sin_clave():\n    assert leak() is None\n"
    )
    code = "import os\n\ndef leak():\n    return os.environ.get('OPENAI_API_KEY')\n"
    assert run_tests(code, make_task(tests)).solved


def test_parse_junit_error_de_recogida(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text(
        '<testsuites><testsuite tests="1" errors="1">'
        '<testcase classname="" name="test_task"><error message="collection failure"/>'
        "</testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    counts = parse_junit(xml)
    assert counts["collection_error"] is True
    assert counts["total"] == 0


def test_parse_junit_mixto(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="test_task" name="a"/>'
        '<testcase classname="test_task" name="b"><failure message="x"/></testcase>'
        '<testcase classname="test_task" name="c"><error message="x"/></testcase>'
        '<testcase classname="test_task" name="d"><skipped message="x"/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    counts = parse_junit(xml)
    assert counts["passed"] == 1
    assert counts["failed"] == 1
    assert counts["errors"] == 1
    assert counts["skipped"] == 1
    assert counts["total"] == 4
    assert counts["collection_error"] is False


def test_parse_junit_xml_roto(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text("<testsuites", encoding="utf-8")
    assert parse_junit(xml) is None


# ---------------------------------------------------------------- casos límite (qa)


def _spawn_child_code(marker, delay: float, close_fds: bool = True) -> str:
    """Solución que lanza un proceso hijo que escribe ``marker`` tras ``delay`` segundos."""
    child = (
        f"import time, pathlib; time.sleep({delay}); pathlib.Path({str(marker)!r}).write_text('x')"
    )
    return (
        "import subprocess, sys\n"
        f"subprocess.Popen([sys.executable, '-c', {child!r}], close_fds={close_fds})\n"
        "def add(a, b):\n"
        "    return a + b\n"
    )


def test_no_espera_a_procesos_nietos_que_heredan_la_salida(make_task, tmp_path):
    marker = tmp_path / "nieto.txt"
    start = time.perf_counter()
    result = run_tests(_spawn_child_code(marker, 8, close_fds=False), make_task(ADD_TESTS))
    assert result.solved
    assert time.perf_counter() - start < 6


def test_mata_el_arbol_de_procesos_al_terminar(make_task, tmp_path):
    marker = tmp_path / "nieto.txt"
    result = run_tests(_spawn_child_code(marker, 2), make_task(ADD_TESTS))
    assert result.solved
    time.sleep(3.5)
    assert not marker.exists(), "el proceso hijo de la solución siguió vivo"


def test_mata_el_arbol_de_procesos_al_agotar_el_tiempo(make_task, tmp_path):
    marker = tmp_path / "nieto.txt"
    code = _spawn_child_code(marker, 4) + "while True:\n    pass\n"
    result = run_tests(code, make_task(ADD_TESTS), timeout=2)
    assert result.status == "timeout"
    time.sleep(4)
    assert not marker.exists(), "el proceso hijo de la solución siguió vivo"


def test_salida_enorme_se_recorta_y_conserva_el_resumen_final(make_task):
    code = "def add(a, b):\n    print('ruido ' * 200_000)\n    return -1\n"
    result = run_tests(code, make_task(ADD_TESTS))
    assert result.status == "ok"
    assert (result.passed, result.failed) == (0, 3)
    assert len(result.output) < MAX_OUTPUT_CHARS + 200
    assert "salida recortada" in result.output
    # Lo último que imprime pytest (el resumen) es lo más útil: no se puede perder.
    assert "3 failed" in result.output.splitlines()[-1]


def test_salida_sin_retornos_de_carro_y_con_utf8(make_task):
    code = "def add(a, b):\n    print('¡ñandú €!')\n    return 0\n"
    result = run_tests(code, make_task(ADD_TESTS))
    assert "\r" not in result.output
    assert "¡ñandú €!" in result.output


def test_leer_stdin_no_bloquea(make_task):
    code = "valor = input()\ndef add(a, b):\n    return a + b\n"
    result = run_tests(code, make_task(ADD_TESTS), timeout=10)
    assert result.status == "import_error"
    assert "EOFError" in result.output or "reading from stdin" in result.output


def test_temporales_de_la_solucion_dentro_del_directorio_de_la_ejecucion(make_task):
    # Lo que la solución (o pytest) deje en el temporal se borra al terminar la ejecución.
    tests = "from solution import where\n\ndef test_tmp():\n    assert 'modelduel-' in where()\n"
    code = "import tempfile\n\ndef where():\n    return tempfile.gettempdir()\n"
    assert run_tests(code, make_task(tests)).solved


def test_ruta_de_tarea_con_espacios_y_acentos(tmp_path):
    from modelduel.tasks import load_task

    folder = tmp_path / "mis tareas" / "sumar ñandú"
    folder.mkdir(parents=True)
    (folder / "task.md").write_text("# Sumar\n", encoding="utf-8")
    (folder / "test_task.py").write_text(ADD_TESTS, encoding="utf-8")
    assert run_tests(CORRECT, load_task(folder)).solved


def test_tarea_sin_tests_es_un_error_claro(make_task):
    result = run_tests(CORRECT, make_task("from solution import add\n"))
    assert result.status == "error"
    assert not result.solved
    assert "ningún test" in result.message


def test_junit_ausente_es_un_error(make_task):
    # La solución termina el proceso de pytest antes de que escriba el XML.
    code = "import os\nos._exit(0)\n"
    result = run_tests(code, make_task(ADD_TESTS))
    assert result.status == "error"
    assert "sin generar resultados" in result.message


def test_parse_junit_vacio(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text("", encoding="utf-8")
    assert parse_junit(xml) is None
