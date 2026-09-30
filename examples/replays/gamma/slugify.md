---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 388
output_tokens: 96
latency_s: 0.92
---
```python
import re
import unicodedata


def slugify(text: str, separator: str = "-") -> str:
    plain = "".join(
        char for char in unicodedata.normalize("NFD", text) if not unicodedata.combining(char)
    )
    return separator.join(re.findall(r"[a-z0-9]+", plain.lower()))
```
