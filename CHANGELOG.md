# Registro de cambios

Todos los cambios relevantes de modelduel se anotan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.9.0] - 2026-10-26

### Seguridad

- **`--sandbox docker` / `--sandbox podman`**: cada ejecución de los tests corre en un contenedor desechable de la imagen oficial `python:3.13.17-slim` fijada por digest, sin red (`--network none`), sin privilegios (`--cap-drop ALL`, `no-new-privileges`, usuario sin root), con el sistema de archivos de solo lectura salvo la carpeta de la ejecución y un `/tmp` en memoria de 64 MiB, 1 GiB de memoria sin swap, 1 CPU y 128 procesos. La imagen se descarga antes del duelo; si Docker o Podman no están instalados, un error en español dice cómo instalarlos. También con `aislamiento = "docker"` en `modelduel.toml`.
- **Red cortada por defecto en Linux** (`--sandbox auto`): el supervisor entra en un espacio de nombres de usuario y de red propio (como `unshare --map-current-user --net`, sin root). Si el sistema no lo permite, `run` y `doctor` lo avisan; si falla a mitad, no se ejecuta nada. `--sandbox ninguno` lo desactiva.
- **Límite de memoria en Windows**: `JOB_OBJECT_LIMIT_PROCESS_MEMORY` (1 GiB por proceso) y `KILL_ON_JOB_CLOSE` en el Job Object del runner. Los tests arrancan suspendidos y solo se reanudan dentro del Job con el límite; si no se puede poner, no se ejecutan.
- `--replay` trata la carpeta como dato no fiable: `respuestas.json` de 50 MiB como máximo, de 1 a 100 ejecuciones, y tareas sin enlaces simbólicos ni más de 2000 archivos o 50 MiB.

### Añadido

- **Modo solo generar**: `modelduel run … --solo-generar --out CARPETA` guarda las respuestas (`respuestas.json`) y una copia de las tareas sin ejecutar nada (no necesita pytest); `modelduel run --replay CARPETA [--sandbox docker]` ejecuta después los tests, en otra máquina o en un contenedor, sin llamar a ninguna API.
- `modelduel doctor`: apartado «Aislamiento disponible» (Docker/Podman, red cortada o nada) con la opción recomendada.
- Cinco tareas de ejemplo nuevas con respuestas grabadas: `flatten_json` (JSON), `csv_totals` (CSV), `wrap_text` (texto), `grid_path` y `topo_order` (algoritmos). La demo enseña también los estados «sin código» y «error de importación».
- CI: tests y un duelo con Docker de verdad en Ubuntu, el límite de memoria en Windows y el flujo generar → reproducir.

## [0.8.0] - 2026-10-24

### Seguridad

- **Los procesos que se desligan ya no sobreviven** (Linux): los tests corren bajo un supervisor intermedio que se declara «subreaper» con `prctl(PR_SET_CHILD_SUBREAPER)` (sin privilegios), así que un nieto que haga `setsid()` o un doble fork sigue colgando de él; al terminar, al agotar el tiempo o con Ctrl+C mata a todos sus descendientes recorriendo `/proc`. Si la solución mata a su supervisor, el padre busca y mata los procesos que conservan la marca `MODELDUEL_RUN` en su entorno, y el intento no cuenta como resuelto. En macOS sigue el grupo de procesos y en Windows el Job Object.
- **CSP sin `'unsafe-inline'` en `style-src`**: los `<style>` de informes, clasificación y portada se autorizan por su hash SHA-256 (todas las webs de Pages de BertMarti comparten el origen `bertmarti.github.io`).
- **Ejecución del código de los modelos endurecida** (`runner.py`): en POSIX el subproceso arranca con `setrlimit` (4 GiB de espacio de direcciones, que solo aplica Linux; CPU = límite de tiempo + 5 s, con el duro un segundo por encima para que llegue SIGXCPU; archivos de 256 MiB como máximo, con un mensaje claro si se superan; 256 descriptores y sin volcados de memoria) mediante un arranque `python -c` que después llama a `pytest.main`, sin `preexec_fn` (no es seguro con el hilo de la señal de vida). `HOME`, `USERPROFILE`, `APPDATA` y `XDG_*` apuntan al temporal de la ejecución, y el filtro de entorno quita también `PASS*`, `AUTH` (`SSH_AUTH_SOCK`), `PRIVATE`, `COOKIE`, `SESSION`, `SIGNATURE`, `DSN`, `PROXY`, `WEBHOOK`, `_PWD`, `DATABASE_URL`, `DOCKER_HOST`, `KUBECONFIG`, `GNUPGHOME` y rutas a configuraciones con credenciales (`AWS_CONFIG_FILE`, `NETRC`, `DOCKER_CONFIG`…) Un final por señal (`SIGXCPU`, `SIGXFSZ`, `SIGKILL`) se explica en el mensaje.
- **Content-Security-Policy** en los informes, la clasificación (`default-src 'none'`, sin scripts) y la portada (`script-src 'self'`): defensa en profundidad frente a XSS con salidas de modelos.
- CI: job «Seguridad» con gitleaks (binario con suma SHA-256 comprobada, todo el historial) y pip-audit; Dependabot semanal y agrupado; `SECURITY.md`; el despliegue de Pages da `pages` e `id-token` solo al job que despliega.

