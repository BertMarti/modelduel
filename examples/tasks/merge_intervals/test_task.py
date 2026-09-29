import pytest

from solution import merge_intervals


def test_lista_vacia():
    assert merge_intervals([]) == []


def test_ejemplo_del_enunciado():
    assert merge_intervals([(8, 10), (1, 3), (2, 6), (15, 18)]) == [(1, 6), (8, 10), (15, 18)]


def test_sin_solapes_se_ordenan_y_no_se_fusionan():
    assert merge_intervals([(5, 6), (1, 2), (3, 4)]) == [(1, 2), (3, 4), (5, 6)]


def test_intervalos_que_comparten_extremo_se_fusionan():
    assert merge_intervals([(3, 5), (1, 3), (5, 7)]) == [(1, 7)]


def test_intervalos_contenidos_en_otro():
    assert merge_intervals([(1, 10), (2, 3), (4, 8), (9, 10)]) == [(1, 10)]


def test_intervalos_de_un_solo_punto():
    assert merge_intervals([(5, 5), (1, 2), (2, 2), (7, 7)]) == [(1, 2), (5, 5), (7, 7)]


def test_no_modifica_la_entrada():
    data = [(4, 6), (1, 5)]
    copy = list(data)
    result = merge_intervals(data)
    assert data == copy
    assert result == [(1, 6)]
    assert all(isinstance(item, tuple) for item in result)


def test_intervalo_invalido_lanza_valueerror():
    with pytest.raises(ValueError):
        merge_intervals([(1, 2), (6, 3)])
