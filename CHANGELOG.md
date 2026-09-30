# Registro de cambios

Todos los cambios relevantes de modelduel se anotan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Cambiado

- El veredicto del duelo de dos usa ahora la misma ordenación que la clasificación (tareas resueltas, luego tests superados y luego coste) y dice qué criterio decide: «gana A por tareas resueltas (2 frente a 1)», «gana A por tests superados (…, con las mismas tareas resueltas)», «gana B por coste (…)» o «empate en tareas resueltas, tests y coste» (o «empate en tareas resueltas y tests (sin coste comparable)» si algún contendiente no tiene precio o las monedas difieren). Antes solo contaba tests superados y podía discrepar de la clasificación ([#15](https://github.com/BertMarti/modelduel/issues/15)).

## [0.2.0] - 2026-09-30

### Añadido

- **Reintentos** ante HTTP 429, 500, 502, 503 y 504 y cortes de conexión, con espera exponencial (1 s × 2^n, tope 30 s) y azar, respetando la cabecera `Retry-After` y avisando en consola de cada reintento. Opción `--retries N` (3 por defecto; `0` los desactiva). No se reintentan los tiempos de espera agotados ni los servidores apagados ([#4](https://github.com/BertMarti/modelduel/issues/4), PR [#10](https://github.com/BertMarti/modelduel/pull/10)).
- **Guardado incremental**: `results.json` se reescribe de forma atómica tras cada intento y lleva `status` (`in_progress` o `complete`), `updated_at` y una huella por tarea. Un corte con Ctrl+C deja además un informe parcial marcado como «Duelo incompleto» ([#5](https://github.com/BertMarti/modelduel/issues/5), PR [#11](https://github.com/BertMarti/modelduel/pull/11)).
- **`--resume`**: continúa un duelo interrumpido saltando los intentos terminados y repitiendo los que acabaron en error del proveedor. Da error si cambian los contendientes y avisa si cambian una tarea, el límite de tiempo o el número de ejecuciones. Sin `--resume` no se sobrescribe un duelo incompleto ([#5](https://github.com/BertMarti/modelduel/issues/5), PR [#11](https://github.com/BertMarti/modelduel/pull/11)).
- **Liga de 2 a 6 contendientes** con `--model/-m` repetible (se puede mezclar con `--a` y `--b`). Informe de liga con clasificación, comparativa con barras, matriz por tarea y detalle; paleta ampliada con seis acentos de contraste AA, siempre acompañados de su letra `A` a `F`. Proveedor de demostración `replay:gamma` ([#6](https://github.com/BertMarti/modelduel/issues/6), PR [#12](https://github.com/BertMarti/modelduel/pull/12)).
- **Publicación en PyPI**: `pip install modelduel` (y extra `modelduel[pytest]`), metadatos completos y workflow `release.yml` con Trusted Publishing, sin tokens. Los ejemplos viajan dentro de la wheel ([#7](https://github.com/BertMarti/modelduel/issues/7), PR [#13](https://github.com/BertMarti/modelduel/pull/13)).
- **`modelduel demo`**: liga de tres modelos ficticios sin claves ni coste (`--out DIR`) y `demo --copy DIR` para copiar las tareas y respuestas de ejemplo como plantilla ([#7](https://github.com/BertMarti/modelduel/issues/7)).
- Job `package` en el CI: construye el paquete, lo comprueba con `twine check --strict` y prueba la wheel en un entorno limpio.
- Documentación de la versión: guía de uso, este registro de cambios y cómo publicar una versión o añadir un color a la paleta ([#9](https://github.com/BertMarti/modelduel/issues/9)).

### Cambiado

- El resumen de la consola es ahora una tabla de clasificación, con una fila por contendiente también en un duelo de dos. Cambia el formato impreso respecto a v0.1.0, no el contrato de la orden ni los códigos de salida.
- La clasificación ordena por tareas resueltas, luego tests superados y luego coste (menos es mejor, solo si todos tienen precio en la misma moneda); los empates comparten posición.
- La demo del CI y de la web es ahora una liga de tres contendientes; el CI comprueba además que `--a`/`--b` sigue dando el «Informe de duelo».
- La versión tiene una única fuente, `src/modelduel/__init__.py`.
- Los resultados de v0.1.0 (`results.json`) se siguen leyendo y se muestran como duelo de dos.

### Corregido

Revisión QA de la versión ([#8](https://github.com/BertMarti/modelduel/issues/8), PR [#14](https://github.com/BertMarti/modelduel/pull/14)):

- `Retry-After` absurdo (números enormes, fechas lejanísimas, negativos o ilegibles) y desbordes con `--retries` muy grandes.
- `--resume` ante un `results.json` de un formato más nuevo (error claro) o manipulado (error en vez de traza), y aviso si el duelo previo es de otra versión de modelduel.
- Un sustituto UTF-16 suelto en un mensaje de error del proveedor rompía el guardado de los resultados.
- Informe de liga ilegible en móvil con seis nombres largos (la barra medía 0 px) y tablas inalcanzables con el teclado.
- Contraste AA de toda la paleta, en pantalla y en impresión, comprobado por un test.
- Escapado de HTML con dos, tres y seis contendientes.
- `release.yml` solo publica commits de `main` y no guarda credenciales de git en el checkout.
- Los tests ya no pueden esperar de verdad (se inyecta la espera en los reintentos).

### Limitaciones conocidas

- El veredicto del duelo de dos («gana A por N») cuenta tests superados, mientras que la clasificación ordena primero por tareas resueltas: con pocas tareas pueden discrepar ([#15](https://github.com/BertMarti/modelduel/issues/15), previsto para v0.3.0).

## [0.1.0] - 2026-09-30

Primera versión (MVP).

### Añadido

- CLI `modelduel` con las órdenes `run`, `report` y `list-tasks`, con ayuda y errores en español y códigos de salida 0, 1, 2 y 130. Solo biblioteca estándar en ejecución (PR [#1](https://github.com/BertMarti/modelduel/pull/1)).
- Proveedores `replay` (respuestas grabadas, sin red), `gemini` (API REST `generateContent`) y `openai` (Chat Completions: OpenAI, OpenRouter, Ollama).
- Ejecución de los tests de cada tarea con pytest en un directorio temporal, con límite de tiempo y sin variables de entorno secretas.
- Coste estimado con tabla de precios ampliable (`--prices`) y `--runs N` para repetir cada tarea.
- Informe HTML «duelo editorial oscuro» autocontenido, con gráficas SVG, sin JavaScript y con hoja de impresión.
- Tres tareas de ejemplo originales (`slugify`, `merge_intervals`, `parse_duration`) con respuestas grabadas.
- Web del proyecto e informe de demostración en GitHub Pages, y CI en Ubuntu y Windows.
- Revisión QA: árbol de procesos muerto al terminar, salida acotada, UTF-8 y BOM, tareas sin tests o con errores de sintaxis, errores de red y respuestas vacías de los proveedores, accesibilidad AA y cobertura mínima del 90 % (PR [#2](https://github.com/BertMarti/modelduel/pull/2)).
- Guía de uso (`docs/USO.md`) y `CONTRIBUTING.md` (PR [#3](https://github.com/BertMarti/modelduel/pull/3)).

[Sin publicar]: https://github.com/BertMarti/modelduel/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/BertMarti/modelduel/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/BertMarti/modelduel/releases/tag/v0.1.0
