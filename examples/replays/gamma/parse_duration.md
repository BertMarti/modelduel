---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 490
output_tokens: 188
latency_s: 1.58
---
```python
import re

_PATTERN = re.compile(
    r"\s*(?:(\d+)d)?(?:\s*(\d+)h)?(?:\s*(\d+)m)?(?:\s*(\d+)s)?\s*", re.IGNORECASE
)


def parse_duration(text: str) -> int:
    match = _PATTERN.fullmatch(text)
    if match is None or all(group is None for group in match.groups()):
        raise ValueError(f"Duración no válida: {text!r}")
    days, hours, minutes, seconds = (int(group or 0) for group in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds
```
