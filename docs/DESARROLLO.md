# Desarrollo de modelduel

Esta página reúne la información técnica del proyecto. Para instalarlo y usarlo, consulta la [guía de uso](USO.md). Para colaborar, sigue [CONTRIBUTING.md](../CONTRIBUTING.md).

## Estructura

```text
src/modelduel/
├── cli.py              # run, init, doctor, demo, report, leaderboard, list-tasks
├── config.py           # modelduel.toml e init (catálogo de proveedores)
├── doctor.py           # comprobaciones de modelduel doctor
├── tasks.py            # carga de tareas y recuento de tests
├── node.py             # Node.js, permisos y versiones para tareas JS/TS
├── extract.py          # extracción del bloque de código
├── runner.py           # prompt y ejecución de pytest en temporal (local o contenedor)
├── sandbox.py          # --sandbox: contenedor Docker/Podman y red cortada en Linux
├── offline.py          # --solo-generar (respuestas.json) y --replay
├── duel.py             # orquestación del duelo
├── resume.py           # reanudación de un duelo interrumpido
├── demo.py             # localiza los ejemplos incluidos
├── results.py          # results.json y resumen del marcador
├── pricing.py          # tarifas y fórmula de coste
├── providers/          # replay, gemini, openai y omniroute
├── leaderboard.py      # clasificación pública y página estática
└── report/             # HTML de duelo/liga y Markdown
docs/USO.md             # guía para personas usuarias
examples/tasks/         # tareas originales de ejemplo
examples/tasks-js/      # tareas experimentales de JavaScript y TypeScript
examples/replays/       # respuestas grabadas
site/                   # web estática y demo pregrabada
tests/                  # pruebas sin llamadas de red
```

## Stack

- Python 3.12 o superior.
- Solo biblioteca estándar en ejecución: `argparse`, `urllib`, `string.Template`, `xml.etree` y `tomllib`.
- `pytest` ejecuta las tareas y las pruebas del proyecto; `ruff` comprueba lint y formato.
- Informes HTML autocontenidos con plantillas propias y gráficas SVG en línea, sin JavaScript.
- GitHub Actions ejecuta el CI en Ubuntu y Windows y despliega la web y la demo en GitHub Pages.

## Flujo técnico

`run` carga las tareas, envía el enunciado a cada proveedor y extrae el primer bloque Python utilizable. Cada respuesta se guarda como `solution.py` en un temporal y se ejecuta con un arranque `python -c` que aplica los límites del sistema (en POSIX) y llama a `pytest.main`, con límite de tiempo y XML JUnit. El resultado distingue tests ejecutados, falta de código, error de importación, tiempo agotado, error de ejecución y error del proveedor.

Los resultados se escriben incrementalmente en `results.json`; un duelo interrumpido puede continuar con `--resume`. El informe HTML es un único archivo sin JavaScript. El informe Markdown es el único camino de los datos de `results.json` al texto compartible: aplana y escapa datos no fiables, y no copia código ni salida de los modelos.

Las ligas admiten de dos a seis contendientes. La clasificación ordena por proporción de tareas resueltas, proporción de tests y coste por intento cuando los precios son comparables. Los empates comparten posición.

## Opciones principales

| Opción | Función |
|---|---|
| `--a`, `--b` | Contendientes A y B. |
| `--model`, `-m` | Contendiente repetible para ligas de 2 a 6. |
| `--runs N` | Ejecuciones por tarea; una por defecto. |
| `--timeout S` | Límite de los tests de cada respuesta; 20 segundos por defecto. |
| `--retries N` | Reintentos ante 429, 5xx y cortes de conexión; 3 por defecto. |
| `--resume` | Reanuda los intentos ya guardados en `--out`. |
| `--format` | `html`, `md` o `html,md`; HTML por defecto. |
| `--prices f.json` | Tabla de tarifas por millón de tokens. |
| `--replays DIR` | Carpeta adicional de respuestas grabadas. |
| `--out DIR` | Carpeta de `results.json` e informes. |
| `--sandbox MODO` | `auto` (por defecto), `docker`, `podman` o `ninguno`; también `aislamiento` en `modelduel.toml`. |
| `--sandbox-imagen IMAGEN` | Imagen de Python para el contenedor (por defecto, la oficial fijada por digest). |
| `--solo-generar` | Guarda `respuestas.json` y `tareas/` en `--out` sin ejecutar nada (no necesita pytest). |
| `--replay CARPETA` | Ejecuta los tests sobre esas respuestas sin llamar a ninguna API. |

