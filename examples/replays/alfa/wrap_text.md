---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 498
output_tokens: 245
latency_s: 3.44
---
```python
def wrap_text(text: str, width: int) -> list[str]:
    if width < 1:
        raise ValueError("El ancho debe ser positivo")
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(word) <= width:
            if current and len(current) + 1 + len(word) > width:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
                current = ""
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            current = word
    if current:
        lines.append(current)
    return lines
```
