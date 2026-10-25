---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 584
output_tokens: 301
latency_s: 4.18
---
```python
import csv
from decimal import Decimal
from io import StringIO


def csv_totals(text: str) -> dict[str, str]:
    rows = list(csv.DictReader(StringIO(text)))
    if not rows:
        header = next(csv.reader(StringIO(text)), [])
        names = {name.strip().lower() for name in header}
        if not {"fecha", "categoria", "importe"} <= names:
            raise ValueError("Falta una columna")
        return {}
    names = {name.strip().lower() for name in rows[0]}
    if not {"fecha", "categoria", "importe"} <= names:
        raise ValueError("Falta una columna")
    columns = {name.strip().lower(): name for name in rows[0]}
    totals = {}
    for row in rows:
        category = row[columns["categoria"]]
        try:
            amount = Decimal(row[columns["importe"]])
        except Exception as exc:
            raise ValueError("Importe no válido") from exc
        totals[category] = totals.get(category, Decimal("0")) + amount
    return {key: f"{totals[key]:.2f}" for key in sorted(totals)}
```