El timeout HTTP de los proveedores reales es de 90 segundos por defecto y se cambia con `MODELDUEL_HTTP_TIMEOUT`. Los reintentos respetan `Retry-After` salvo esperas superiores a dos minutos. Un error del proveedor se registra y no detiene el resto del duelo. Los códigos de salida son `0` (duelo terminado), `1` (no se pudo escribir), `2` (uso o configuración) y `130` (Ctrl+C).

## Formato de una tarea

Una tarea Python es una carpeta con dos archivos obligatorios y metadatos opcionales:

```text
mi-tarea/
├── task.md        # enunciado para el modelo
├── test_task.py   # tests pytest que importan de solution
└── meta.toml      # opcional: title, difficulty, order
```

`task.md` debe pedir una función con nombre y firma exactos. `test_task.py` importa la solución desde `solution`, y puede incluir un `conftest.py`. `meta.toml` permite definir título, dificultad y orden. Los archivos se leen en UTF-8 y se acepta BOM de Windows; un error de sintaxis en los tests se detecta antes de llamar a los modelos.

```python
from solution import slugify


def test_acentos():
    assert slugify("Canción de Añoranza") == "cancion-de-anoranza"
```

El prompt añade la instrucción de responder con un único bloque de código Python. Los tests no se envían al modelo. La carpeta temporal solo recibe `test_task.py` y, si existe, `conftest.py`.

Las tareas JavaScript y TypeScript usan la misma estructura, pero el archivo de tests es `test_task.mjs` o `test_task.ts` y la solución se importa con su extensión (`./solution.mjs` o `./solution.ts`) desde un módulo ES. `meta.toml` puede declarar `language = "javascript"`, `"js"`, `"typescript"` o `"ts"`; si no aparece, se deduce del único archivo de tests. Con dos archivos hay que declararlo. Los tests usan `node:test` y `node:assert/strict`; `tasks.py` cuenta las llamadas `test(`/`it(` de primer nivel, no `t.test` ni bucles. El prompt pide un único bloque `javascript` o `typescript`, con `export function`, sin `require` ni paquetes npm; en TypeScript solo se admiten anotaciones borrables.

## Proveedores y costes

`replay` lee respuestas grabadas con front-matter opcional (`input_tokens`, `output_tokens`, `latency_s`). `gemini` usa `generateContent`; `openai` usa Chat Completions compatible; `omniroute` es el preset local de OpenAI.

Los precios no están fijados en el paquete porque cambian. `--prices` acepta tarifas de entrada y salida por millón de tokens y una moneda. El coste se calcula así:

```text
coste = entrada / 1e6 × tarifa_entrada + salida / 1e6 × tarifa_salida
```

Sin tokens o sin precio, el informe muestra «sin datos». Las tarifas incluidas para `replay` son ficticias.

## Seguridad de ejecución

El runner usa un temporal propio (también como `HOME`), un subproceso limitado y un entorno depurado de secretos (`is_sensitive_var` en `runner.py`). Los límites (`resource_limits`) se aplican en el propio subproceso, sin `preexec_fn`, que no es seguro con el hilo de la señal de vida. En Linux y macOS aplica límites de CPU (el duro un segundo por encima del blando, para que llegue SIGXCPU y no SIGKILL), tamaño de archivo (256 MiB; CPython ignora SIGXFSZ y `write()` lanza `OSError [Errno 27]`, que el runner traduce a un mensaje), descriptores y volcados; el de memoria (4 GiB de espacio de direcciones, no de memoria residente) solo lo aplica Linux; en Windows usa Job Object y en POSIX un grupo de procesos para matar el árbol al terminar. En Linux, además, pytest corre bajo un supervisor intermedio (`_SUPERVISOR`) que se declara *subreaper* con `prctl(PR_SET_CHILD_SUBREAPER)`: los procesos que se desligan con `setsid()`/doble fork siguen colgando de él y, al terminar, los mata todos recorriendo `/proc` (pruebas en `tests/test_sandbox.py`, incluido un control que demuestra que sin supervisor el nieto escaparía). Si la solución mata al supervisor, el padre busca la marca `MODELDUEL_RUN` en `/proc/*/environ`.

