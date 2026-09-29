# MEMORY.md · modelduel
Última actualización: 2026-09-30 por docs

## Estado actual
MVP completo en la rama `agent/builder` (PR #1 a `main`, sin fusionar) y revisión QA en `agent/qa` (PR #2 a `agent/builder`, se fusiona después de #1):
- CLI `modelduel` (`run`, `report`, `list-tasks`) en `src/modelduel/`, solo biblioteca estándar. Ayuda y errores en español; códigos de salida 0/1/2/130.
- Proveedores `replay`, `gemini` (REST `generateContent`) y `openai` (Chat Completions compatible: OpenAI, OpenRouter, Ollama). Errores de red, HTTP y respuestas vacías o raras se convierten en `ProviderError` con mensaje en español.
- Runner: extrae el bloque de código, ejecuta pytest en un directorio temporal con límite de tiempo y lee el XML JUnit. Mata el árbol de procesos al terminar, acota la salida y distingue `ok`, `no_code`, `import_error`, `timeout`, `error` y `provider_error`.
- Costes con tabla ampliable (`--prices`); solo hay precios ficticios integrados para `replay:alfa` y `replay:beta`.
- Informe HTML «duelo editorial oscuro» (`string.Template`, CSS en línea, SVG con `<title>` y `aria-label`, sin JavaScript, hoja de impresión). Con `--runs` > 1 muestra «Intentos resueltos» y «suma de N ejecuciones».
- Tres tareas originales (`slugify`, `merge_intervals`, `parse_duration`) y respuestas grabadas de `alfa` (falla 1 caso límite de `parse_duration`) y `beta` (falla 2 tests de `slugify`).
- Web estática en `site/index.html` con metadatos Open Graph y favicon en línea; la demo `site/demo/` se genera en el CI (está en `.gitignore`).
- 132 tests pytest sin red (cobertura ~94 %); CI en Ubuntu y Windows con `pytest --cov` (mínimo 90 %); despliegue a Pages en `deploy.yml`.
- Documentación en `agent/docs` (PR a `agent/qa`, se fusiona después de #1 y #2): `docs/USO.md` (guía de uso en español, con un ejemplo de tarea nuevo, `es_palindromo`, probado con respuestas grabadas), `CONTRIBUTING.md` y enlaces a ambos desde el README y `site/index.html` (apuntan a `blob/main`, así que funcionan cuando se fusione en `main`).

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
- 2026-09-30 (qa): el runner escribe la salida de pytest en un archivo en vez de usar tuberías. Con tuberías, un proceso nieto que las heredaba obligaba a esperar a que terminase (en Windows, `subprocess.run` podía colgarse pasado el límite). Del archivo se leen como mucho 256 KB (principio y final) y el recorte final conserva el final, donde está el resumen de pytest.
- 2026-09-30 (qa): el árbol de procesos se mata SIEMPRE al acabar (también tras un final normal): en Windows con un Job Object vía `ctypes` (biblioteca estándar; `taskkill /T` de respaldo) y en POSIX con `start_new_session` + `killpg`. No hace falta ninguna dependencia.
- 2026-09-30 (qa): `TMP`/`TEMP`/`TMPDIR` del subproceso apuntan a un temporal propio de la ejecución, que se borra (con reintentos en Windows).
- 2026-09-30 (qa): código de pytest 5 (sin tests) → estado `error` con mensaje claro. Un `test_task.py` con error de sintaxis se rechaza al cargar la tarea (`TaskError`) para no culpar a los modelos ni gastar llamadas.
- 2026-09-30 (qa): todos los archivos que edita el usuario (`task.md`, `test_task.py`, `meta.toml`, `--prices`, `results.json`) se leen con `utf-8-sig` para aceptar el BOM de Windows.
- 2026-09-30 (qa): `run_attempt` convierte cualquier excepción del proveedor en `provider_error` (con el tipo en el mensaje): un duelo largo y de pago no debe perderse por una respuesta rara. Los sustitutos UTF-16 sueltos (válidos en JSON) se sustituyen antes de guardar.
- 2026-09-30 (qa): respuestas sin texto de Gemini/OpenAI son `provider_error` con `finishReason`/`finish_reason`/`refusal` en el mensaje, en vez de un «sin bloque de código» engañoso.
- 2026-09-30 (qa): `MODELDUEL_HTTP_TIMEOUT` se lee y valida en cada petición (antes, un valor no numérico rompía la importación del paquete).
- 2026-09-30 (qa): argparse no trae traducciones; `SpanishArgumentParser` traduce la ayuda y los errores más habituales con una tabla de expresiones regulares, sin tocar el `gettext` global.
- 2026-09-30 (qa): códigos de salida: 0 duelo completado (aunque los modelos fallen), 1 no se pudo escribir la salida, 2 uso/configuración, 130 Ctrl+C. `--out` se comprueba antes de llamar a las APIs.
- 2026-09-30 (qa): el valor «perdedor» del informe se atenúa con `opacity: .8` solo en el número (`.num`): el `.55` anterior dejaba el rosa en 3,7:1 y el texto secundario en 2,6:1. Un test calcula el contraste AA de los acentos, del texto y del atenuado en pantalla e impresión.
- 2026-09-30 (qa): se añade `pytest-cov` SOLO al extra `dev` (no es dependencia de ejecución) para medir cobertura en el CI con un mínimo del 90 %. El subproceso de las tareas no carga el plugin porque tiene desactivada la autocarga.
- 2026-09-30 (docs): la documentación la escribe Claude Code (subagente, Sonnet) en `agent/docs`, no OpenCode, porque el sistema de permisos no permite lanzar OpenCode en modo autónomo. `AGENTS.md` lo refleja; OpenCode volverá a ser el agente docs cuando se permita su ejecución autónoma.
- 2026-09-30 (docs): los enlaces de la web a `docs/USO.md` y `CONTRIBUTING.md` apuntan a `github.com/BertMarti/modelduel/blob/main/...` (el test de la web solo admite enlaces a ese repositorio); no funcionarán hasta que la rama se fusione en `main`.

## Siguiente paso
1. lead: fusionar #1 en `main` y después #2 (cambiar su base a `main` si GitHub no lo hace solo al borrar `agent/builder`); comprobar que Pages publica la web y `demo/`.
2. lead: probar una vez `gemini:` y `openai:` contra las APIs reales con claves propias (solo se han probado con respuestas simuladas).
3. lead: fusionar el PR de `agent/docs` después de #1 y #2 y comprobar que los enlaces «Guía de uso» y «Contribuir» de la web abren los archivos en GitHub.
4. Opcional: reintentos con espera para HTTP 429/5xx y guardado incremental de `results.json` durante el duelo.

## Problemas conocidos
- El aislamiento es solo un directorio temporal + subproceso con límite + entorno sin secretos + muerte del árbol de procesos: el código del modelo puede leer y escribir en el resto del disco. Está advertido en README y web; lo ideal es usar un contenedor o VM.
- Un proceso que se desligue a propósito del árbol (`setsid`/doble fork en POSIX, `CREATE_BREAKAWAY_FROM_JOB` si el Job lo permitiera) puede sobrevivir. En Windows hay una ventana de milisegundos entre crear pytest y meterlo en el Job Object (Popen no permite crear el proceso suspendido).
- El disco que pueda llenar una solución que imprime sin parar está acotado solo por el límite de tiempo (va al temporal de la ejecución, que se borra).
- `<details>` cerrados no se despliegan al imprimir en navegadores sin `::details-content` (p. ej. Firefox antiguo); sin JavaScript no hay alternativa fiable.
- Sin reintentos ante HTTP 429/5xx: el intento queda como «error del proveedor».
- Los proveedores `gemini` y `openai` solo se prueban con respuestas simuladas (sin red); no se han probado contra las APIs reales.

## Registro de sesiones
- 2026-09-29 lead (main): creación del repositorio y reparto del equipo.
- 2026-09-29 builder (agent/builder): MVP completo (CLI, proveedores, runner, costes, informe, tareas, web, tests, CI y Pages) y PR a main.
- 2026-09-30 qa (agent/qa): revisión QA en PR #2: runner (árbol de procesos, salida acotada, UTF-8/CRLF, tareas sin tests), tareas (BOM, tests rotos, parametrize), proveedores (errores de red/HTTP, respuestas vacías), duelo resiliente, informe (escapado, `--runs`, accesibilidad AA, impresión), CLI en español con códigos coherentes, web (meta, favicon, accesibilidad) y cobertura en CI. 68 → 132 tests.
- 2026-09-30 docs · Claude Code Sonnet (agent/docs): `docs/USO.md` (guía completa en español, comprobada contra el código y ejecutando la demo y un ejemplo de tarea nuevo con respuestas grabadas), `CONTRIBUTING.md`, enlaces desde README y web, y fila docs de `AGENTS.md` actualizada.
