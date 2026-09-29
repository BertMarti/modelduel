from modelduel.runner import build_prompt, parse_junit, run_tests, safe_env
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
