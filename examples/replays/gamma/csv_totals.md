---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 449
output_tokens: 177
latency_s: 1.31
---
```python
import csv
from io import StringIO


def csv_totals(text: str) -> dict[str, str]:
    rows = csv.DictReader(StringIO(text))
    totals = {}
    for row in rows:
        category = row["categoria"]
        value = float(row["importe"])
        totals[category] = totals.get(category, 0) + value
    return {key: str(round(value, 2)) for key, value in sorted(totals.items())}
```
