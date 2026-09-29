from solution import slugify


def test_basico():
    assert slugify("Hola Mundo") == "hola-mundo"


def test_acentos_y_enie():
    assert slugify("Canción de Añoranza") == "cancion-de-anoranza"
    assert slugify("Pingüino FRANÇAIS") == "pinguino-francais"


def test_colapsa_signos_y_espacios():
    assert slugify("¡¡Hola,   mundo!!  ¿Qué tal?") == "hola-mundo-que-tal"


def test_sin_separadores_en_los_extremos():
    assert slugify("  --Ya está--  ") == "ya-esta"


def test_punto_entre_digitos_separa():
    assert slugify("Python 3.12 en 2026") == "python-3-12-en-2026"


def test_barra_y_guion_bajo_separan():
    assert slugify("Entrada/Salida") == "entrada-salida"
    assert slugify("nombre_de_variable") == "nombre-de-variable"


def test_sin_caracteres_validos_devuelve_vacio():
    assert slugify("") == ""
    assert slugify("   ") == ""
    assert slugify("¡¿!?") == ""


def test_separador_personalizado():
    assert slugify("Árbol Genealógico", separator="_") == "arbol_genealogico"
    assert slugify("  a · b  ", separator=".") == "a.b"
