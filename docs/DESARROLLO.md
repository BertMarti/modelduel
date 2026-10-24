# Desarrollo de modelduel

Esta página reúne la información técnica del proyecto. Para instalarlo y usarlo, consulta la [guía de uso](USO.md). Para colaborar, sigue [CONTRIBUTING.md](../CONTRIBUTING.md).

## Estructura

```text
src/modelduel/
├── cli.py              # run, report, leaderboard, list-tasks, demo
├── tasks.py            # carga de tareas y recuento de tests
├── extract.py          # extracción del bloque de código
├── runner.py           # prompt y ejecución de pytest en temporal
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

El timeout HTTP de los proveedores reales es de 90 segundos por defecto y se cambia con `MODELDUEL_HTTP_TIMEOUT`. Los reintentos respetan `Retry-After` salvo esperas superiores a dos minutos. Un error del proveedor se registra y no detiene el resto del duelo. Los códigos de salida son `0` (duelo terminado), `1` (no se pudo escribir), `2` (uso o configuración) y `130` (Ctrl+C).

## Formato de una tarea

Una tarea es una carpeta con dos archivos obligatorios y metadatos opcionales:

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

## Proveedores y costes

`replay` lee respuestas grabadas con front-matter opcional (`input_tokens`, `output_tokens`, `latency_s`). `gemini` usa `generateContent`; `openai` usa Chat Completions compatible; `omniroute` es el preset local de OpenAI.

Los precios no están fijados en el paquete porque cambian. `--prices` acepta tarifas de entrada y salida por millón de tokens y una moneda. El coste se calcula así:

```text
coste = entrada / 1e6 × tarifa_entrada + salida / 1e6 × tarifa_salida
```

Sin tokens o sin precio, el informe muestra «sin datos». Las tarifas incluidas para `replay` son ficticias.

## Seguridad de ejecución

El runner usa un temporal propio (también como `HOME`), un subproceso limitado y un entorno depurado de secretos (`is_sensitive_var` en `runner.py`). Los límites (`resource_limits`) se aplican en el propio subproceso, sin `preexec_fn`, que no es seguro con el hilo de la señal de vida. En Linux y macOS aplica límites de CPU (el duro un segundo por encima del blando, para que llegue SIGXCPU y no SIGKILL), tamaño de archivo (256 MiB; CPython ignora SIGXFSZ y `write()` lanza `OSError [Errno 27]`, que el runner traduce a un mensaje), descriptores y volcados; el de memoria (4 GiB de espacio de direcciones, no de memoria residente) solo lo aplica Linux; en Windows usa Job Object y en POSIX un grupo de procesos para matar el árbol al terminar. Esto reduce riesgos, pero no constituye un sandbox: el código generado conserva red y acceso al disco con rutas absolutas.

## Clasificación

`modelduel leaderboard results --out site/leaderboard` agrega `results.json` y genera una página estática junto con un informe por duelo. Los resultados incompletos o ilegibles se rechazan. La clasificación usa proporciones para que un modelo no gane solo por participar en más duelos.

## Cómo se ha construido

El proyecto lo ha desarrollado un equipo de agentes de IA, cada uno en su rama y con pull requests, con supervisión humana:

- **v0.1.0:** lead, builder y qa con Claude Opus; documentación con Claude Sonnet.
- **v0.2.0:** Claude Sonnet, guiado por issues y un pull request por issue.
- **v0.4.0 a v0.7.0:** Claude Code implementó proveedores, clasificación pública, accesibilidad, duelo en directo, Markdown y señal de vida.
- **v0.8.0 (24/10/2026):** mejoras nocturnas de seguridad, interfaz y documentación con Claude Code como jefe y GPT-5.6 Luna y modelos gratuitos de OpenCode como delegados.

## Versiones

El detalle de novedades, cambios incompatibles y fechas está en el [registro de cambios](../CHANGELOG.md).

Para el entorno virtual, comandos de lint y tests, ramas, commits y pull requests, consulta [CONTRIBUTING.md](../CONTRIBUTING.md).
