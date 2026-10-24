---
name: anadir-tarea
description: Guía para añadir una nueva tarea de ejemplo con sus respuestas grabadas.
---

# Skill: Añadir Tarea

Sigue estos pasos para añadir una tarea de ejemplo al repositorio.

## 1. Archivos de la tarea
Crea la carpeta `examples/tasks/<id>/` con:

- **`task.md`**: Enunciado claro. Debe especificar el nombre de la función y lo que debe devolver.
- **`test_task.py`**: Tests `pytest`. Importa la función desde `solution`. Incluye varios casos de prueba, incluyendo límites.
- **`meta.toml`**: 
  ```toml
  title = "Convertir un texto en slug"
  difficulty = "fácil"   # fácil | media | difícil, en minúsculas como las existentes
  order = 4              # posición en la lista
  ```

## 2. Respuestas grabadas (replays)
Crea o edita los archivos en `examples/replays/<contendiente>/<id>.md` (donde contendiente es `alfa`, `beta` o `gamma`):

```markdown
---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 412
output_tokens: 188
latency_s: 2.84
---
```python
# Tu código aquí
```
```

## 3. Verificación
1. **Listar:** `modelduel list-tasks examples/tasks` debe mostrar la nueva tarea.
2. **Ejecutar tests:** `pytest tests/test_tasks.py` (carga y orden) y `pytest` completo: hay tests que comprueban las tareas y respuestas incluidas en el paquete.
3. **Demo:** Ejecuta la demo (`modelduel run examples/tasks --model replay:alfa ...`) y verifica el informe generado.

Imita el estilo de las tareas existentes como `slugify` o `merge_intervals`.
