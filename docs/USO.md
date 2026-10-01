# Guía de uso de modelduel

Esta guía es para quien quiere **usar** modelduel, no para quien quiere modificar su código (para eso, mira [`CONTRIBUTING.md`](../CONTRIBUTING.md)). No hace falta saber programar en profundidad: si sabes abrir una terminal y copiar órdenes, puedes seguirla.

## Índice

1. [Qué es y cuándo usarlo](#qué-es-y-cuándo-usarlo)
2. [Instalación](#instalación)
3. [Tu primer duelo con la demo](#tu-primer-duelo-con-la-demo)
4. [Un duelo real con modelos de verdad](#un-duelo-real-con-modelos-de-verdad)
   - [OmniRoute](#omniroute)
   - [Gemini](#gemini)
   - [OpenAI](#openai)
   - [OpenRouter](#openrouter)
   - [Ollama (modelos en tu ordenador)](#ollama-modelos-en-tu-ordenador)
5. [Crear tu propia tarea paso a paso](#crear-tu-propia-tarea-paso-a-paso)
6. [Una liga de tres a seis modelos](#una-liga-de-tres-a-seis-modelos)
7. [Leer el informe](#leer-el-informe)
8. [Clasificación pública](#clasificación-pública)
9. [Opciones: `--runs`, `--timeout`, `--retries`, `--resume` y `--prices`](#opciones---runs---timeout---retries---resume-y---prices)
10. [Códigos de salida](#códigos-de-salida)
11. [Seguridad: qué aísla y qué no](#seguridad-qué-aísla-y-qué-no)
12. [Límites conocidos](#límites-conocidos)
13. [Preguntas frecuentes y solución de problemas](#preguntas-frecuentes-y-solución-de-problemas)

---

## Qué es y cuándo usarlo

modelduel es una herramienta de terminal que **enfrenta a dos modelos de inteligencia artificial (o a una liga de hasta seis) con el mismo problema de programación**:

1. Envía el mismo enunciado a cada modelo y les pide una función en Python.
2. Guarda la respuesta de cada uno y le pasa **tus tests** (los mismos para todos).
3. Te da un informe con quién acierta más, cuánto tarda, cuántos tokens gasta y cuánto cuesta.

Úsalo cuando tengas que **elegir un modelo para tu trabajo** y no te fíes de los rankings generales, porque miden tareas que no son las tuyas. También sirve para comprobar si un modelo barato o pequeño (por ejemplo, uno que corre en tu ordenador con Ollama) te basta para lo que haces.

Ten en cuenta dos límites:

- Solo evalúa **funciones de Python** que se pueden comprobar con tests automáticos.
- **Una sola ejecución es una señal débil**: los modelos no son deterministas. Repite el duelo (`--runs`) y usa tareas de tu propio trabajo.

> **Aviso importante:** el código que escriben los modelos **se ejecuta en tu ordenador**. Lee la sección de [seguridad](#seguridad-qué-aísla-y-qué-no) antes de usar tareas o modelos que no controles.

---

## Instalación

Necesitas **Python 3.12 o superior** y **pytest** en el mismo entorno (modelduel lo usa para ejecutar los tests de las tareas; no es una dependencia del programa y por eso se instala aparte, o con el extra `[pytest]`). modelduel no necesita ninguna otra biblioteca.

### Desde PyPI (recomendado)

```bash
pip install "modelduel[pytest]"
modelduel --version
```

`[pytest]` instala también pytest; es lo mismo que `pip install modelduel pytest`. Escribe `modelduel 0.2.0` (o la versión actual) si todo va bien. Así tienes la orden `modelduel` **con las tareas y respuestas de ejemplo incluidas** (ver `modelduel demo` en la sección siguiente).

> **Ojo:** el paquete se publica en PyPI cuando se crea la *release* `v0.2.0` del repositorio. Hasta entonces `pip install modelduel` no lo encontrará y tienes que instalarlo desde GitHub (siguiente apartado).

### Desde GitHub (la última versión, publicada o no)

```bash
pip install git+https://github.com/BertMarti/modelduel pytest
```

### Desde el código fuente (para tener `examples/` a mano)

Necesitas además **Git**. Windows (PowerShell):

```powershell
git clone https://github.com/BertMarti/modelduel
cd modelduel
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e . pytest
modelduel --version
```

Si PowerShell se queja de que la ejecución de scripts está deshabilitada al activar el entorno, no hace falta activarlo: usa `.venv\Scripts\python.exe -m modelduel` donde esta guía dice `modelduel`.

Linux y macOS:

```bash
git clone https://github.com/BertMarti/modelduel
cd modelduel
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e . pytest
modelduel --version
```

**Cada vez que abras una terminal nueva** tienes que volver a activar el entorno (`.venv\Scripts\Activate.ps1` en Windows, `source .venv/bin/activate` en Linux y macOS) o no encontrará la orden `modelduel`. Lo mismo vale si instalas desde PyPI dentro de un entorno virtual.

---

## Tu primer duelo con la demo

Si solo quieres **ver** cómo es un duelo, abre el [duelo en directo](https://bertmarti.github.io/modelduel/#demo) de la web: reproduce, en unos 25 segundos, un duelo **pregrabado** (no llama a ningún modelo ni ejecuta código). Puedes pausarlo o detenerlo, y si tu sistema pide «reducir movimiento» avanza paso a paso con el botón «Siguiente». Usa los datos de `demo/results.json`, el mismo `results.json` que genera `modelduel run`.

La demo no necesita claves ni cuesta nada: usa respuestas **grabadas y ficticias** de tres «modelos» llamados `alfa`, `beta` y `gamma` (proveedor `replay`): es una liga de tres contendientes.

### `modelduel demo`

Con el paquete instalado (desde PyPI o desde GitHub), sin clonar nada:

```bash
modelduel demo                        # informe en modelduel-demo/
modelduel demo --out otra-carpeta     # elegir la carpeta de salida
modelduel demo --copy MIS-EJEMPLOS    # no ejecuta nada: copia las tareas y respuestas de ejemplo
```

`demo --copy` crea `MIS-EJEMPLOS/tasks` (las tres tareas) y `MIS-EJEMPLOS/replays` (las respuestas grabadas) y te dice cómo probarlas. Es el punto de partida más rápido para [crear tus propias tareas](#crear-tu-propia-tarea-paso-a-paso): copia una carpeta de tarea y cámbiala.

### La misma demo con `run`

`modelduel demo` hace lo mismo que esta orden, que puedes lanzar desde un clon del repositorio (con el entorno activado):

```bash
modelduel run examples/tasks --model replay:alfa --model replay:beta --model replay:gamma --out runs/demo
```

(En Windows, la misma orden; las barras de las rutas también funcionan.) Verás algo así:

```text
modelduel 0.2.0 · 3 tareas · 1 ejecución por tarea
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

`gamma` empata con `beta` en tareas y en tests, pero es mucho más barato, así que queda por delante: ese es el desempate por coste. Con `--a` y `--b` (o con solo dos `--model`) sigues teniendo el duelo de dos de siempre (`modelduel run examples/tasks --a replay:alfa --b replay:beta --out runs/demo`). Cómo se lee la clasificación se explica en [Una liga de tres a seis modelos](#una-liga-de-tres-a-seis-modelos).

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

Un contendiente se escribe como `proveedor:modelo`. Hay cuatro proveedores:

| Proveedor | Para qué sirve | Variables de entorno |
|---|---|---|
| `replay:<nombre>` | Respuestas grabadas, sin red ni coste (la demo). | Ninguna |
| `gemini:<modelo>` | La API de Google Gemini. | `GEMINI_API_KEY` (obligatoria), `GEMINI_BASE_URL` (opcional) |
| `openai:<modelo>` | Cualquier API compatible con «Chat Completions» de OpenAI: OpenAI, OpenRouter, Ollama… | `OPENAI_API_KEY`, `OPENAI_BASE_URL` (por defecto `https://api.openai.com/v1`) |
| `omniroute:<modelo>` | [OmniRoute](#omniroute), un router local con API compatible con OpenAI. | `OMNIROUTE_BASE_URL` (por defecto `http://localhost:20128/v1`), `OMNIROUTE_API_KEY` (opcional) |

Antes de empezar, ten en cuenta:

- Las **claves** se leen **solo de variables de entorno**, nunca de archivos. Nunca las escribas dentro del proyecto ni las subas a GitHub.
- **Cada llamada a una API real puede costar dinero.** El número de llamadas es `tareas × ejecuciones × contendientes`. Con las tres tareas de ejemplo, dos contendientes y `--runs 3` son 18 llamadas (en una liga de seis, 54).
- El nombre del `<modelo>` es el que use el proveedor (consulta su documentación). En esta guía se escribe `<modelo>` para que pongas el tuyo.
- Las variables de entorno solo valen para la terminal donde las defines y desaparecen al cerrarla. Cambia `PEGA_AQUI_TU_CLAVE` por tu clave real.
- Los dos contendientes `openai:` de una misma orden comparten `OPENAI_BASE_URL` y `OPENAI_API_KEY`. Si quieres comparar dos modelos de OpenRouter, usa `openai:` para los dos; si quieres comparar Gemini con uno de OpenRouter, usa `gemini:` y `openai:`.

### OmniRoute

OmniRoute es un router local que expone muchos modelos con una API compatible con OpenAI. `omniroute:` es el proveedor `openai:` con otras variables y otra dirección por defecto, así que puedes mezclarlo con `openai:` y `gemini:` en la misma orden sin que se pisen las claves.

```bash
omniroute serve                       # en otra terminal; escucha en http://localhost:20128/v1
modelduel run examples/tasks --a omniroute:<modelo-1> --b omniroute:<modelo-2> --out runs/omniroute
```

- Otra dirección: `OMNIROUTE_BASE_URL`. Si tu OmniRoute pide clave: `OMNIROUTE_API_KEY` (opcional; no se exige).
- Si el servidor no responde, modelduel dice «Arranca OmniRoute con `omniroute serve`» y no reintenta.
- El nombre del `<modelo>` es el que exponga tu OmniRoute.

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

## Una liga de tres a seis modelos

Para comparar más de dos modelos, repite `--model` (o `-m`) una vez por contendiente. Hacen falta entre **2 y 6 en total**:

```bash
modelduel run mis-tareas \
  --model gemini:<modelo> --model openai:<modelo-1> --model openai:<modelo-2> \
  --runs 3 --out runs/liga
```

- También puedes mezclar: `--a` y `--b` van los primeros y cada `--model` se añade después (`--a X --b Y --model Z` es una liga de tres: A=X, B=Y, C=Z).
- Cada contendiente recibe una **letra** (`A` a `F`) por orden de aparición y un color. La letra es siempre la pista principal; el color, un refuerzo.
- No puedes repetir el mismo `proveedor:modelo`: se rechaza antes de llamar a nadie. Para ver cuánto varía un modelo consigo mismo usa `--runs`.
- Con más de seis contendientes la orden termina con un error.
- Las llamadas a las APIs son `tareas × runs × contendientes`: con seis contendientes la factura se multiplica. Prueba antes con `replay` o con una sola tarea.

### Cómo leer la clasificación

En la consola, y arriba del informe de liga, hay una fila por contendiente, de mejor a peor. El orden sale de tres criterios, **en este orden**:

1. **Tareas resueltas** (más es mejor): tareas con todos los tests en verde en todas las ejecuciones.
2. **Tests superados** (más es mejor): suma de tests en verde.
3. **Coste** (menos es mejor): solo desempata si **todos** los contendientes tienen precio y en la misma moneda; si no, no cuenta.

Los empates completos **comparten posición**. En la demo:

```text
  #   Contendiente     Tareas   Tests   Tiempo   Tokens (ent/sal)        Coste
  ----------------------------------------------------------------------------
  1   A replay:alfa       2/3   31/32   10,1 s          1.401/703   0,0017 USD
  2   C replay:gamma      2/3   30/32    3,7 s          1.314/426   0,0003 USD
  3   B replay:beta       2/3   30/32   28,1 s        1.373/2.132   0,0248 USD
```

`alfa` va primero porque, con las mismas tareas resueltas que los demás (2 de 3), supera más tests (31 frente a 30). `gamma` y `beta` empatan en tareas y en tests, y `gamma` queda delante por ser más barato. Con tres tareas, una sola respuesta cambia el orden: léelo con cautela.

Con tres o más contendientes, el informe HTML añade, debajo de la clasificación, una **comparativa** con una barra fina por contendiente y métrica, una **matriz por tarea** (tests superados y un estado escrito —«resuelta», «no resuelta», «sin hacer»…, para no depender del color) y el desplegable de código y salida de cada intento. En móvil, las tablas se desplazan en horizontal dentro de su propio marco (también con el teclado).

---

## Leer el informe

`index.html` es un único archivo: no necesita conexión, no usa JavaScript y se imprime bien. Con **dos** contendientes es un duelo enfrentado (lo que describe la lista de abajo); con **tres a seis** es una **liga**: cabecera con quién va primero, una **clasificación** (tareas resueltas, después tests superados y después coste, menos es mejor; los empates comparten posición), una comparativa con una barra fina por contendiente y métrica, una **matriz por tarea** (tests superados y si la tarea quedó resuelta) y el mismo desplegable de código y salida. Cada contendiente lleva una letra (`A` a `F`) junto a su color: la letra es la pista principal y el color, un refuerzo. En el duelo de dos, de arriba abajo:

1. **Cabecera:** los nombres de los contendientes, el número de tareas, de ejecuciones por tarea y el límite de tiempo.
2. **Marcador:** los tests superados por cada uno (`A` en lima, `B` en rosa) y, debajo, el veredicto: quién gana **y qué criterio decide**. Es el mismo orden que la clasificación: primero las tareas resueltas, si empatan los tests superados y, si también empatan, el coste (solo si los dos tienen precio en la misma moneda). Por ejemplo, «gana A por tareas resueltas (2 frente a 1)» o «gana B por coste (…, con las mismas tareas resueltas y tests)»; si no hay diferencia, «empate en tareas resueltas, tests y coste». Como el criterio que manda puede no ser el de los números grandes (un modelo con menos tests pero más tareas resueltas gana), el veredicto lo dice siempre.
3. **Métricas enfrentadas**, una fila por medida:
   - **Tareas resueltas:** tareas con **todos** los tests en verde **en todas las ejecuciones**.
   - **Intentos resueltos** (solo si usas `--runs` mayor que 1): ejecuciones con todos los tests en verde.
   - **Tests superados:** suma de tests en verde.
   - **Tiempo del modelo:** lo que tarda el modelo en responder (debajo, en pequeño, el tiempo de los tests). Menos es mejor.
   - **Tokens:** entrada y salida. Son las unidades en las que cobran los proveedores. Menos es mejor. (En Gemini, los tokens de razonamiento se cuentan como salida porque se facturan así.)
   - **Coste estimado:** calculado con la tabla de precios (ver `--prices`). Si el modelo no tiene precio o el proveedor no devolvió tokens, pone **«sin datos»**: nunca se inventa. Si los dos modelos tienen monedas distintas, avisa de que no son comparables.
   - «▲ mejor» y «▼ peor» (glifo y texto, nunca solo color) marcan quién gana y quién pierde en cada fila; si hay empate no se marca ninguno.
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

## Clasificación pública

El repositorio publica en <https://bertmarti.github.io/modelduel/leaderboard/> una clasificación de modelos construida con los `results.json` de la carpeta [`results/`](https://github.com/BertMarti/modelduel/tree/main/results). El CI la regenera en cada cambio. Hoy contiene tres resultados de demostración con respuestas grabadas (`replay`) y precios ficticios.

### Generarla en tu ordenador

```bash
modelduel leaderboard results --out runs/clasificacion
```

Crea `runs/clasificacion/index.html` (la clasificación y el histórico) y un informe por duelo en `runs/clasificacion/duelos/<id>/index.html`. Sirve para cualquier carpeta con `results.json` de modelduel, también la tuya.

- **Cómo se ordena.** Cada modelo (`proveedor:modelo`) suma tareas, tests y coste de todos los duelos donde aparece. Se compara la **proporción** de tareas resueltas, después la de tests y después el coste por intento (solo si todos tienen precio en la misma moneda). Con totales, un modelo ganaría solo por jugar más duelos. Los empates comparten posición.
- **Mira el nº de duelos.** Un modelo con un solo duelo es una señal débil, igual que una sola ejecución.
- Un `results.json` incompleto (`in_progress`) o ilegible es un error: termínalo con `--resume` antes de publicarlo.

### Añadir resultados reales

1. Lanza el duelo o la liga con tus tareas y guarda la salida: `modelduel run mis-tareas --a gemini:<modelo> --b omniroute:<modelo> --runs 3 --out runs/duelo-1`.
2. Copia `runs/duelo-1/results.json` a `results/` con un nombre que sea la fecha y qué se enfrentó (el nombre, sin `.json`, es el id del duelo): `results/2026-10-02-gemini-vs-omniroute.json`.
3. Genera la página para comprobarla (`modelduel leaderboard results --out runs/clasificacion`) y abre un pull request. El CI la publica al fusionarlo.

`results/` es público: no incluyas claves ni tareas privadas (el `results.json` guarda el enunciado, las respuestas y el código de cada modelo).

---

## Opciones: `--runs`, `--timeout`, `--retries`, `--resume` y `--prices`

La orden `run` necesita `--out` y entre dos y seis contendientes (`--a` y `--b`, o `--model` varias veces); acepta además estas opciones:

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

### `--retries`

Las APIs reales fallan a veces por motivos pasajeros. Con `--retries N` (3 por defecto; `--retries 0` lo desactiva), modelduel **reintenta solo** la llamada cuando el proveedor responde:

- **HTTP 429** (límite de peticiones o cuota) o **500, 502, 503 y 504** (fallos del servidor).
- **Cortes de una conexión ya abierta** (el servidor cierra a mitad de respuesta).

La espera crece como 1, 2, 4… segundos (tope de 30 s) con algo de azar para que varios clientes no coincidan. Si el servidor manda la cabecera `Retry-After`, se respeta, salvo que pida esperar **más de 2 minutos**: entonces modelduel se rinde sin esperar. Cada reintento se avisa en consola:

```text
  ~~  openai:mi-modelo: reintento 1/3 en 1,2 s: HTTP 429 ...
```

**No** se reintenta lo que no suele arreglarse esperando: los errores de tu configuración (400, 401, 403, 404…), los **tiempos de espera agotados** (`MODELDUEL_HTTP_TIMEOUT`: reintentar triplicaría la espera), un **servidor apagado** (por ejemplo, Ollama sin arrancar) ni los errores de resolución de nombres (DNS). Si tras los reintentos la llamada sigue fallando, ese intento queda como «error del proveedor» y el duelo sigue con el resto; `--resume` puede repetirlo después. El tiempo del modelo que se anota es el del intento bueno, sin las esperas.

### `--resume`

Un duelo con APIs reales puede tardar y costar dinero, así que `results.json` se guarda **tras cada intento** (con un archivo temporal que después reemplaza al anterior, de modo que nunca queda a medias). Si el duelo se corta —Ctrl+C, un apagón, la red—, lo hecho sigue en `results.json` (con `"status": "in_progress"`) y en un `index.html` parcial que muestra «Duelo incompleto: X de Y intentos». Un duelo terminado queda con `"status": "complete"`.

Para continuar, repite **la misma orden** añadiendo `--resume`:

```bash
modelduel run mis-tareas --a gemini:<modelo> --b openai:<modelo> --runs 3 --out runs/duelo --resume
```

Empieza con una línea como `Reanudando: 5 intentos ya hechos de 9; quedan 4.`; los intentos reutilizados se ven como `==  ...  · ya hecho` y solo se llama a los modelos por lo que falta. Los intentos que acabaron en «error del proveedor» se **repiten** (lo normal es reanudar precisamente por eso). El coste de los intentos reutilizados se recalcula con la tabla de precios actual.

**Cuándo avisa y cuándo da error:**

| Qué ha cambiado desde el duelo anterior | Qué pasa |
|---|---|
| Los **contendientes** (otro modelo, uno de más o de menos) | **Error** (código 2): mezclar modelos distintos daría un marcador sin sentido. Usa la misma configuración u otra carpeta `--out`. |
| El `results.json` es de un formato **más nuevo** que el que entiende esta versión, o está dañado | **Error** (código 2). |
| Una **tarea** (enunciado o tests) | **Aviso**: esa tarea se repite entera; el resto se conserva. |
| Una tarea que **ya no está** en la carpeta | **Aviso**: se descarta. |
| El límite `--timeout` o el número de `--runs` | **Aviso**: se conservan los intentos hechos. |
| La **versión de modelduel** | **Aviso**: el enunciado que se envía a los modelos pudo cambiar. |
| No hay `results.json` previo | Sin aviso: empieza de cero. |

**Sin `--resume`**, modelduel se niega a sobrescribir un duelo incompleto (`... es un duelo incompleto. Continúalo con --resume o bórralo, o elige otra carpeta --out.`, código 2). Uno completo sí se rehace, como siempre.

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

## Límites conocidos

- Sin `--resume`, un `results.json` ilegible o de un formato más nuevo se sobrescribe sin aviso; solo se protege un duelo incompleto legible.
- Un `Retry-After` de entre 30 y 120 s se respeta entero en cada reintento: con `--retries 3`, un proveedor saturado puede costar varios minutos por intento. Baja `--retries` si prefieres rendirte antes.
- Los proveedores `gemini`, `openai` y `omniroute` solo se han probado con respuestas simuladas, no contra las APIs reales.

---

## Preguntas frecuentes y solución de problemas

**«modelduel» no se reconoce como una orden.**
No tienes activado el entorno virtual (o estás en otra terminal). Actívalo (`.venv\Scripts\Activate.ps1` en Windows, `source .venv/bin/activate` en Linux y macOS) o ejecuta `python -m modelduel ...`.

**Sale «modelduel necesita pytest para ejecutar los tests de las tareas».**
Falta pytest en el entorno de Python que ejecuta modelduel. Instálalo en ese mismo entorno: `pip install pytest`.

**Sale «Falta la variable de entorno GEMINI_API_KEY» (o `OPENAI_API_KEY`).**
No has definido la clave en **esta** terminal. Las variables de entorno se pierden al cerrarla; vuelve a definirla como se explica en [Un duelo real](#un-duelo-real-con-modelos-de-verdad). Con `openai:` la clave solo es opcional si `OPENAI_BASE_URL` apunta a `localhost` (Ollama).

**Sale «No hay resultados en …» con `leaderboard`.**
La carpeta no existe o no tiene ningún `.json`. Copia ahí los `results.json` de tus duelos.

**Sale «Proveedor … desconocido» o «Especificación … no válida».**
Los contendientes se escriben `proveedor:modelo`, con uno de estos proveedores: `replay`, `gemini`, `openai`, `omniroute`.

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
El proveedor te está limitando: has superado el número de peticiones por minuto o se ha agotado tu cuota o saldo. Espera un poco y repite, revisa tu plan, o usa un modelo distinto. modelduel ya **reintenta solo** estos casos (ver [`--retries`](#--retries)). Si tras los reintentos sigue fallando, o si el servidor pide esperar más de 2 minutos, ese intento queda como «error del proveedor» y el duelo sigue; puedes repetirlo después con `--resume`.

**Otros errores HTTP.** El mensaje incluye una pista: 400 (revisa el nombre del modelo), 401 y 403 (revisa la clave y los permisos), 404 (¿existe el modelo y es correcta `OPENAI_BASE_URL`?), y los 5xx son errores del servidor del proveedor.

**El coste sale como «sin datos».**
El modelo no tiene precio en la tabla (añádelo con `--prices`) o el proveedor no devolvió el número de tokens.

**¿Puedo comparar más de dos modelos?**
Sí, hasta seis: repite `--model`. Ver [Una liga de tres a seis modelos](#una-liga-de-tres-a-seis-modelos).

**¿Puedo usar tareas en otro lenguaje que no sea Python?**
No: solo funciones de Python comprobadas con pytest.

**¿Dónde se guardan mis resultados?**
En la carpeta que pases a `--out`: `results.json` (datos) e `index.html` (informe). Si repites un duelo completo en la misma carpeta, se sobrescriben; usa una carpeta distinta por duelo. Si se cortó a medias, continúalo con `--resume`.

**¿Se envía mi código o mis tests a algún sitio?**
Solo el **enunciado** (`task.md`, más las instrucciones de formato) se envía a la API del proveedor que elijas. Los tests no se envían a los modelos.

**Los números salen con coma decimal y punto de miles.**
Es intencionado: el informe y la consola usan el formato español (`1.401` tokens, `10,1 s`).
