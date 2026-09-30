# modelduel

**Dos modelos, una tarea, los mismos tests.** `modelduel` enfrenta a dos modelos de IA con un problema de programación, ejecuta tus tests sobre el código de cada uno y te da un informe con quién acierta, cuánto tarda y cuánto cuesta.

[![CI](https://github.com/BertMarti/modelduel/actions/workflows/ci.yml/badge.svg)](https://github.com/BertMarti/modelduel/actions/workflows/ci.yml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-b5e853.svg)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-ff7eb6.svg)

**Web:** <https://bertmarti.github.io/modelduel/> · **Informe de demostración:** <https://bertmarti.github.io/modelduel/demo/>

**Documentación:** [Guía de uso](docs/USO.md) (instalación, duelos reales, crear tus tareas, leer el informe) · [Cómo contribuir](CONTRIBUTING.md)

```text
                          A replay:alfa   B replay:beta
  -----------------------------------------------------
  Tests superados                 31/32           30/32
  Tareas resueltas                  2/3             2/3
  Tiempo del modelo              10,1 s          28,1 s
  Tokens entrada/salida       1.401/703     1.373/2.132
  Coste estimado             0,0017 USD      0,0248 USD
  (precios ficticios de demostración)
```

> [!WARNING]
> **El código generado por los modelos se ejecuta en tu máquina.** modelduel lo ejecuta siempre en un directorio temporal, en un subproceso con límite de tiempo y sin tus variables de entorno secretas, y al terminar mata todos los procesos que haya lanzado (Job Object en Windows, grupo de procesos en Linux/macOS), pero eso **no es un aislamiento real**: el código puede leer y escribir en el resto del disco, y un proceso que se desligue a propósito (`setsid`, `CREATE_BREAKAWAY_FROM_JOB`) puede sobrevivir. Úsalo solo con tareas de confianza e, idealmente, dentro de un contenedor o una máquina virtual.

## Por qué

Los rankings de modelos miden tareas que no son las tuyas. La forma honesta de elegir es hacer tu propia comparativa: el mismo enunciado, los mismos tests y los números a la vista. modelduel convierte ese ejercicio en una orden.

## Instalación

Necesitas Python 3.12 o superior. modelduel solo usa la biblioteca estándar; pytest hace falta para ejecutar los tests de las tareas.

```bash
pip install git+https://github.com/BertMarti/modelduel pytest
```

Para desarrollar:

```bash
git clone https://github.com/BertMarti/modelduel
cd modelduel
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest --cov
```

## Uso rápido

```bash
# Demo sin claves ni coste, con respuestas grabadas
modelduel run examples/tasks --a replay:alfa --b replay:beta --out runs/demo

# Dos modelos reales, tres ejecuciones por tarea
export GEMINI_API_KEY=...        # PowerShell: $env:GEMINI_API_KEY = "..."
export OPENAI_API_KEY=...
modelduel run examples/tasks --a gemini:<modelo> --b openai:<modelo> --runs 3 --prices precios.json --out runs/duelo

# Regenerar el HTML a partir de los resultados
modelduel report runs/duelo/results.json --out runs/duelo

# Ver las tareas de una carpeta
modelduel list-tasks examples/tasks
```

| Opción | Qué hace |
|---|---|
| `--a`, `--b` | Contendientes en formato `proveedor:modelo`. |
| `--runs N` | Ejecuciones por tarea (1 por defecto). Una sola ejecución es una señal débil. |
| `--timeout S` | Límite en segundos para los tests de cada respuesta (20 por defecto). |
| `--retries N` | Reintentos ante HTTP 429/500/502/503/504 y cortes de conexión, con espera exponencial y respetando `Retry-After` (3 por defecto; `0` los desactiva). |
| `--prices f.json` | Tabla de precios adicional (ver «Coste»). |
| `--replays DIR` | Carpeta de respuestas grabadas para `replay` (por defecto, `replays/` junto a la carpeta de tareas). |
| `--out DIR` | Carpeta donde se escriben `results.json` e `index.html`. Se comprueba antes de llamar a las APIs. |

Códigos de salida: `0` duelo completado (aunque los modelos fallen tests), `1` no se pudieron escribir los resultados, `2` error de uso o de configuración (argumentos, tareas, proveedores, precios, `results.json`) y `130` interrumpido con Ctrl+C.

El informe `index.html` es un único archivo autocontenido: CSS en línea, gráficas SVG, sin JavaScript y con hoja de impresión clara.

## Formato de una tarea

Una tarea es una carpeta:

```text
examples/tasks/slugify/
├── task.md        # enunciado para el modelo: pide una función concreta con nombre y firma
├── test_task.py   # tests pytest que importan de `solution`
└── meta.toml      # opcional: title, difficulty, order
```

```python
# test_task.py
from solution import slugify


def test_acentos():
    assert slugify("Canción de Añoranza") == "cancion-de-anoranza"
```

```toml
# meta.toml
title = "Convertir un texto en slug"
difficulty = "fácil"
order = 1
```

modelduel añade al enunciado la instrucción de responder con un único bloque de código Python, extrae el primer bloque `python` (o el único bloque de la respuesta), lo guarda como `solution.py` junto a una copia de `test_task.py` en un directorio temporal y ejecuta `python -m pytest` con límite de tiempo. Los resultados se leen del XML JUnit de pytest. Se distinguen estos casos: tests ejecutados, sin bloque de código, error al importar, tiempo agotado, error al ejecutar (p. ej. una tarea en la que pytest no encuentra tests) y error del proveedor. La salida de pytest se recorta conservando el principio y el final, donde está el resumen.

Los archivos de la tarea se leen en UTF-8 (se acepta el BOM de los editores de Windows) y un `test_task.py` con errores de sintaxis se rechaza antes de llamar a los modelos.

Las tres tareas de ejemplo son originales y de dificultad creciente: `slugify`, `merge_intervals` y `parse_duration`.

## Proveedores y variables de entorno

| Especificación | Qué usa | Variables |
|---|---|---|
| `replay:<nombre>` | Respuestas grabadas en `examples/replays/<nombre>/<tarea>.md`, con tokens y latencia en un front-matter. Sin red. | — |
| `gemini:<modelo>` | API REST `generateContent` de Google Generative Language. | `GEMINI_API_KEY` (obligatoria), `GEMINI_BASE_URL` (opcional) |
| `openai:<modelo>` | Cualquier API compatible con Chat Completions de OpenAI: OpenAI, OpenRouter, Ollama… | `OPENAI_API_KEY`, `OPENAI_BASE_URL` (por defecto `https://api.openai.com/v1`) |

- **OpenRouter:** `OPENAI_BASE_URL=https://openrouter.ai/api/v1` y tu clave de OpenRouter en `OPENAI_API_KEY`.
- **Ollama:** `OPENAI_BASE_URL=http://localhost:11434/v1`. En servidores locales la clave no es obligatoria.
- `MODELDUEL_HTTP_TIMEOUT` cambia el límite de las peticiones HTTP (180 s por defecto).

Las claves se leen **solo** de variables de entorno: nunca de archivos del repositorio, nunca en la URL (Gemini recibe la clave en una cabecera) y nunca en los mensajes de error ni en el informe. Tampoco llegan al subproceso que ejecuta el código de los modelos.

Formato de una respuesta grabada (`examples/replays/alfa/slugify.md`):

````markdown
---
input_tokens: 412
output_tokens: 188
latency_s: 2.84
---
```python
def slugify(text: str, separator: str = "-") -> str:
    ...
```
````

## Coste

```text
coste = entrada / 1e6 × tarifa_entrada + salida / 1e6 × tarifa_salida
```

Las tarifas son por **millón de tokens**. Como los precios reales cambian a menudo, modelduel no trae precios reales: los pones tú con `--prices`:

```json
{
  "_nota": "Precios por millón de tokens. Compruébalos en la web del proveedor.",
  "openai:mi-modelo": { "input": 0.15, "output": 0.60, "currency": "USD" },
  "gemini:otro-modelo": { "input": 0.10, "output": 0.40, "currency": "EUR" }
}
```

Se busca primero por `proveedor:modelo` y después solo por `modelo`. Si un modelo no tiene precio, o el proveedor no devuelve tokens, el coste es **«sin datos»**: nunca se inventa. Los precios integrados de `replay:alfa` y `replay:beta` son **ficticios** y el informe lo indica.

## Más documentación

- [`docs/USO.md`](docs/USO.md): guía para personas usuarias, paso a paso y con solución de problemas.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): entorno, comandos, ramas, commits y cómo añadir un proveedor o una tarea de ejemplo.

## Estructura

```text
src/modelduel/
├── cli.py              # run, report, list-tasks
├── tasks.py            # carga de tareas y recuento de tests
├── extract.py          # extracción del bloque de código
├── runner.py           # prompt + ejecución de pytest en temporal con límite
├── duel.py             # orquestación del duelo
├── results.py          # results.json y resumen del marcador
├── pricing.py          # tarifas y fórmula de coste
├── providers/          # replay, gemini, openai_compat
└── report/             # informe HTML (string.Template + SVG)
docs/USO.md             # guía de uso para personas usuarias
examples/tasks/         # tareas originales de ejemplo
examples/replays/       # respuestas grabadas de alfa y beta
site/                   # web del proyecto (la demo se genera en el CI)
tests/                  # pytest, sin llamadas de red
```

## Stack

- Python 3.12, solo biblioteca estándar en ejecución (`argparse`, `urllib`, `string.Template`, `xml.etree`, `tomllib`).
- pytest para los tests y para ejecutar las tareas; ruff para lint y formato.
- GitHub Actions: CI en Ubuntu y Windows, y despliegue en GitHub Pages de la web y del informe de demostración.

## Cómo se ha construido

Este proyecto lo ha desarrollado un **equipo de agentes de IA** —Claude Code: lead y builder (Opus), qa (Opus) y docs (Sonnet); OpenCode estaba previsto para la documentación pero no pudo ejecutarse en modo autónomo— trabajando cada uno en su rama y con pull requests, **supervisado por Alberto Martínez**. Las decisiones y el estado del proyecto están en [`MEMORY.md`](MEMORY.md) y las reglas del equipo en [`AGENTS.md`](AGENTS.md).

## Licencia

[MIT](LICENSE).
