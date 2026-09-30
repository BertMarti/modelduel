# MEMORY.md · modelduel
Última actualización: 2026-09-30 por builder (v0.2.0 · #7)

## Estado actual
v0.1.0 fusionada en `main` (MVP, revisión QA y guía de uso). Hito **v0.2.0** en curso, un PR por issue, todos contra `main` y encadenados (cada rama parte de la anterior; se fusionan en orden):
- #4 reintentos ante 429/5xx (rama `agent/builder/4-reintentos`): HECHO, en PR.
- #5 guardado incremental y `--resume` (rama `agent/builder/5-guardado-incremental`, parte de la de #4): HECHO, en PR.
- #6 liga de 2 a 6 contendientes (rama `agent/builder/6-liga`, parte de la de #5): HECHO, en PR.
- #7 publicación en PyPI (rama `agent/builder/7-pypi`, parte de la de #6): HECHO, en PR. La publicación real la dispara Alberto tras registrar el «trusted publisher» (ver PR y `CONTRIBUTING.md`).

Base heredada de v0.1.0:
- CLI `modelduel` (`run`, `report`, `list-tasks`) en `src/modelduel/`, solo biblioteca estándar. Ayuda y errores en español; códigos de salida 0/1/2/130.
- Proveedores `replay`, `gemini` (REST `generateContent`) y `openai` (Chat Completions compatible: OpenAI, OpenRouter, Ollama). Errores de red, HTTP y respuestas vacías o raras se convierten en `ProviderError` con mensaje en español.
- Reintentos (#4): `post_json` reintenta HTTP 429/500/502/503/504 y cortes de conexión (`--retries N`, 3 por defecto, `0` los desactiva) con espera exponencial (1 s × 2^n, tope 30 s) y jitter (50-100 %), respetando `Retry-After` (segundos o fecha; si pide más de 120 s no se espera). Cada reintento se avisa en consola (`~~  openai:modelo: reintento 1/3 en 1.2 s: HTTP 429 ...`).
- Guardado incremental (#5): `run_duel` llama a `on_update` tras cada intento y la CLI reescribe `results.json` de forma atómica (`.tmp` + `os.replace`, con reintentos por si Windows lo tiene abierto). `results.json` lleva `status` (`in_progress`/`complete`), `updated_at` y una huella (`fingerprint`) por tarea. Ctrl+C escribe además un informe parcial con el aviso «Duelo incompleto».
- `--resume` (`src/modelduel/resume.py`): reutiliza los intentos terminados de tareas sin cambios y repite los `provider_error`; contendientes distintos = error (exit 2); tarea cambiada, otro `--timeout` u otro `--runs` = aviso. Sin `--resume` no se sobrescribe un duelo incompleto (sí uno completo o ilegible, como en v0.1.0).
- Liga (#6): `--model/-m SPEC` repetible (2 a 6 en total, contando `--a`/`--b`, que van primero); cada contendiente recibe una letra `a`-`f` (`results.ALL_SIDES`) y `results.json` sigue con la misma estructura (`contenders`/`results` por letra), así que los de v0.1.0 se leen igual. `rank_sides` clasifica por tareas resueltas, tests y coste (el coste solo si todos tienen precio en la misma moneda); los empates comparten posición. Nombres repetidos = error.
- Informe (#6): con 2 contendientes, el duelo enfrentado de siempre (`report/html.py`, `template.html`); con 3-6, la liga (`report/league.py`, `league.html`): clasificación, comparativa con barras finas, matriz por tarea y detalle en rejilla. El CSS vive en `report/style.css` y se incrusta en ambas plantillas. Paleta AA: A lima `#b5e853`, B rosa `#ff7eb6`, C cian `#4fd1e5`, D ámbar `#ffb833`, E violeta `#b79cff`, F coral `#ff8a65` (en impresión `#4d7c0f #be185d #0e7490 #a15c00 #6d3fd6 #c2410c`).
- Demo (#6): CI, deploy y AGENTS.md generan `site/demo` con una liga de tres (`replay:alfa`, `replay:beta` y el nuevo `replay:gamma`, con precio ficticio); el CI comprueba además que `--a/--b` sigue dando un «Informe de duelo».
- Paquete (#7): versión 0.2.0 con fuente única en `src/modelduel/__init__.py` (`pyproject.toml` la lee vía hatch); metadatos completos (clasificadores, URLs, `license-files`); extra opcional `modelduel[pytest]`. Los ejemplos (`examples/`) viajan dentro de la wheel como `modelduel/examples` (`force-include`) y `modelduel demo` los localiza con `demo.py` (paquete o clon). `modelduel demo [--out DIR | --copy DIR]`: liga de tres replay sin claves, o copia de las tareas y respuestas para usarlas de plantilla.
- Publicación (#7): `.github/workflows/release.yml` (al publicar una Release: comprueba que la etiqueta `vX.Y.Z` coincide con la versión, `python -m build`, `twine check --strict`, prueba la wheel en un venv limpio y publica con `pypa/gh-action-pypi-publish@release/v1` en el environment `pypi`, con `id-token: write` solo en el job de publicación; sin tokens). El CI tiene un job `package` con los mismos pasos de construcción y comprobación. El nombre `modelduel` estaba libre en PyPI el 2026-09-30 (`/pypi/modelduel/json` daba 404).
- Runner: extrae el bloque de código, ejecuta pytest en un directorio temporal con límite de tiempo y lee el XML JUnit. Mata el árbol de procesos al terminar, acota la salida y distingue `ok`, `no_code`, `import_error`, `timeout`, `error` y `provider_error`.
- Costes con tabla ampliable (`--prices`); solo hay precios ficticios integrados para `replay:alfa` y `replay:beta`.
- Informe HTML «duelo editorial oscuro» (`string.Template`, CSS en línea, SVG con `<title>` y `aria-label`, sin JavaScript, hoja de impresión). Con `--runs` > 1 muestra «Intentos resueltos» y «suma de N ejecuciones».
- Tres tareas originales (`slugify`, `merge_intervals`, `parse_duration`) y respuestas grabadas de `alfa` y `beta`.
- Web estática en `site/index.html`; la demo `site/demo/` se genera en el CI (está en `.gitignore`).
- Tests pytest sin red (cobertura > 90 % exigida en el CI Ubuntu y Windows); despliegue a Pages en `deploy.yml`.
- Documentación: `docs/USO.md`, `CONTRIBUTING.md`.

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

- 2026-09-30 (builder): #4 no reintenta los tiempos de espera agotados (`MODELDUEL_HTTP_TIMEOUT`, 180 s por defecto: reintentar triplicaría la espera) ni los servidores apagados (`ConnectionRefusedError`, p. ej. Ollama sin arrancar) ni errores DNS; sí los cortes de una conexión ya abierta (`ConnectionError`, `RemoteDisconnected`, `IncompleteRead`). La latencia registrada es la del intento bueno, sin las esperas.
- 2026-09-30 (builder): `RetryPolicy` (en `providers/base.py`) lleva `sleep` y `rng` inyectables: los tests de reintentos no esperan y el jitter es determinista.
- 2026-09-30 (lead/builder): flujo de v0.2.0 por issues, ramas `agent/<rol>/<n>-<slug>`, PRs siempre contra `main` con `Closes #n`, y Alberto fusiona (ver `AGENTS.md`). Los PR encadenados deben fusionarse con «Create a merge commit» (no squash) y en orden.
- 2026-09-30 (builder): #5 `--resume` NO mezcla contendientes distintos (error) pero sí tolera cambios de timeout/runs/tareas con aviso; los `provider_error` se repiten porque el motivo de reanudar suele ser precisamente un fallo del proveedor. El coste de los intentos reutilizados se recalcula con la tabla de precios actual.
- 2026-09-30 (builder): #5 `tasks_solved` exige tantos intentos como `runs` para contar una tarea como resuelta: en un `results.json` parcial no cuenta como resuelta una tarea con ejecuciones sin hacer.
- 2026-09-30 (builder): #5 si falla el guardado intermedio (disco lleno) el duelo continúa con un único aviso; el guardado final sí es un error (exit 1).
- 2026-09-30 (builder): #6 el color nunca es la única pista: cada contendiente lleva su letra (etiqueta `A`-`F`) en clasificación, comparativa, matriz y detalle. Seis acentos sobre un fondo oscuro son distinguibles pero no infinitos; las letras compensan a `D` (ámbar) y `F` (coral) frente a `B` (rosa).
- 2026-09-30 (builder): #6 la matriz por tarea muestra tests superados y un estado escrito («resuelta», «no resuelta», «sin hacer»…) para no depender del color; en móvil tiene desplazamiento horizontal propio (`.table-wrap`), sin desbordar la página.
- 2026-09-30 (builder): #6 el resumen de consola pasa a ser una tabla de clasificación (una fila por contendiente) también con dos; cambia el formato impreso respecto a v0.1.0, no el contrato de la CLI ni los códigos de salida.
- 2026-09-30 (builder): #6 `replay:gamma` (respuestas originales y ficticias, precio ficticio 0,10/0,40 USD): resuelve `slugify` y `parse_duration` y falla 2 tests de `merge_intervals`. Empata con `beta` en tareas y tests y queda por delante por coste, lo que enseña el desempate.
- 2026-09-30 (builder): #7 `pytest` NO pasa a ser dependencia obligatoria (se mantiene «solo biblioteca estándar»); se añade el extra opcional `modelduel[pytest]` para instalarlo de una vez. Los ejemplos se empaquetan con `force-include` en vez de moverlos a `src/`, para no duplicar ni cambiar rutas de docs, tests y CI.
- 2026-09-30 (builder): #7 los enlaces del README son absolutos (`blob/main`) porque PyPI no resuelve rutas relativas; un test lo vigila. Ojo: apuntan a `main`, no a la etiqueta.
- 2026-09-30 (builder): #7 `twine check` no se pudo ejecutar en local (Windows bloquea la DLL `nh3` por una directiva de control de aplicaciones); sí se construyeron sdist y wheel con `python -m build` y se instaló la wheel en un venv limpio (`modelduel demo` en verde). `twine check --strict` corre en el CI (job `package`) y en `release.yml`.

## Siguiente paso
1. Alberto: fusionar los PR de v0.2.0 en orden (#4, #5, #6, #7) con «Create a merge commit».
   - Para publicar en PyPI: registrar el *trusted publisher* (PyPI > Your projects > Publishing > "Add a new pending publisher": proyecto `modelduel`, propietario `BertMarti`, repositorio `modelduel`, workflow `release.yml`, environment `pypi`), crear el environment `pypi` en GitHub (Settings > Environments) y crear la Release `v0.2.0`.
2. Alberto: probar una vez `gemini:` y `openai:` contra las APIs reales con claves propias (solo se han probado con respuestas simuladas).
3. Tras fusionar y publicar: comprobar `pip install "modelduel[pytest]"` y `modelduel demo` desde un entorno limpio, y actualizar enlaces (README/web) con el badge de PyPI si se desea.

## Problemas conocidos
- El aislamiento es solo un directorio temporal + subproceso con límite + entorno sin secretos + muerte del árbol de procesos: el código del modelo puede leer y escribir en el resto del disco. Está advertido en README y web; lo ideal es usar un contenedor o VM.
- Un proceso que se desligue a propósito del árbol (`setsid`/doble fork en POSIX, `CREATE_BREAKAWAY_FROM_JOB` si el Job lo permitiera) puede sobrevivir. En Windows hay una ventana de milisegundos entre crear pytest y meterlo en el Job Object (Popen no permite crear el proceso suspendido).
- El disco que pueda llenar una solución que imprime sin parar está acotado solo por el límite de tiempo (va al temporal de la ejecución, que se borra).
- `<details>` cerrados no se despliegan al imprimir en navegadores sin `::details-content` (p. ej. Firefox antiguo); sin JavaScript no hay alternativa fiable.
- Los proveedores `gemini` y `openai` solo se prueban con respuestas simuladas (sin red); no se han probado contra las APIs reales.

## Registro de sesiones
- 2026-09-29 lead (main): creación del repositorio y reparto del equipo.
- 2026-09-29 builder (agent/builder): MVP completo (CLI, proveedores, runner, costes, informe, tareas, web, tests, CI y Pages) y PR a main.
- 2026-09-30 qa (agent/qa): revisión QA en PR #2: runner (árbol de procesos, salida acotada, UTF-8/CRLF, tareas sin tests), tareas (BOM, tests rotos, parametrize), proveedores (errores de red/HTTP, respuestas vacías), duelo resiliente, informe (escapado, `--runs`, accesibilidad AA, impresión), CLI en español con códigos coherentes, web (meta, favicon, accesibilidad) y cobertura en CI. 68 → 132 tests.
- 2026-09-30 docs · Claude Code Sonnet (agent/docs): `docs/USO.md` (guía completa en español, comprobada contra el código y ejecutando la demo y un ejemplo de tarea nuevo con respuestas grabadas), `CONTRIBUTING.md`, enlaces desde README y web, y fila docs de `AGENTS.md` actualizada.
- 2026-09-30 builder · Claude Code Sonnet (agent/builder/4-reintentos): #4 reintentos con espera exponencial y jitter ante 429/5xx y cortes de conexión, `--retries`, avisos en consola, tests sin red ni esperas; AGENTS.md con el flujo por issues de v0.2.0.
- 2026-09-30 builder · Claude Code Sonnet (agent/builder/5-guardado-incremental): #5 guardado incremental atómico de `results.json`, `--resume`, informe parcial al cortar con Ctrl+C y tests de corte y reanudación.
- 2026-09-30 builder · Claude Code Sonnet (agent/builder/6-liga): #6 liga de 2 a 6 contendientes con `--model`, clasificación e informe de liga (paleta AA ampliada), demo de tres en CI y web, tercer contendiente `replay:gamma`.
- 2026-09-30 builder · Claude Code Sonnet (agent/builder/7-pypi): #7 paquete listo para PyPI (v0.2.0, metadatos, ejemplos dentro de la wheel, `modelduel demo`), `release.yml` con Trusted Publishing, job `package` en el CI y guía de publicación.
