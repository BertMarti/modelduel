import pytest

from solution import parse_duration


def test_ejemplo_del_enunciado():
    assert parse_duration("1h 30m 15s") == 5415


def test_una_sola_unidad():
    assert parse_duration("45s") == 45
    assert parse_duration("2d") == 172_800


def test_componentes_juntos_y_unidades_omitidas():
    assert parse_duration("1h30m") == 5_400
    assert parse_duration("2d 5s") == 172_805


def test_mayusculas_y_espacios_sobrantes():
    assert parse_duration("  2H   5M ") == 7_500


def test_cero_es_valido():
    assert parse_duration("0s") == 0


@pytest.mark.parametrize("text", ["", "   "])
def test_texto_vacio_lanza_valueerror(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["10", "5x", "1h 2h", "-5m", "1.5h", "h", "1h y 5m", "1 h"])
def test_formatos_invalidos_lanzan_valueerror(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def test_unidades_fuera_de_orden_lanzan_valueerror():
    with pytest.raises(ValueError):
        parse_duration("30m 1h")