### Añadido

- **`modelduel init`**: prepara una carpeta con tareas de ejemplo, respuestas grabadas y un `modelduel.toml` comentado; con `--proveedor gemini|openai|openrouter|ollama|omniroute` explica qué variables definir (Linux/macOS y PowerShell), dónde conseguir la clave y dónde mirar los modelos.
- **`modelduel.toml`**: `modelduel run` sin argumentos usa la configuración de la carpeta actual (o `--config`); lo que se pase en la orden manda. Errores guiados para TOML roto, claves desconocidas, tipos y marcadores `CAMBIA-ESTO` sin editar.
- **`modelduel doctor`**: comprueba Python, pytest, ejemplos, la protección del runner, las variables de entorno (sin mostrar nunca las claves), la configuración y, con `--red`, la lista de modelos de cada proveedor (no gasta tokens). Sale con 1 si algo falla.
- `modelduel` sin orden muestra los primeros pasos; si falta una clave, el error dice cómo definirla y remite a `modelduel doctor`.
- `mypy` en el extra `dev` y en el CI (configuración ligera en `pyproject.toml`); el CI prueba también Python 3.13.
- README para personas usuarias con cabecera propia (`docs/img/banner.svg`) y capturas; lo técnico pasa a `docs/DESARROLLO.md`.
- `PLAN.md`, subagentes en `.claude/agents/` y skills en `.claude/skills/` para trabajar en el repo con Claude Code.

### Corregido

- `tests/test_resume.py` no se recogía en Python 3.13 (docstring con `\ud800` sin prefijo `r`).
- Portada en el móvil: la marca y los enlaces de la navegación se apretaban en 390 px; ahora van en dos filas con zona táctil cómoda y los botones ocupan el ancho.
- Informes y clasificación en el móvil: la columna «Pos.» medía 170 px y el pie de la tabla se salía de la pantalla.
- Nueve avisos de tipos de mypy sin cambio de comportamiento.

## [0.7.0] - 2026-10-01

### Añadido

