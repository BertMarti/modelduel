from modelduel.extract import extract_code, find_code_blocks


def test_bloque_python_con_texto_alrededor():
    text = "Aquí va:\n\n```python\ndef f():\n    return 1\n```\n\nEspero que sirva."
    assert extract_code(text) == "def f():\n    return 1\n"


def test_alias_py_y_python3():
    assert extract_code("```py\nx = 1\n```") == "x = 1\n"
    assert extract_code("```Python3\nx = 2\n```") == "x = 2\n"


def test_prefiere_el_primer_bloque_python():
    text = "```bash\npip install nada\n```\n```python\nx = 1\n```\n```python\nx = 2\n```"
    assert extract_code(text) == "x = 1\n"


def test_unico_bloque_sin_lenguaje():
    assert extract_code("Mira:\n```\nx = 3\n```") == "x = 3\n"


def test_unico_bloque_con_otro_lenguaje():
    assert extract_code("```text\nx = 4\n```") == "x = 4\n"


def test_varios_bloques_sin_python_usa_el_primero_sin_lenguaje():
    text = "```\nx = 5\n```\n\n```text\nsalida\n```"
    assert extract_code(text) == "x = 5\n"


def test_sin_bloques_devuelve_none():
    assert extract_code("def f(): return 1") is None
    assert extract_code("") is None


def test_bloque_vacio_devuelve_none():
    assert extract_code("```python\n\n```") is None


def test_tildes_y_fin_de_linea_windows():
    text = "~~~python\r\nx = 'ñ'\r\n~~~\r\n"
    assert extract_code(text) == "x = 'ñ'\n"


def test_bloque_sin_cerrar_toma_el_resto():
    assert extract_code("```python\ndef f():\n    return 1\n") == "def f():\n    return 1\n"


def test_cuatro_comillas_permiten_triples_dentro():
    text = '````python\ns = """\n```\n"""\n````'
    assert extract_code(text) == 's = """\n```\n"""\n'


def test_find_code_blocks_devuelve_lenguajes():
    blocks = find_code_blocks("```python\na\n```\n```\nb\n```")
    assert blocks == [("python", "a"), ("", "b")]


def test_bloque_sangrado_dentro_de_una_lista():
    # Sin quitar la sangría común, el código daba «unexpected indent» al importarlo.
    text = "1. Solución:\n   ```python\n   def f():\n       return 1\n   ```\n"
    assert extract_code(text) == "def f():\n    return 1\n"


def test_salta_bloques_python_vacios():
    text = "```python\n\n```\n\n```python\nx = 1\n```"
    assert extract_code(text) == "x = 1\n"
