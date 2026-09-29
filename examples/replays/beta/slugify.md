---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 405
output_tokens: 596
latency_s: 7.62
---
Aquí tienes una implementación basada en el enfoque clásico de muchos frameworks web:
primero se eliminan los diacríticos con la normalización Unicode NFKD, después se
descartan los signos de puntuación y por último se sustituyen los espacios por el
separador.

```python
import re
import unicodedata


def slugify(text: str, separator: str = "-") -> str:
    """Convierte ``text`` en un slug apto para URL."""
    # 1. Quitar tildes y diacríticos: "Canción" -> "Cancion".
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # 2. Eliminar todo lo que no sea letra, dígito, espacio o guion.
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()

    # 3. Colapsar espacios, guiones y guiones bajos en un único separador.
    text = re.sub(r"[\s_-]+", separator, text)

    # 4. Nunca empezar ni terminar con el separador.
    return text.strip(separator)
```

La función es idempotente: aplicarla dos veces sobre el mismo texto da el mismo resultado.
