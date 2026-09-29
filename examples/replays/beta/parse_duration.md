---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 509
output_tokens: 834
latency_s: 11.48
---
Para validar el orden y que cada unidad aparezca como mucho una vez, lo más robusto es
una única expresión regular con un grupo opcional por unidad, en orden fijo:

```
import re

_UNITS = (("d", 86_400), ("h", 3_600), ("m", 60), ("s", 1))
_PATTERN = re.compile(
    r"\s*"
    r"(?:(?P<d>\d+)d)?\s*"
    r"(?:(?P<h>\d+)h)?\s*"
    r"(?:(?P<m>\d+)m)?\s*"
    r"(?:(?P<s>\d+)s)?\s*",
    re.IGNORECASE,
)


def parse_duration(text: str) -> int:
    """Convierte una duración como "1h 30m 15s" en segundos."""
    match = _PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"Duración no válida: {text!r}")

    values = match.groupdict()
    if all(value is None for value in values.values()):
        raise ValueError("La duración está vacía")

    return sum(int(values[unit]) * factor for unit, factor in _UNITS if values[unit] is not None)
```

Algunos ejemplos de uso:

```text
parse_duration("1h 30m 15s")  -> 5415
parse_duration("2d 5s")       -> 172805
parse_duration("30m 1h")      -> ValueError
```
