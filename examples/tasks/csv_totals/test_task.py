import pytest

from solution import csv_totals


def test_ejemplo_del_enunciado():
    text = "fecha,categoria,importe\n2026-01-01,comida,10.50\n2026-01-02,comida,2"
    assert csv_totals(text) == {"comida": "12.50"}


def test_cabecera_en_cualquier_orden_y_sin_mayusculas():
    text = "IMPORTE,Categoria,FECHA\n1.20,libros,2026-01-01\n2.30,viajes,2026-01-02"
    assert csv_totals(text) == {"libros": "1.20", "viajes": "2.30"}


def test_comas_en_campos_entre_comillas():
    text = 'fecha,categoria,importe\n2026-01-01,"casa, luz",4.25'
    assert csv_totals(text) == {"casa, luz": "4.25"}


def test_filas_vacias_y_decimales_se_suman_exactamente():
    text = "fecha,categoria,importe\n\n2026-01-01,a,0.10\n2026-01-02,a,0.20\n"
    assert csv_totals(text) == {"a": "0.30"}


def test_claves_en_orden_alfabetico():
    text = "fecha,categoria,importe\n1,z,1\n2,a,2"
    assert list(csv_totals(text)) == ["a", "z"]


def test_columna_ausente_lanza_valueerror():
    with pytest.raises(ValueError):
        csv_totals("fecha,categoria\n2026-01-01,comida")


def test_importe_no_numerico_lanza_valueerror():
    with pytest.raises(ValueError):
        csv_totals("fecha,categoria,importe\n2026-01-01,comida,ninguno")


def test_texto_sin_filas_devuelve_diccionario_vacio():
    assert csv_totals("fecha,categoria,importe\n") == {}
