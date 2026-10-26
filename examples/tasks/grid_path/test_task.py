import pytest

from solution import grid_path


def test_ejemplo_del_enunciado():
    assert grid_path(["S..", ".#.", "..E"]) == 4


def test_camino_recto():
    assert grid_path(["S.E"]) == 2


def test_rodea_muros():
    assert grid_path(["S#.", "..E"]) == 3


def test_sin_camino_devuelve_menos_uno():
    assert grid_path(["S#E"]) == -1


@pytest.mark.parametrize("grid", [["..E"], ["S.S", "..E"], ["S.E", "E.."]])
def test_falta_o_hay_mas_de_un_inicio_meta_lanza_valueerror(grid):
    with pytest.raises(ValueError):
        grid_path(grid)


def test_filas_de_distinta_longitud_lanzan_valueerror():
    with pytest.raises(ValueError):
        grid_path(["S..", ".E"])


@pytest.mark.parametrize("grid", [["SxE"], ["S..", ".?E"]])
def test_caracter_desconocido_lanza_valueerror(grid):
    with pytest.raises(ValueError):
        grid_path(grid)