Para JavaScript y TypeScript, `_EXEC_BOOTSTRAP` aplica los mismos `setrlimit` y hace `os.execv` a Node bajo el mismo supervisor, grupo de procesos y red. Node se ejecuta directamente sobre el archivo de tests, no con `node --test` (que lanzaría un hijo por archivo y obligaría a permitir procesos), con `--permission` (`--experimental-permission` antes de 22.13), `--allow-fs-read` y `--allow-fs-write` limitados a la carpeta de la ejecución, `--max-old-space-size=2048`, reporter `spec` para la salida y reporter `junit` para el XML que lee el runner. En TypeScript, con Node anterior a 22.18 se añade `--experimental-strip-types`; la carpeta de trabajo lleva `package.json` con `{ "type": "module" }`. En contenedor se usa `NODE_IMAGE` de `sandbox.py`, una imagen oficial de Node fijada por digest: se actualiza igual que `DEFAULT_IMAGE`, eligiendo una etiqueta, obteniendo su digest y cambiando la constante y su prueba.

### Aislamiento (`sandbox.py`, desde v0.9.0)

- **`auto` (por defecto) en Linux:** antes de lanzar pytest, el supervisor hace `os.unshare(CLONE_NEWUSER | CLONE_NEWNET)` y escribe `setgroups`/`uid_map`/`gid_map` con el mismo UID (equivale a `unshare --map-current-user --net`, sin root) y enciende `lo` (`ioctl SIOCSIFFLAGS`, que pytest ya no puede repetir porque pierde las capacidades al hacer `execve`): la solución solo tiene `127.0.0.1`, así que los tests con servidores locales siguen funcionando (`sandbox.NETNS_ENTER`, compartido con la prueba previa). `network_isolation_available()` lo prueba una vez en un proceso aparte; si el sistema no lo permite (`kernel.apparmor_restrict_unprivileged_userns=1`, `user.max_user_namespaces=0`, algunos contenedores) `run` y `doctor` lo avisan. Si el supervisor no consigue entrar en el espacio de nombres, informa `nonet` y no ejecuta nada (`_SetupFailed`): nunca se ejecuta con red por sorpresa.
- **`docker` / `podman`:** `prepare_container` comprueba la imagen (`image inspect`; si falta, `pull` antes del duelo para que la descarga no cuente en el límite de tiempo) y el usuario (`--user UID:GID` con Docker normal, nada con Docker rootless, `--userns=keep-id` con Podman, nada en Windows). Cada ejecución lanza esta orden (`container_command`; el cliente corre con tu entorno para hablar con su demonio, pero al contenedor solo llegan las `--env` de la lista):

```text
docker run --rm --name modelduel-<aleatorio> --pull never --network none \
  --cap-drop ALL --security-opt no-new-privileges --read-only --security-opt label=disable \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m --memory 1g --memory-swap 1g --cpus 1 --pids-limit 128 \
  --user 1000:1000 \
  --mount type=bind,source=/tmp/modelduel-XXXX,target=/sandbox \
  --mount type=bind,source=<site-packages>/_pytest,target=/deps/_pytest,readonly \
  … (pytest, pluggy, iniconfig, packaging, pygments: pytest_mounts()) \
  --env HOME=/tmp --env TMPDIR=/tmp --env PYTHONPATH=/deps --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONIOENCODING=utf-8 --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  --workdir /sandbox/work --entrypoint timeout \
  python:3.13.17-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 \
  -s KILL 20 python -c <_BOOTSTRAP: setrlimit + pytest.main> <límites> \
  -q --tb=short -p no:cacheprovider --junitxml=/sandbox/junit.xml test_task.py
```

  `timeout` sale con 124 al agotar el tiempo (→ `timeout`); 128+N se traduce a la señal N (137 = SIGKILL, p. ej. por memoria); 125-127 es que Docker/Podman no pudo arrancar el contenedor (→ `error` con mensaje). Si el cliente no vuelve en `timeout + 30 s`, `docker rm -f` para el contenedor. `label=disable` quita las etiquetas SELinux de los montajes: con SELinux en «enforcing» (Fedora/RHEL, sobre todo con Podman) un bind mount sin etiquetar da «Permission denied»; se prefiere a `:z`, que reetiquetaría tus site-packages. Sin SELinux no cambia nada.
