import pytest

from solution import flatten_json


def test_ejemplo_del_enunciado():
    assert flatten_json({"a": [{"b": 1}]}) == {"a.0.b": 1}


def test_anida_diccionarios_y_listas():
    data = {"usuario": {"nombre": "Ana", "roles": ["admin", "lectora"]}}
    assert flatten_json(data) == {
        "usuario.nombre": "Ana",
        "usuario.roles.0": "admin",
        "usuario.roles.1": "lectora",
    }


def test_conserva_contenedores_vacios():
    assert flatten_json({"objeto": {}, "lista": [], "anidado": {"vacio": []}}) == {
        "objeto": {},
        "lista": [],
        "anidado.vacio": [],
    }


def test_raiz_vacia():
    assert flatten_json({}) == {}


def test_no_modifica_la_entrada():
    data = {"a": {"b": [1, 2]}}
    original = {"a": {"b": [1, 2]}}
    flatten_json(data)
    assert data == original


def test_clave_con_punto_lanza_valueerror():
    with pytest.raises(ValueError):
        flatten_json({"a.b": 1})


def test_clave_no_textual_lanza_typeerror():
    with pytest.raises(TypeError):
        flatten_json({1: "valor"})


def test_lista_de_valores_primitivos():
    assert flatten_json({"valores": [True, None, 3]}) == {
        "valores.0": True,
        "valores.1": None,
        "valores.2": 3,
    }
