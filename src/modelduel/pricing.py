"""Coste estimado a partir de tarifas por millón de tokens.

coste = entrada / 1e6 × tarifa_entrada + salida / 1e6 × tarifa_salida

La tabla integrada solo contiene precios FICTICIOS para los contendientes ``replay`` de la demo.
Los precios reales cambian a menudo: añádelos tú con ``--prices precios.json``::

    {
      "openai:mi-modelo": {"input": 0.15, "output": 0.60, "currency": "USD"},
      "gemini:otro-modelo": {"input": 0.10, "output": 0.40, "currency": "EUR"}
    }

Si un modelo no tiene precio, el coste es «sin datos»: nunca se inventa.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


class PricingError(Exception):
    """Archivo de precios no válido."""


@dataclass(frozen=True)
class Price:
    input: float  # por millón de tokens de entrada
    output: float  # por millón de tokens de salida
    currency: str = "USD"
    fictitious: bool = False
    source: str = "builtin"

    def to_dict(self) -> dict:
        return asdict(self)


BUILTIN_PRICES: dict[str, Price] = {
    # Precios FICTICIOS: solo sirven para que la demo con respuestas grabadas muestre costes.
    "replay:alfa": Price(input=0.40, output=1.60, currency="USD", fictitious=True),
    "replay:beta": Price(input=2.50, output=10.00, currency="USD", fictitious=True),
    "replay:gamma": Price(input=0.10, output=0.40, currency="USD", fictitious=True),
}


def load_prices(path: Path | None) -> dict[str, Price]:
    """Tabla integrada ampliada (o sobrescrita) con el JSON del usuario."""
    table = dict(BUILTIN_PRICES)
    if path is None:
        return table
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise PricingError(f"No se pudo leer {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PricingError(f"{path} no es JSON válido: {exc}") from exc
    if not isinstance(data, dict):
        raise PricingError(f'{path} debe ser un objeto JSON {{"proveedor:modelo": {{...}}}}.')
    for key, entry in data.items():
        if key.startswith("_"):  # permite comentarios como "_nota"
            continue
        if not isinstance(entry, dict):
            raise PricingError(f"El precio de «{key}» debe ser un objeto con input y output.")
        try:
            price_in = float(entry["input"])
            price_out = float(entry["output"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PricingError(f"El precio de «{key}» necesita input y output numéricos.") from exc
        if price_in < 0 or price_out < 0:
            raise PricingError(f"El precio de «{key}» no puede ser negativo.")
        table[key] = Price(
            input=price_in,
            output=price_out,
            currency=str(entry.get("currency", "USD")).upper(),
            fictitious=bool(entry.get("fictitious", False)),
            source="file",
        )
    return table


def find_price(spec: str, table: dict[str, Price]) -> Price | None:
    """Busca por ``proveedor:modelo`` y, si no, solo por ``modelo``."""
    if spec in table:
        return table[spec]
    _, _, model = spec.partition(":")
    return table.get(model) if model else None


def compute_cost(
    price: Price | None, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if price is None or input_tokens is None or output_tokens is None:
        return None
    return input_tokens / 1e6 * price.input + output_tokens / 1e6 * price.output
