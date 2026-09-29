---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 412
output_tokens: 188
latency_s: 2.84
---
```python
import re
import unicodedata


def slugify(text: str, separator: str = "-") -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    parts = re.split(r"[^a-z0-9]+", ascii_text)
    return separator.join(part for part in parts if part)
```
