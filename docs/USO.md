# Guía de uso de modelduel

Esta guía es para quien quiere **usar** modelduel, no para quien quiere modificar su código (para eso, mira [`CONTRIBUTING.md`](../CONTRIBUTING.md)). No hace falta saber programar en profundidad: si sabes abrir una terminal y copiar órdenes, puedes seguirla.

## Índice

1. [Qué es y cuándo usarlo](#qué-es-y-cuándo-usarlo)
2. [Instalación](#instalación)
3. [Tu primer duelo con la demo](#tu-primer-duelo-con-la-demo)
4. [Un duelo real con modelos de verdad](#un-duelo-real-con-modelos-de-verdad)
   - [Gemini](#gemini)
   - [OpenAI](#openai)
   - [OpenRouter](#openrouter)
   - [Ollama (modelos en tu ordenador)](#ollama-modelos-en-tu-ordenador)
5. [Crear tu propia tarea paso a paso](#crear-tu-propia-tarea-paso-a-paso)
6. [Leer el informe](#leer-el-informe)
7. [Opciones: `--runs`, `--timeout`, `--resume` y `--prices`](#opciones---runs---timeout---resume-y---prices)
8. [Códigos de salida](#códigos-de-salida)
9. [Seguridad: qué aísla y qué no](#seguridad-qué-aísla-y-qué-no)
10. [Preguntas frecuentes y solución de problemas](#preguntas-frecuentes-y-solución-de-problemas)

---

## Qué es y cuándo usarlo

modelduel es una herramienta de terminal que **enfrenta a dos modelos de inteligencia artificial con el mismo problema de programación**:

1. Envía el mismo enunciado a los dos modelos y les pide una función en Python.
2. Guarda la respuesta de cada uno y le pasa **tus tests** (los mismos para los dos).
3. Te da un informe con quién acierta más, cuánto tarda, cuántos tokens gasta y cuánto cuesta.

Úsalo cuando tengas que **elegir un modelo para tu trabajo** y no te fíes de los rankings generales, porque miden tareas que no son las tuyas. También sirve para comprobar si un modelo barato o pequeño (por ejemplo, uno que corre en tu ordenador con Ollama) te basta para lo que haces.

Ten en cuenta dos límites:

- Solo evalúa **funciones de Python** que se pueden comprobar con tests automáticos.
- **Una sola ejecución es una señal débil**: los modelos no son deterministas. Repite el duelo (`--runs`) y usa tareas de tu propio trabajo.

> **Aviso importante:** el código que escriben los modelos **se ejecuta en tu ordenador**. Lee la sección de [seguridad](#seguridad-qué-aísla-y-qué-no) antes de usar tareas o modelos que no controles.

---

## Instalación

Necesitas:

- **Python 3.12 o superior.**
- **Git**, para descargar el proyecto.
- **pytest** en el mismo entorno de Python (modelduel lo usa para ejecutar los tests de las tareas; no es una dependencia del programa y por eso se instala aparte).

modelduel no necesita ninguna otra biblioteca.

### Windows (PowerShell)

```powershell
git clone https://github.com/BertMarti/modelduel
cd modelduel
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e . pytest
modelduel --version
```

Si PowerShell se queja de que la ejecución de scripts está deshabilitada al activar el entorno, no hace falta activarlo: usa `.venv\Scripts\python.exe -m modelduel` donde esta guía dice `modelduel`.

### Linux y macOS

```bash
git clone https://github.com/BertMarti/modelduel
cd modelduel
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e . pytest
modelduel --version
```

Si todo va bien, `modelduel --version` escribe `modelduel 0.1.0` (o la versión actual).

**Cada vez que abras una terminal nueva** tienes que volver a activar el entorno (`.venv\Scripts\Activate.ps1` en Windows, `source .venv/bin/activate` en Linux y macOS) o no encontrará la orden `modelduel`.

### Instalarlo sin clonar el proyecto

También puedes instalarlo directamente desde GitHub:

```bash
pip install git+https://github.com/BertMarti/modelduel pytest
```

Así tendrás la orden `modelduel`, pero no las tareas y respuestas de ejemplo (`examples/`), que solo están en el repositorio clonado. Para la demo de la sección siguiente necesitas clonarlo.

---

## Tu primer duelo con la demo

La demo no necesita claves ni cuesta nada: usa respuestas **grabadas y ficticias** de tres «modelos» llamados `alfa`, `beta` y `gamma` (proveedor `replay`): es una liga de tres contendientes. Desde la carpeta `modelduel` con el entorno activado:

```bash
modelduel run examples/tasks --model replay:alfa --model replay:beta --model replay:gamma --out runs/demo
```

(En Windows, la misma orden; las barras de las rutas también funcionan.) Verás algo así:

```text
modelduel 0.1.0 · 3 tareas · 1 ejecución por tarea
  A  replay:alfa
  B  replay:beta
  C  replay:gamma
  Aviso: el código de los modelos se ejecuta en esta máquina (temporal + límite).

  ok  slugify                  A  8/8
  --  slugify                  B  6/8
  ok  slugify                  C  8/8
  ok  merge_intervals          A  8/8
  ok  merge_intervals          B  8/8
  --  merge_intervals          C  6/8
  --  parse_duration           A  15/16
  ok  parse_duration           B  16/16
  ok  parse_duration           C  16/16

  #   Contendiente     Tareas   Tests   Tiempo   Tokens (ent/sal)        Coste
  ----------------------------------------------------------------------------
  1   A replay:alfa       2/3   31/32   10,1 s          1.401/703   0,0017 USD
  2   C replay:gamma      2/3   30/32    3,7 s          1.314/426   0,0003 USD
  3   B replay:beta       2/3   30/32   28,1 s        1.373/2.132   0,0248 USD
  (precios ficticios de demostración)

  Resultados  runs\demo\results.json
  Informe     runs\demo\index.html
```

Cada línea `ok` o `--` es un intento: `ok` significa que superó **todos** los tests de la tarea, `--` que falló alguno (el número es «tests superados/tests totales»). Al final tienes la clasificación (tareas resueltas, luego tests superados y luego coste) y dos archivos en `runs/demo`:

- `index.html`: el informe. Ábrelo con doble clic en cualquier navegador.
- `results.json`: todos los datos en bruto.

`gamma` empata con `beta` en tareas y en tests, pero es mucho más barato, así que queda por delante: ese es el desempate por coste. Con `--a` y `--b` sigues teniendo el duelo de dos de siempre (`modelduel run examples/tasks --a replay:alfa --b replay:beta --out runs/demo`).

Otras dos órdenes útiles:

```bash
# Lista las tareas de una carpeta, con su número de tests
modelduel list-tasks examples/tasks

# Regenera el informe HTML a partir de un results.json (por ejemplo, tras actualizar modelduel)
modelduel report runs/demo/results.json --out runs/demo
```

Las tareas de ejemplo son `slugify` (fácil), `merge_intervals` (media) y `parse_duration` (difícil).

---

## Un duelo real con modelos de verdad

Un contendiente se escribe como `proveedor:modelo`. Hay tres proveedores:

| Proveedor | Para qué sirve | Variables de entorno |
|---|---|---|
| `replay:<nombre>` | Respuestas grabadas, sin red ni coste (la demo). | Ninguna |
| `gemini:<modelo>` | La API de Google Gemini. | `GEMINI_API_KEY` (obligatoria), `GEMINI_BASE_URL` (opcional) |
| `openai:<modelo>` | Cualquier API compatible con «Chat Completions» de OpenAI: OpenAI, OpenRouter, Ollama… | `OPENAI_API_KEY`, `OPENAI_BASE_URL` (por defecto `https://api.openai.com/v1`) |

Antes de empezar, ten en cuenta:

- Las **claves** se leen **solo de variables de entorno**, nunca de archivos. Nunca las escribas dentro del proyecto ni las subas a GitHub.
- **Cada llamada a una API real puede costar dinero.** El número de llamadas es `tareas × ejecuciones × contendientes`. Con las tres tareas de ejemplo, dos contendientes y `--runs 3` son 18 llamadas (en una liga de seis, 54).
- El nombre del `<modelo>` es el que use el proveedor (consulta su documentación). En esta guía se escribe `<modelo>` para que pongas el tuyo.
- Las variables de entorno solo valen para la terminal donde las defines y desaparecen al cerrarla. Cambia `PEGA_AQUI_TU_CLAVE` por tu clave real.
- Los dos contendientes `openai:` de una misma orden comparten `OPENAI_BASE_URL` y `OPENAI_API_KEY`. Si quieres comparar dos modelos de OpenRouter, usa `openai:` para los dos; si quieres comparar Gemini con uno de OpenRouter, usa `gemini:` y `openai:`.

### Gemini

Crea una clave en Google AI Studio y defínela.

PowerShell (Windows):

```powershell
$env:GEMINI_API_KEY = "PEGA_AQUI_TU_CLAVE"
```

Linux y macOS:

```bash
export GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"
```

Después, por ejemplo, Gemini contra la demo (útil para probar que la clave funciona):

```bash
modelduel run examples/tasks --a gemini:<modelo> --b replay:beta --out runs/gemini
```

### OpenAI

PowerShell:

```powershell
$env:OPENAI_API_KEY = "PEGA_AQUI_TU_CLAVE"
```

Linux y macOS:

```bash
export OPENAI_API_KEY="PEGA_AQUI_TU_CLAVE"
```

```bash
modelduel run examples/tasks --a openai:<modelo-1> --b openai:<modelo-2> --out runs/openai
```

O contra Gemini (con las dos claves definidas):

```bash
modelduel run examples/tasks --a gemini:<modelo> --b openai:<modelo> --runs 3 --out runs/duelo
```

### OpenRouter

OpenRouter da acceso a muchos modelos con una sola clave. Usa el proveedor `openai:` apuntando a la dirección de OpenRouter y **tu clave de OpenRouter** en `OPENAI_API_KEY`.

PowerShell:

```powershell
$env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
$env:OPENAI_API_KEY = "PEGA_AQUI_TU_CLAVE_DE_OPENROUTER"
```

Linux y macOS:

```bash
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_API_KEY="PEGA_AQUI_TU_CLAVE_DE_OPENROUTER"
```

```bash
modelduel run examples/tasks --a openai:<modelo-1> --b openai:<modelo-2> --out runs/openrouter
```

Los nombres de modelo de OpenRouter suelen llevar una barra (`autor/modelo`) y, a veces, dos puntos (`autor/modelo:free`). Ambas cosas funcionan: modelduel separa el proveedor del modelo por el **primer** `:`.

### Ollama (modelos en tu ordenador)

Con [Ollama](https://ollama.com) los modelos corren en tu máquina, sin coste por llamada. Instala Ollama, descarga un modelo (`ollama pull <modelo>`) y asegúrate de que el servicio está en marcha.

PowerShell:

```powershell
$env:OPENAI_BASE_URL = "http://localhost:11434/v1"
```

Linux y macOS:

```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
```

```bash
modelduel run examples/tasks --a openai:<modelo-local> --b gemini:<modelo> --out runs/local
```

Con una dirección local (`localhost`, `127.0.0.1`…) **no hace falta `OPENAI_API_KEY`**. Si la dirección no es local, sí es obligatoria.

Los modelos locales pueden ser lentos: si las peticiones se cortan por tiempo, sube el límite de red con la variable `MODELDUEL_HTTP_TIMEOUT` (segundos; 180 por defecto), por ejemplo `$env:MODELDUEL_HTTP_TIMEOUT = "600"` en PowerShell o `export MODELDUEL_HTTP_TIMEOUT=600` en Linux y macOS.

Para volver a usar OpenAI de verdad después de OpenRouter u Ollama, quita la variable: `Remove-Item Env:OPENAI_BASE_URL` (PowerShell) o `unset OPENAI_BASE_URL` (Linux y macOS), o cierra la terminal.

---

## Crear tu propia tarea paso a paso

Una tarea es una **carpeta** con dos archivos obligatorios (`task.md` y `test_task.py`) y uno opcional (`meta.toml`). Vamos a crear una nueva, «detectar palíndromos», y a probarla sin gastar nada.

### Paso 1. La estructura

Crea una carpeta de tareas y, dentro, una carpeta por tarea. **El nombre de la carpeta es el identificador de la tarea.** Al lado, una carpeta `replays` para las respuestas de prueba del paso 5:

```text
mis-tareas/
└── es_palindromo/
    ├── task.md
    ├── test_task.py
    └── meta.toml
replays/
```

### Paso 2. El enunciado (`task.md`)

Es lo que lee el modelo. Pide **una función concreta con nombre y firma exactos** y define las reglas sin ambigüedad: lo que no esté escrito aquí, los modelos lo interpretarán cada uno a su manera. Un título con `#` al principio se usa como título de la tarea si no hay `meta.toml`.

`mis-tareas/es_palindromo/task.md`:

````markdown
# Detectar palíndromos

Escribe una función de Python con esta firma exacta:

```python
def es_palindromo(texto: str) -> bool:
```

Devuelve `True` si el texto se lee igual de izquierda a derecha que de derecha a izquierda,
y `False` en caso contrario. Reglas:

1. Se ignoran las mayúsculas y las minúsculas.
2. Se ignoran las tildes: `á` cuenta como `a`.
3. Solo cuentan las letras y los dígitos; espacios y signos de puntuación se ignoran.
4. Un texto sin ninguna letra ni dígito (por ejemplo, `""` o `"¡?"`) se considera palíndromo.

Ejemplos:

- `es_palindromo("Anita lava la tina")` → `True`
- `es_palindromo("Átale, demoníaco Caín, o me delata")` → `True`
- `es_palindromo("modelduel")` → `False`
````

No hace falta que el enunciado diga cómo responder: modelduel le añade solo las instrucciones de formato (un único bloque de código Python, sin tests, respetando nombre y firma).

### Paso 3. Los tests (`test_task.py`)

Son tests normales de [pytest](https://docs.pytest.org). La solución del modelo se guarda como `solution.py`, así que los tests la importan con `from solution import ...`. **Incluye casos límite**: son los que separan a un modelo que entiende el enunciado de uno que solo se parece a la respuesta correcta.

`mis-tareas/es_palindromo/test_task.py`:

```python
import pytest

from solution import es_palindromo


def test_frase_sencilla():
    assert es_palindromo("Anita lava la tina") is True


def test_no_es_palindromo():
    assert es_palindromo("modelduel") is False


def test_ignora_tildes_y_puntuacion():
    assert es_palindromo("Dábale arroz a la zorra el abad") is True
    assert es_palindromo("¿Acaso hubo búhos acá?") is True


@pytest.mark.parametrize("texto", ["", "   ", "¡?"])
def test_sin_letras_ni_digitos(texto):
    assert es_palindromo(texto) is True


def test_los_digitos_cuentan():
    assert es_palindromo("12321") is True
    assert es_palindromo("1232") is False
```

Este archivo tiene **7 tests** (`@pytest.mark.parametrize` con una lista escrita en el propio decorador cuenta un test por valor). Reglas prácticas:

- Debe ser un archivo `test_task.py` autocontenido y con la sintaxis correcta: si tiene un error de sintaxis, modelduel lo rechaza antes de llamar a ningún modelo (así no gastas dinero).
- Solo se copian a la ejecución `test_task.py` y, si existe, un `conftest.py` de la carpeta de la tarea. **Otros archivos (datos, módulos auxiliares) no se copian.**
- Los archivos se leen en UTF-8 (se acepta el BOM que añaden algunos editores de Windows).
- Si un modelo nombra mal la función, los tests no podrán importarla y el intento saldrá como «no se pudo importar» en el informe.

### Paso 4. Los metadatos (`meta.toml`, opcional)

`mis-tareas/es_palindromo/meta.toml`:

```toml
title = "Detectar palíndromos"
difficulty = "fácil"
order = 1
```

- `title`: título en el informe (si falta, se usa el título `#` del enunciado y, si tampoco hay, el nombre de la carpeta).
- `difficulty`: etiqueta libre (`fácil`, `media`, `difícil`…) que se muestra en el informe.
- `order`: número para ordenar las tareas (de menor a mayor; sin `order`, después y por nombre de carpeta).

Comprueba que modelduel la reconoce y cuenta bien los tests:

```bash
modelduel list-tasks mis-tareas
```

```text
es_palindromo   7 tests  Detectar palíndromos  [fácil]
```

### Paso 5. Probarla sin gastar nada

Antes de gastar dinero en llamadas reales, comprueba tu tarea con dos respuestas grabadas hechas a mano. Un contendiente `replay:<nombre>` lee sus respuestas de `replays/<nombre>/<id_de_la_tarea>.md`, y modelduel busca la carpeta `replays` **junto a la carpeta de tareas** (aquí, `replays` está al lado de `mis-tareas`). Si la tienes en otro sitio, indícala con `--replays DIR`.

Un modelo «bueno», en `replays/bueno/es_palindromo.md`:

````markdown
---
input_tokens: 210
output_tokens: 95
latency_s: 1.8
---
```python
import unicodedata


def es_palindromo(texto: str) -> bool:
    base = unicodedata.normalize("NFKD", texto)
    limpio = [c.lower() for c in base if c.isalnum()]
    return limpio == limpio[::-1]
```
````

Un modelo «flojo» que olvida las tildes y la puntuación, en `replays/flojo/es_palindromo.md`:

````markdown
---
input_tokens: 205
output_tokens: 60
latency_s: 1.1
---
```python
def es_palindromo(texto: str) -> bool:
    t = texto.lower().replace(" ", "")
    return t == t[::-1]
```
````

El bloque entre `---` es opcional: da los tokens y la latencia (en segundos) que se mostrarán en el informe. Sin él, los tokens aparecen como «sin datos» (y con ellos el coste) y el tiempo del modelo como 0 s. Ahora, el duelo:

```bash
modelduel run mis-tareas --a replay:bueno --b replay:flojo --out runs/palindromo
```

```text
  ok  es_palindromo            A  7/7
  --  es_palindromo            B  5/7

                          A replay:bueno   B replay:flojo
  -------------------------------------------------------
  Tests superados                    7/7              5/7
  Tareas resueltas                   1/1              0/1
  ...
```

Si el modelo «bueno» saca 7/7 y el «flojo» falla algunos, tu tarea distingue bien. Si los dos sacan 7/7, tus tests son demasiado blandos; si el bueno falla, revisa el enunciado o los tests.

### Paso 6. El duelo real

Con las variables de entorno de la sección anterior:

```bash
modelduel run mis-tareas --a gemini:<modelo> --b openai:<modelo> --runs 3 --out runs/palindromo-real
```

Puedes pasar a `run` la carpeta con todas las tareas (`mis-tareas`) o la carpeta de una sola (`mis-tareas/es_palindromo`).

---

## Leer el informe

`index.html` es un único archivo: no necesita conexión, no usa JavaScript y se imprime bien. Con **dos** contendientes es un duelo enfrentado (lo que describe la lista de abajo); con **tres a seis** es una **liga**: cabecera con quién va primero, una **clasificación** (tareas resueltas, después tests superados y después coste, menos es mejor; los empates comparten posición), una comparativa con una barra fina por contendiente y métrica, una **matriz por tarea** (tests superados y si la tarea quedó resuelta) y el mismo desplegable de código y salida. Cada contendiente lleva una letra (`A` a `F`) junto a su color: la letra es la pista principal y el color, un refuerzo. En el duelo de dos, de arriba abajo:

1. **Cabecera:** los nombres de los contendientes, el número de tareas, de ejecuciones por tarea y el límite de tiempo.
2. **Marcador:** los tests superados por cada uno (`A` en lima, `B` en rosa) y quién gana y por cuánto (o «empate»).
3. **Métricas enfrentadas**, una fila por medida:
   - **Tareas resueltas:** tareas con **todos** los tests en verde **en todas las ejecuciones**.
   - **Intentos resueltos** (solo si usas `--runs` mayor que 1): ejecuciones con todos los tests en verde.
   - **Tests superados:** suma de tests en verde.
   - **Tiempo del modelo:** lo que tarda el modelo en responder (debajo, en pequeño, el tiempo de los tests). Menos es mejor.
   - **Tokens:** entrada y salida. Son las unidades en las que cobran los proveedores. Menos es mejor. (En Gemini, los tokens de razonamiento se cuentan como salida porque se facturan así.)
   - **Coste estimado:** calculado con la tabla de precios (ver `--prices`). Si el modelo no tiene precio o el proveedor no devolvió tokens, pone **«sin datos»**: nunca se inventa. Si los dos modelos tienen monedas distintas, avisa de que no son comparables.
   - El punto `●` y el texto «(mejor)» marcan quién gana en cada fila.
4. **Tests superados por tarea:** barras finas, una por contendiente y tarea.
5. **Tabla por tarea:** los mismos números desglosados.
6. **Código y salida de los tests:** un desplegable por tarea con el enunciado y, para cada intento, el estado, el código que escribió el modelo y la salida de pytest. **Léelo siempre**: dos modelos con la misma nota pueden haber escrito código muy distinto.

Cada intento tiene un estado, que se ve en el informe y en `results.json`:

| Estado en el informe | Qué significa |
|---|---|
| tests ejecutados | Los tests se ejecutaron; mira cuántos pasaron. |
| sin bloque de código | La respuesta no contiene ningún bloque de código utilizable. Cuenta como 0 tests superados. |
| no se pudo importar | El código no se pudo importar (error de sintaxis, falta la función o tiene otro nombre…). |
| tiempo agotado | Los tests superaron el límite de `--timeout` y se interrumpieron. |
| error al ejecutar | pytest no pudo ejecutar la tarea (por ejemplo, no encuentra tests). |
| error del proveedor | La llamada a la API falló (clave, red, cuota…). Ese intento cuenta como no resuelto y sin tests superados. |

Un «error del proveedor» no detiene el duelo: se anota y se sigue con el resto.

---

## Opciones: `--runs`, `--timeout`, `--resume` y `--prices`

La orden `run` necesita `--out` y al menos dos contendientes (`--a` y `--b`, o `--model` varias veces); acepta además estas opciones:

| Opción | Qué hace |
|---|---|
| `--model SPEC`, `-m SPEC` | Contendiente `proveedor:modelo`; repítelo para una liga de 2 a 6 (además de, o en lugar de, `--a` y `--b`). |
| `--runs N` | Ejecuciones por tarea (1 por defecto). |
| `--timeout S` | Límite en segundos para los tests de cada respuesta (20 por defecto). |
| `--resume` | Continúa el duelo de `--out` saltando los intentos ya terminados. |
| `--retries N` | Reintentos ante HTTP 429/5xx y cortes de conexión (3 por defecto; `0` los desactiva). |
| `--prices f.json` | Tabla de precios adicional. |
| `--replays DIR` | Carpeta de respuestas grabadas para `replay`. |

### `--runs`

Los modelos no responden siempre lo mismo. `--runs 3` pide **tres respuestas** por tarea a cada contendiente y las evalúa por separado:

- «Tests superados», tiempo, tokens y coste son **la suma** de todas las ejecuciones.
- Una tarea cuenta como «resuelta» solo si **todas** las ejecuciones superan todos los tests.
- Las llamadas son `tareas × runs × contendientes`, así que el coste crece en la misma proporción.

Debe ser 1 o más; con `--runs 0` la orden termina con un error.

### `--timeout`

Es el tiempo máximo, en segundos, que tienen **los tests** de una respuesta para ejecutarse (20 por defecto). Sirve para cortar bucles infinitos o soluciones muy lentas: al agotarse, el intento queda como «tiempo agotado». Admite decimales (`--timeout 2.5`) y debe ser mayor que 0. **No limita la espera al modelo:** eso lo controla la variable de entorno `MODELDUEL_HTTP_TIMEOUT` (180 s por defecto).

### `--resume`

Un duelo con APIs reales puede tardar y costar dinero, así que `results.json` se guarda **tras cada intento** (con un archivo temporal que después reemplaza al anterior, de modo que nunca queda a medias). Si el duelo se corta —Ctrl+C, un apagón, la red—, lo hecho sigue en `results.json` y en un `index.html` parcial que muestra «Duelo incompleto: X de Y intentos».

Para continuar, repite **la misma orden** añadiendo `--resume`:

```bash
modelduel run mis-tareas --a gemini:<modelo> --b openai:<modelo> --runs 3 --out runs/duelo --resume
```

- Se saltan los intentos ya terminados (se ven como `==  ...  · ya hecho`) y solo se llama a los modelos por lo que falta.
- Los intentos que acabaron en «error del proveedor» se **repiten**.
- Si has cambiado los contendientes, la orden se detiene con un error: mezclar modelos distintos daría un marcador sin sentido. Usa otra carpeta `--out`.
- Si has cambiado una tarea, el límite de tiempo o el número de ejecuciones, avisa y sigue: la tarea cambiada se repite entera, el resto se conserva.
- Si no hay `results.json` previo, empieza de cero.
- **Sin `--resume`**, modelduel se niega a sobrescribir un duelo incompleto (bórralo o cambia de `--out`); uno completo sí se rehace, como siempre.

### `--prices`

modelduel **no trae precios reales** porque cambian a menudo. Los pones tú en un archivo JSON, con tarifas **por millón de tokens**:

```json
{
  "_nota": "Precios por millón de tokens. Compruébalos en la web del proveedor.",
  "gemini:mi-modelo": { "input": 0.10, "output": 0.40, "currency": "EUR" },
  "openai:otro-modelo": { "input": 0.15, "output": 0.60, "currency": "USD" }
}
```

(Sustituye los nombres y las cifras por los reales de tus modelos: estos valores son un ejemplo de formato.)

- La **clave** es `proveedor:modelo`, tal como lo escribes en `--a`/`--b`. También vale solo el nombre del modelo.
- `input` y `output` son obligatorios, numéricos y no negativos.
- `currency` es opcional (`USD` por defecto); se muestra en mayúsculas.
- Las claves que empiezan por `_` (como `_nota`) se ignoran: sirven para comentarios.
- La fórmula es `coste = entrada / 1e6 × tarifa_entrada + salida / 1e6 × tarifa_salida`.

Se usa así:

```bash
modelduel run mis-tareas --a gemini:<modelo> --b openai:<modelo> --prices precios.json --out runs/duelo
```

Los precios de `replay:alfa` y `replay:beta` son ficticios y vienen integrados solo para la demo (el informe lo advierte). Si un archivo no es JSON válido o le falta `input`/`output`, la orden termina con un error explicativo antes de llamar a ningún modelo.

---

## Códigos de salida

Útiles si usas modelduel dentro de un script:

| Código | Significado |
|---|---|
| `0` | El duelo se completó, **aunque los modelos fallen tests**. |
| `1` | No se pudo escribir en la carpeta de salida. |
| `2` | Error de uso o de configuración: argumentos, tareas, proveedores, claves que faltan, precios o un `results.json` ilegible. |
| `130` | Interrumpido con Ctrl+C. |

La carpeta de salida se comprueba **antes** de llamar a las APIs, para no perder un duelo de pago por un error tonto.

---

## Seguridad: qué aísla y qué no

Los modelos escriben código y modelduel **lo ejecuta en tu ordenador**. Qué hace para reducir el riesgo:

- Guarda cada solución en un **directorio temporal** que se borra al terminar.
- Ejecuta los tests en un **subproceso con límite de tiempo** (`--timeout`).
- Le quita al subproceso las **variables de entorno con aspecto de secreto** (las que contienen `KEY`, `TOKEN`, `SECRET`, `PASSWORD` o `CREDENTIAL` en el nombre), de modo que no ve tus claves de API.
- Al terminar mata **todos los procesos** que haya lanzado la solución.
- Las claves no aparecen nunca en el informe, en los errores ni en la URL de las peticiones.

Qué **no** hace, y conviene tener presente:

- **No es un aislamiento real.** El código del modelo puede leer y escribir en el resto de tu disco y usar la red con tus permisos de usuario.
- Un proceso que se desligue a propósito del grupo (por ejemplo con `setsid`) puede sobrevivir.
- Una solución que escriba sin parar puede llenar el disco temporal hasta que se agote el límite de tiempo.

Recomendaciones: usa tus propias tareas o tareas de confianza, no ejecutes duelos con modelos que no conozcas sobre datos sensibles y, si puedes, lanza modelduel dentro de un **contenedor o una máquina virtual**.

---

## Preguntas frecuentes y solución de problemas

**«modelduel» no se reconoce como una orden.**
No tienes activado el entorno virtual (o estás en otra terminal). Actívalo (`.venv\Scripts\Activate.ps1` en Windows, `source .venv/bin/activate` en Linux y macOS) o ejecuta `python -m modelduel ...`.

**Sale «modelduel necesita pytest para ejecutar los tests de las tareas».**
Falta pytest en el entorno de Python que ejecuta modelduel. Instálalo en ese mismo entorno: `pip install pytest`.

**Sale «Falta la variable de entorno GEMINI_API_KEY» (o `OPENAI_API_KEY`).**
No has definido la clave en **esta** terminal. Las variables de entorno se pierden al cerrarla; vuelve a definirla como se explica en [Un duelo real](#un-duelo-real-con-modelos-de-verdad). Con `openai:` la clave solo es opcional si `OPENAI_BASE_URL` apunta a `localhost` (Ollama).

**Sale «Proveedor … desconocido» o «Especificación … no válida».**
Los contendientes se escriben `proveedor:modelo`, con uno de estos proveedores: `replay`, `gemini`, `openai`.

**Sale «No encuentro las respuestas grabadas de …» con `replay`.**
La carpeta `replays/<nombre>` no está donde modelduel la busca (junto a la carpeta de tareas, o en `examples/replays`). Indícala con `--replays DIR`. Y cada tarea necesita su archivo `<id_de_la_tarea>.md` dentro.

**Un intento sale con «tiempo agotado».**
Los tests de esa respuesta tardaron más que `--timeout` (20 s por defecto): puede ser un bucle infinito del modelo o una solución realmente lenta. Si sabes que tu tarea necesita más tiempo, súbelo (`--timeout 60`). Si es la llamada al modelo la que se corta, el mensaje será «La petición a … superó N s»: sube `MODELDUEL_HTTP_TIMEOUT`.

**Un intento sale con «sin bloque de código».**
El modelo no respondió con un bloque delimitado por tres acentos graves (```` ``` ````), por ejemplo porque respondió solo con explicaciones o se negó. Mira la respuesta completa en el informe (se muestra en ese caso). modelduel toma el primer bloque marcado como `python` o, si no hay ninguno marcado, el único bloque de la respuesta. Ocurre a veces con modelos pequeños; cuenta como fallo, y es justo.

**Sale «no se pudo importar».**
El código del modelo tiene un error de sintaxis o no define la función con el nombre pedido. Revisa el código y la salida de pytest en el informe, y comprueba que tu enunciado da el nombre y la firma exactos.

**Sale «error al ejecutar» y «pytest no encontró ningún test».**
Es un problema de tu tarea, no del modelo: `test_task.py` no contiene funciones que empiecen por `test`. Compruébalo con `modelduel list-tasks`, que muestra el número de tests de cada tarea.

**Errores HTTP 429 («límite de peticiones o cuota agotada»).**
El proveedor te está limitando: has superado el número de peticiones por minuto o se ha agotado tu cuota o saldo. Espera un poco y repite, revisa tu plan, o usa un modelo distinto. modelduel **reintenta solo** los 429, 500, 502, 503 y 504 y los cortes de conexión (hasta 3 veces, con `--retries N`; `0` lo desactiva): espera 1, 2, 4… segundos con algo de azar, respeta la cabecera `Retry-After` y avisa en consola de cada reintento. Si tras los reintentos sigue fallando, o si el servidor pide esperar más de 2 minutos, ese intento queda como «error del proveedor» y el duelo sigue. Los tiempos de espera agotados (`MODELDUEL_HTTP_TIMEOUT`) no se reintentan.

**Otros errores HTTP.** El mensaje incluye una pista: 400 (revisa el nombre del modelo), 401 y 403 (revisa la clave y los permisos), 404 (¿existe el modelo y es correcta `OPENAI_BASE_URL`?), y los 5xx son errores del servidor del proveedor.

**El coste sale como «sin datos».**
El modelo no tiene precio en la tabla (añádelo con `--prices`) o el proveedor no devolvió el número de tokens.

**¿Puedo comparar más de dos modelos?**
No: cada duelo enfrenta a dos. Para comparar más, haz varios duelos.

**¿Puedo usar tareas en otro lenguaje que no sea Python?**
No: solo funciones de Python comprobadas con pytest.

**¿Dónde se guardan mis resultados?**
En la carpeta que pases a `--out`: `results.json` (datos) e `index.html` (informe). Si repites un duelo completo en la misma carpeta, se sobrescriben; usa una carpeta distinta por duelo. Si se cortó a medias, continúalo con `--resume`.

**¿Se envía mi código o mis tests a algún sitio?**
Solo el **enunciado** (`task.md`, más las instrucciones de formato) se envía a la API del proveedor que elijas. Los tests no se envían a los modelos.

**Los números salen con coma decimal y punto de miles.**
Es intencionado: el informe y la consola usan el formato español (`1.401` tokens, `10,1 s`).