- **Prueba previa (`check_sandbox`):** antes de la primera llamada a una API, `run` hace una ejecución de prueba con el aislamiento elegido (`python -c pass` en el contenedor o bajo el supervisor con la red cortada). Si falla, la orden termina con código 2 sin gastar nada; y si el aislamiento fallara a mitad de duelo, `run_tests` lanza `RunnerError` y el duelo se para (lo hecho queda en `results.json` para `--resume`). pytest no viene en la imagen y el contenedor no tiene red: se montan de solo lectura los paquetes de Python puro de pytest y sus dependencias de este entorno.
- **Actualizar la imagen:** elige la etiqueta (`python:3.13.N-slim`), saca su digest sin descargarla con `docker buildx imagetools inspect python:3.13.N-slim` (o la cabecera `docker-content-digest` del registro) y cambia `DEFAULT_IMAGE` en `sandbox.py`; el test `test_la_imagen_es_la_oficial_de_python_fijada_por_digest` comprueba el formato.
- **Windows:** el Job Object lleva `JOB_OBJECT_LIMIT_PROCESS_MEMORY` (1 GiB de memoria comprometida por proceso; al superarla la reserva falla con `MemoryError`), `JOB_OBJECT_LIMIT_JOB_MEMORY` (2 GiB entre todos), `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` (128 procesos) y `KILL_ON_JOB_CLOSE` (`job_memory_limit_info`, probado en el CI de Windows). El proceso se crea suspendido y solo se reanuda dentro del Job.
- **Pruebas:** `tests/test_isolation.py`. El camino del contenedor se prueba con un `docker` falso que ejecuta la orden en local; los tests con Docker de verdad solo corren con `MODELDUEL_TEST_DOCKER=1` (el CI de Ubuntu lo activa) y `tests/conftest.py` oculta `docker`/`podman` al resto para que ningún test arranque contenedores por accidente.

Lo que queda sin cubrir sin contenedor: la solución puede leer y escribir rutas absolutas del disco y el espacio total que ocupa solo lo acota el tiempo.

### Solo generar y reproducir (`offline.py`, desde v0.9.0)

`run --solo-generar --out DIR` escribe `DIR/respuestas.json` (`kind: "responses"`, `schema: 1`, contendientes, `runs`, y por tarea su huella e intentos `{run, response, latency_s, input_tokens, output_tokens}` o `{run, error}`; atómico tras cada intento) y copia las tareas a `DIR/tareas/`. No ejecuta nada ni necesita pytest. `run --replay DIR` valida el JSON entero como dato no fiable (tipos, letras, specs repetidos, `status: complete`, 50 MiB como máximo), crea un `RecordedProvider` por contendiente y reutiliza `run_duel` (con `run=` para elegir la ejecución grabada): el `results.json` resultante conserva los `spec` reales, latencias y tokens. Tarea no grabada = error; tarea cambiada (huella distinta) = aviso.

## Clasificación

`modelduel leaderboard results --out site/leaderboard` agrega `results.json` y genera una página estática junto con un informe por duelo. Los resultados incompletos o ilegibles se rechazan. La clasificación usa proporciones para que un modelo no gane solo por participar en más duelos.

## Cómo se ha construido

El proyecto lo ha desarrollado un equipo de agentes de IA, cada uno en su rama y con pull requests, con supervisión humana:

- **v0.1.0:** lead, builder y qa con Claude Opus; documentación con Claude Sonnet.
- **v0.2.0:** Claude Sonnet, guiado por issues y un pull request por issue.
- **v0.4.0 a v0.7.0:** Claude Code implementó proveedores, clasificación pública, accesibilidad, duelo en directo, Markdown y señal de vida.
- **v0.8.0 (24/10/2026):** mejoras nocturnas de seguridad, interfaz y documentación con Claude Code como jefe y GPT-5.6 Luna y modelos gratuitos de OpenCode como delegados.
- **v0.9.0 (26/10/2026):** aislamiento (`--sandbox`, red cortada, memoria en Windows), solo generar/reproducir y cinco tareas nuevas; Claude Code como jefe, GPT-5.6 Luna como delegado.
- **v1.0.0 (26/10/2026):** primera versión estable; reúne lo preparado como 0.8.0 y 0.9.0 (que no llegaron a PyPI), con repaso de calidad, documentación fiel y el workflow de publicación pasando también la suite. Claude Code como jefe.
- **v1.1.0 (31/10/2026):** tareas experimentales de JavaScript y TypeScript con Node y el mismo runner endurecido.

## Versiones

El detalle de novedades, cambios incompatibles y fechas está en el [registro de cambios](../CHANGELOG.md).

Para el entorno virtual, comandos de lint y tests, ramas, commits y pull requests, consulta [CONTRIBUTING.md](../CONTRIBUTING.md).
