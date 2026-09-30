import json

import pytest

from modelduel.pricing import (
    BUILTIN_PRICES,
    Price,
    PricingError,
    compute_cost,
    find_price,
    load_prices,
)


def test_formula_de_coste():
    price = Price(input=2.0, output=8.0)
    # 1500/1e6 × 2 + 500/1e6 × 8 = 0.003 + 0.004
    assert compute_cost(price, 1500, 500) == pytest.approx(0.007)


def test_sin_precio_o_sin_tokens_es_sin_datos():
    assert compute_cost(None, 100, 100) is None
    assert compute_cost(Price(1, 1), None, 100) is None
    assert compute_cost(Price(1, 1), 100, None) is None


def test_precios_de_replay_son_ficticios():
    assert all(price.fictitious for price in BUILTIN_PRICES.values())
    assert set(BUILTIN_PRICES) == {"replay:alfa", "replay:beta", "replay:gamma"}


def test_load_prices_amplia_la_tabla(tmp_path):
    path = tmp_path / "precios.json"
    path.write_text(
        json.dumps(
            {
                "_nota": "comentario ignorado",
                "openai:mi-modelo": {"input": 0.5, "output": 1.5, "currency": "eur"},
            }
        ),
        encoding="utf-8",
    )
    table = load_prices(path)
    assert "replay:alfa" in table
    price = table["openai:mi-modelo"]
    assert (price.input, price.output, price.currency, price.source) == (0.5, 1.5, "EUR", "file")


def test_find_price_por_spec_y_por_modelo():
    table = {"openai:a": Price(1, 1), "b": Price(2, 2)}
    assert find_price("openai:a", table).input == 1
    assert find_price("gemini:b", table).input == 2
    assert find_price("openai:c", table) is None


@pytest.mark.parametrize(
    "content",
    [
        "no es json",
        "[1, 2]",
        '{"m": {"input": 1}}',
        '{"m": {"input": -1, "output": 1}}',
        '{"m": 3}',
    ],
)
def test_load_prices_invalidos(tmp_path, content):
    path = tmp_path / "p.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(PricingError):
        load_prices(path)
