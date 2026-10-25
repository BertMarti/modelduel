import pytest

from solution import topo_order


def test_ejemplo_del_enunciado():
    assert topo_order({"cocinar": ["comprar"], "comer": ["cocinar"]}) == [
        "comprar",
        "cocinar",
        "comer",
    ]


def test_desempata_en_orden_alfabetico():
    assert topo_order({"z": [], "a": []}) == ["a", "z"]


def test_incluye_dependencias_que_no_son_claves():
    assert topo_order({"b": ["externa"], "a": ["externa"]}) == ["externa", "a", "b"]


def test_cadena_de_dependencias():
    assert topo_order({"c": ["b"], "b": ["a"], "a": []}) == ["a", "b", "c"]


def test_grafo_vacio():
    assert topo_order({}) == []


def test_no_modifica_la_entrada():
    deps = {"b": ["a"], "a": []}
    original = {"b": ["a"], "a": []}
    topo_order(deps)
    assert deps == original


def test_ciclo_lanza_valueerror_con_mensaje_claro():
    with pytest.raises(ValueError, match="ciclo"):
        topo_order({"a": ["b"], "b": ["a"]})


def test_varias_ramas_se_intercalan_deterministicamente():
    deps = {"c": ["a"], "d": ["b"], "a": [], "b": []}
    assert topo_order(deps) == ["a", "b", "c", "d"]