- **Señal de vida** en las llamadas largas: mientras un proveedor real (no `replay:`) tarda más de unos 10 s, la CLI escribe por `stderr` cada 10 s `  ··  esperando a gemini:modelo (tarea slugify)… 30 s`. Un hilo con `threading.Event` (`modelduel.heartbeat.Heartbeat`) que se para siempre, también ante un error o Ctrl+C ([#48](https://github.com/BertMarti/modelduel/issues/48)).
- Insignia de PyPI en el README y enlace a <https://pypi.org/project/modelduel/> en la web (apartado de instalación y pie); `tests/test_site.py` admite pypi.org de forma explícita ([#18](https://github.com/BertMarti/modelduel/issues/18)).

### Cambiado

- El límite por defecto de las peticiones HTTP baja de 180 s a **90 s** (`MODELDUEL_HTTP_TIMEOUT` lo cambia). La guía de uso explica, junto a los reintentos, que si parece colgado es que espera respuesta y que Ctrl+C guarda lo hecho y `--resume` lo retoma ([#48](https://github.com/BertMarti/modelduel/issues/48)).
- Retirados de README, `docs/USO.md` y la web los avisos «se publica al crear la release»: el paquete ya está en PyPI (desde v0.6.0) y la instalación recomendada es `pip install "modelduel[pytest]"` ([#19](https://github.com/BertMarti/modelduel/issues/19)).

## [0.6.0] - 2026-10-01

### Añadido

- **Informe en Markdown**: `modelduel report results.json --format md --out DIR` y `modelduel run ... --format html,md` generan `informe.md`, listo para pegar en un PR o un issue de GitHub: marcador, veredicto con su criterio, tabla por tarea y por contendiente (duelo de dos y liga), coste y avisos («una sola ejecución es una señal débil»). `--format` acepta `html` (por defecto), `md` o `html,md`; un formato desconocido es un error de uso. No copia el código ni la salida de los modelos ([#38](https://github.com/BertMarti/modelduel/issues/38), [#39](https://github.com/BertMarti/modelduel/issues/39)).
- El CI genera y comprueba el informe Markdown de la demo.
- **Imagen social** de la web: `site/og.png` (1200×630) y las metas `og:image`, `og:image:width`, `og:image:height`, `og:image:alt` y `twitter:card=summary_large_image` ([#44](https://github.com/BertMarti/modelduel/issues/44)).

### Seguridad

- Todo texto procedente de `results.json` se trata como dato no fiable en el Markdown: se aplana a una línea, se quitan controles y marcas de dirección Unicode, y se escapan barras de tabla, backticks, HTML, enlaces, imágenes, entidades y autoenlaces. Como GitHub enlaza `@usuario`, `#12`, `GH-12`, los SHA de commit (7 a 40 hexadecimales) y correos después de leer el Markdown (comprobado con la API de renderizado de GFM), se inserta un espacio de ancho cero tras `@` y `#`, dentro de `GH-12` y dentro de cada SHA. Un `results.json` que falla al renderizar ya no deja a cero un `informe.md` previo, y el informe parcial de un Ctrl+C respeta `--format`. Hay tests de regresión con contenido hostil ([#38](https://github.com/BertMarti/modelduel/issues/38)).

## [0.5.0] - 2026-10-01

### Añadido

- **Duelo en directo** en la web (`#demo`): reproduce en el navegador, durante unos 25 s, un duelo **pregrabado** (el primero de `demo/results.json`, que genera el CI): enunciado, cada modelo escribiendo su código a ritmo proporcional a su latencia, contadores de tokens, tests que caen uno a uno con ✓/✗ y texto, barras y marcador final con veredicto y enlace al informe completo. El veredicto es solo de esa tarea («En esta tarea (…, 1 de N), gana …») y avisa de que el informe completo agrega todas las tareas y puede dar otro orden. Sin servidor, sin claves y sin ejecutar nada. Pausar/Reanudar está siempre en el botón principal y Detener aparece mientras hay un duelo (al detener, el foco vuelve al botón principal); se pausa al cambiar de pestaña, no arranca solo y, con `prefers-reduced-motion`, avanza con «Siguiente». Si los datos grabados son largos se recortan avisando («… (recortado)», «mostrando 200 de N» tests). Sin JavaScript queda un enlace al informe estático. El script es vanilla (`site/demo.js`, diferido), escribe solo con `textContent` y su lógica se prueba con `node --test` ([#32](https://github.com/BertMarti/modelduel/issues/32)).
- Job `web` en el CI: ejecuta `node --test tests/js` y comprueba que la portada solo carga su propio `demo.js`.

### Cambiado

- **Informes accesibles**: subrayado de enlaces visible y foco de teclado en todos los enlaces, el valor peor de cada métrica se marca con «▼ peor» (y el mejor con «▲ mejor») en lugar de atenuarlo con `opacity`, ningún texto por debajo de 12 px y un enlace «modelduel · web» en el pie ([#30](https://github.com/BertMarti/modelduel/issues/30)).
- **Portada**: jerarquía de acciones (una primaria, una secundaria y enlaces), navegación de cinco enlaces, tabla de proveedores como región desplazable accesible con foco, y la fila de `omniroute`. Se retiran las barras fijas del hero, que no tenían letra ni significado ([#31](https://github.com/BertMarti/modelduel/issues/31)).

## [0.4.0] - 2026-10-01

### Añadido

- **Proveedor `omniroute:<modelo>`** para el router local OmniRoute (API compatible con OpenAI, `http://localhost:20128/v1`; `OMNIROUTE_BASE_URL` y `OMNIROUTE_API_KEY` opcional). Es un preset de `openai:`: mismos reintentos y errores, más el aviso «Arranca OmniRoute con `omniroute serve`» si el servidor no responde ([#23](https://github.com/BertMarti/modelduel/issues/23)).
- **Clasificación pública**: `modelduel leaderboard results/ --out DIR` agrega los `results.json` de una carpeta (uno por duelo o liga) y genera una página estática, sin JavaScript, con la clasificación por modelo (proporción de tareas resueltas, tests, nº de duelos y coste) y el histórico de duelos con un informe regenerado de cada uno. Se compara por proporciones, no por totales, para que jugar más duelos no dé ventaja. La carpeta `results/` trae tres duelos y ligas `replay` de ejemplo ([#24](https://github.com/BertMarti/modelduel/issues/24)).
- El CI y el despliegue generan la clasificación en `site/leaderboard/` (la web la enlaza) y el CI comprueba que no lleva JavaScript. La guía explica cómo añadir resultados reales ([#25](https://github.com/BertMarti/modelduel/issues/25)).

### Corregido

- Los informes regenerados desde un `results.json` ajeno ya no inyectan HTML: la moneda del veredicto «gana A por coste (…)» se escapa y un `failed` o `errors` que no sea un número da un error limpio. En la clasificación, el coste se compara por intento (con `--runs N` contaba N veces).

## [0.3.0] - 2026-10-01

### Cambiado

- El aviso de reintento muestra la espera en formato español (`reintento 1/3 en 1,2 s`), con el mismo formateador que el resto de la salida ([#17](https://github.com/BertMarti/modelduel/issues/17)).
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

[Sin publicar]: https://github.com/BertMarti/modelduel/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/BertMarti/modelduel/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/BertMarti/modelduel/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/BertMarti/modelduel/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/BertMarti/modelduel/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/BertMarti/modelduel/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/BertMarti/modelduel/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/BertMarti/modelduel/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/BertMarti/modelduel/releases/tag/v0.1.0
