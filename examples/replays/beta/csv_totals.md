---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 603
output_tokens: 788
latency_s: 12.37
---
```python
import csv
from decimal import Decimal
from io import StringIO


def csv_totals(text: str) -> dict[str, str]:
    reader = csv.DictReader(StringIO(text))
    names = {name.lower(): name for name in (reader.fieldnames or [])}
    if not {"fecha", "categoria", "importe"} <= set(names):
        raise ValueError("Cabecera incompleta")
    totals = {}
    for row in reader:
        if not any(row.values()):
            continue
        try:
            amount = Decimal(row[names["importe"]])
        except Exception as exc:
            raise ValueError("Importe no válido") from exc
        category = row[names["categoria"]]
        totals[category] = totals.get(category, Decimal("0")) + amount
    return {key: f"{value:.2f}" for key, value in totals.items()}
```
