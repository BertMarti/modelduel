---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 521
output_tokens: 274
latency_s: 3.91
---
```python
import re

_SECONDS = {"d": 86_400, "h": 3_600, "m": 60, "s": 1}
_FORMAT = re.compile(r"(?:\s*\d+[dhms])+\s*", re.IGNORECASE)
_COMPONENT = re.compile(r"(\d+)([dhms])", re.IGNORECASE)


def parse_duration(text: str) -> int:
    if not _FORMAT.fullmatch(text):
        raise ValueError(f"Duración no válida: {text!r}")

    total = 0
    seen: set[str] = set()
    for number, unit in _COMPONENT.findall(text):
        unit = unit.lower()
        if unit in seen:
            raise ValueError(f"Unidad repetida: {unit!r}")
        seen.add(unit)
        total += int(number) * _SECONDS[unit]
    return total
```
