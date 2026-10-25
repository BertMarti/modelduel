import pytest

from solution import wrap_text


def test_ejemplo_del_enunciado():
    assert wrap_text("uno dos tres cuatro", 7) == ["uno dos", "tres", "cuatro"]


def test_colapsa_espacios_y_saltos_de_linea():
    assert wrap_text("  hola   mundo\n desde aquí ", 21) == ["hola mundo desde aquí"]


def test_algoritmo_voraz():
    assert wrap_text("aa bb cc", 5) == ["aa bb", "cc"]


def test_parte_palabras_largas():
    assert wrap_text("abcdef gh", 3) == ["abc", "def", "gh"]


def test_palabra_exacta_y_varias_lineas():
    assert wrap_text("abcd efgh", 4) == ["abcd", "efgh"]


def test_texto_vacio_devuelve_lista_vacia():
    assert wrap_text(" \n\t ", 4) == []


@pytest.mark.parametrize("width", [0, -1])
def test_ancho_invalido_lanza_valueerror(width):
    with pytest.raises(ValueError):
        wrap_text("texto", width)


def test_no_deja_espacios_en_las_lineas():
    assert wrap_text("a  b", 3) == ["a b"]
