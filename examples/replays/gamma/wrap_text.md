---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 431
output_tokens: 183
latency_s: 1.09
---
```python
def wrap_text(text: str, width: int) -> list[str]:
    if width < 1:
        raise ValueError("ancho inválido")
    words = text.split()
    result = []
    line = ""
    for word in words:
        if len(word) > width:
            result.extend(word[i : i + width] for i in range(0, len(word), width))
        elif line and len(line) + len(word) + 1 > width:
            result.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        result.append(line)
    return result
```
