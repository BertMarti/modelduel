# MEMORY.md · modelduel
Última actualización: 2026-09-29 por builder

## Estado actual
MVP completo en la rama `agent/builder` (PR abierto a `main`, sin fusionar):
- CLI `modelduel` (`run`, `report`, `list-tasks`) en `src/modelduel/`, solo biblioteca estándar.
- Proveedores `replay`, `gemini` (REST `generateContent`) y `openai` (Chat Completions compatible: OpenAI, OpenRouter, Ollama).
- Runner: extrae el bloque de código, ejecuta pytest en un directorio temporal con límite de tiempo y lee el XML JUnit. Distingue `ok`, `no_code`, `import_error`, `timeout`, `error` y `provider_error`.
- Costes con tabla ampliable (`--prices`); solo hay precios ficticios integrados para `replay:alfa` y `replay:beta`.
- Informe HTML «duelo editorial oscuro» (`string.Template`, CSS en línea, SVG, sin JavaScript, hoja de impresión).
- Tres tareas originales (`slugify`, `merge_intervals`, `parse_duration`) y respuestas grabadas de `alfa` (falla 1 caso límite de `parse_duration`: no exige el orden de unidades) y `beta` (falla 2 tests de `slugify`: borra `.` y `/` en vez de separar).
- Web estática en `site/index.html`; la demo `site/demo/` se genera en el CI (está en `.gitignore`).
- 68 tests pytest sin red; CI en Ubuntu y Windows; despliegue a Pages en `deploy.yml`.

## Decisiones (por qué)
- 2026-09-29: Proveedor `replay` con respuestas grabadas para que la demo y los tests funcionen sin claves ni coste.
- 2026-09-29: Solo biblioteca estándar en ejecución para que instalarlo sea trivial.
- 2026-09-29 (builder): pytest NO es dependencia de ejecución (solo `dev`), pero hace falta para ejecutar las tareas. Si falta, la CLI da un error claro y el README indica `pip install ... pytest`. Se mantiene así para respetar «solo biblioteca estándar».
- 2026-09-29 (builder): la interfaz de proveedor es `complete(prompt, *, task_id=None) -> Response`; `task_id` solo lo usa `replay` para saber qué archivo leer.
- 2026-09-29 (builder): `replay` busca `<nombre>` en `--replays`, luego en `<carpeta de tareas>/../replays` y luego en `./examples/replays`.
- 2026-09-29 (builder): el subproceso de tests recibe un entorno sin variables que contengan KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL, sin `PYTEST_ADDOPTS`/`PYTHONPATH`, con autocarga de plugins desactivada y un `pytest.ini` vacío para aislarlo de la configuración del usuario.
- 2026-09-29 (builder): Gemini recibe la clave en la cabecera `x-goog-api-key` (no en la URL) y los mensajes de error se redactan por si acaso. Los tokens de razonamiento de Gemini (`thoughtsTokenCount`) se suman a la salida porque se facturan como salida.
- 2026-09-29 (builder): `openai:` no exige clave si `OPENAI_BASE_URL` apunta a localhost (Ollama).
- 2026-09-29 (builder): no se incluyen precios reales en el código porque cambian a menudo; el usuario los aporta con `--prices`. Sin precio o sin tokens → «sin datos».
- 2026-09-29 (builder): con `--runs N`, «tareas resueltas» cuenta solo las tareas con todos los tests en verde en todas las ejecuciones; tests, tiempo, tokens y coste se suman.
- 2026-09-29 (builder): el orden de las tareas sale de `order` en `meta.toml` (después, del nombre de la carpeta).
- 2026-09-29 (builder): números en formato español en el informe y la consola (coma decimal, punto de miles).

## Siguiente paso
1. lead: revisar y fusionar el PR de `agent/builder`; comprobar que `deploy.yml` publica la web y `demo/` en Pages.
2. qa (`agent/qa`): revisar el runner (límite de tiempo en Windows con procesos hijos, salidas enormes, soluciones que escriben fuera del temporal), añadir tests de casos límite de `extract_code` y del informe con `--runs` > 1, y revisar accesibilidad del informe (contraste del texto atenuado, navegación con teclado de `<details>`).
3. docs (`agent/opencode-docs`): escribir `docs/USO.md` a partir del README (instalación, crear tareas, proveedores, precios, cómo leer el informe).

## Problemas conocidos
- El aislamiento es solo un directorio temporal + subproceso con límite + entorno sin secretos: el código del modelo puede leer y escribir en el resto del disco. Está advertido en README y web; lo ideal es usar un contenedor o VM.
- Si un proceso hijo lanzado por la solución sobrevive al `kill` del límite de tiempo, podría seguir en ejecución (no se mata el árbol de procesos).
- Los proveedores `gemini` y `openai` solo se prueban con respuestas simuladas (sin red); no se han probado contra las APIs reales en este MVP.

## Registro de sesiones
- 2026-09-29 lead (main): creación del repositorio y reparto del equipo.
- 2026-09-29 builder (agent/builder): MVP completo (CLI, proveedores, runner, costes, informe, tareas, web, tests, CI y Pages) y PR a main.
