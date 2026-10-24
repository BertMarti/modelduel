# modelduel

![modelduel: modelo contra modelo](https://raw.githubusercontent.com/BertMarti/modelduel/main/docs/img/banner.svg)

**Dos modelos, una tarea, los mismos tests.** Compara modelos de IA con problemas de programación de tu propio trabajo, no con rankings hechos para otra persona.

[![PyPI](https://img.shields.io/pypi/v/modelduel.svg)](https://pypi.org/project/modelduel/)
[![CI](https://github.com/BertMarti/modelduel/actions/workflows/ci.yml/badge.svg)](https://github.com/BertMarti/modelduel/actions/workflows/ci.yml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-b5e853.svg)](https://github.com/BertMarti/modelduel/blob/main/LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-ff7eb6.svg)](https://www.python.org/downloads/)
[![web](https://img.shields.io/badge/web-modelduel-4fd1e5.svg)](https://bertmarti.github.io/modelduel/)

## Pruébalo en un minuto (sin claves)

Una sola orden instala modelduel en un entorno propio y lanza un duelo de ejemplo con respuestas grabadas: no hace falta ninguna clave ni se gasta nada.

Linux o macOS:

```bash
python3 -m venv modelduel-env && modelduel-env/bin/pip install "modelduel[pytest]" && modelduel-env/bin/modelduel demo
```

Windows (PowerShell):

```powershell
py -m venv modelduel-env; modelduel-env\Scripts\pip install "modelduel[pytest]"; modelduel-env\Scripts\modelduel demo
```

Después abre `modelduel-demo/index.html` en el navegador. El entorno virtual (`modelduel-env`) evita mezclar modelduel con el Python del sistema; en muchas distribuciones de Linux, `pip install` fuera de uno da error.

## ▶ Ver un duelo en directo

**[▶ Ver un duelo en directo](https://bertmarti.github.io/modelduel/#demo)**: una reproducción pregrabada, sin claves y sin ejecutar código. También puedes visitar la [web de modelduel](https://bertmarti.github.io/modelduel/), abrir el [informe de demostración](https://bertmarti.github.io/modelduel/demo/) o consultar la [clasificación pública](https://bertmarti.github.io/modelduel/leaderboard/).

![Portada de modelduel](https://raw.githubusercontent.com/BertMarti/modelduel/main/docs/img/captura-portada.png)

![Informe de una liga de tres modelos](https://raw.githubusercontent.com/BertMarti/modelduel/main/docs/img/captura-informe.png)

## Qué es

modelduel envía el mismo enunciado a dos modelos de IA, o a una liga de hasta seis, recoge su código Python y ejecuta tus tests sobre cada respuesta. Después genera un informe con tareas resueltas, tests superados, tiempo, tokens y coste estimado.

## Para qué sirve

Los rankings públicos miden tareas que no son las tuyas. modelduel convierte tu caso real en una comparativa reproducible: mismo enunciado, mismos tests y criterios visibles. También sirve para saber si un modelo pequeño, barato o local te basta.

Solo evalúa funciones de Python comprobables con tests automáticos. Una sola ejecución es una señal débil: los modelos no son deterministas, así que conviene repetir el duelo con `--runs` y usar varias tareas propias.

## Cómo se usa

1. **Instala** modelduel en un entorno virtual y actívalo (si hiciste la prueba de arriba, ya lo tienes):

   ```bash
   python3 -m venv modelduel-env
   source modelduel-env/bin/activate        # Windows: modelduel-env\Scripts\Activate.ps1
   pip install "modelduel[pytest]"
   ```

2. **Prueba la demo** sin claves ni coste: `modelduel demo`. Enfrenta respuestas grabadas de `alfa`, `beta` y `gamma` y deja el informe en `modelduel-demo/`.

3. **Prepara tu duelo** con los proveedores que vayas a usar:

   ```bash
   modelduel init mi-duelo --proveedor gemini --proveedor openai
   ```

   Crea la carpeta `mi-duelo` con tres tareas de ejemplo, respuestas grabadas y un archivo `modelduel.toml` explicado. En la terminal te dice qué variables de entorno necesitas y dónde conseguir cada clave. Sin `--proveedor`, el duelo usa respuestas grabadas y funciona ya, sin claves.

4. **Define las claves y elige los modelos.** Las claves van en variables de entorno, nunca en un archivo:

   ```bash
   export GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"      # PowerShell: $env:GEMINI_API_KEY = "PEGA_AQUI_TU_CLAVE"
   export OPENAI_API_KEY="PEGA_AQUI_TU_CLAVE"
   ```

   Abre `mi-duelo/modelduel.toml` y cambia cada `CAMBIA-ESTO` por el nombre exacto del modelo (el archivo dice dónde ver la lista).

5. **Comprueba que no falta nada:**

   ```bash
   cd mi-duelo
   modelduel doctor          # añade --red para comprobar también la conexión (no gasta tokens)
   ```

   Repasa Python, pytest, las claves (sin mostrarlas nunca) y la configuración, y te dice qué hacer con cada fallo.

6. **Lanza el duelo** con `modelduel run` y abre `resultados/index.html` en el navegador. Es un informe autocontenido, sin JavaScript y con versión para imprimir. Para compartirlo en GitHub, pon `formato = "html,md"` en `modelduel.toml` y tendrás también `informe.md`.

7. **Usa tus propias tareas:** cambia el enunciado (`task.md`) y los tests (`test_task.py`) de las carpetas de `mi-duelo/tasks` y vuelve a lanzar `modelduel run`. Para que el resultado sea fiable, sube `ejecuciones` a 3 o más.

¿Prefieres no usar archivo de configuración? Todo se puede pasar en la orden: `modelduel run CARPETA_DE_TAREAS --a gemini:<modelo> --b openai:<modelo> --runs 3 --out resultados`.

### Proveedores

| Especificación | Para qué sirve | Variables de entorno |
|---|---|---|
| `replay:<nombre>` | Respuestas grabadas para probar sin red ni coste. | Ninguna |
| `gemini:<modelo>` | API de Google Gemini. | `GEMINI_API_KEY`, `GEMINI_BASE_URL` opcional |
| `openai:<modelo>` | OpenAI y APIs compatibles, como OpenRouter u Ollama. | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |
| `omniroute:<modelo>` | Router local OmniRoute compatible con OpenAI. | `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY` opcional |

Para OpenRouter, configura `OPENAI_BASE_URL=https://openrouter.ai/api/v1`. Para Ollama, configura `OPENAI_BASE_URL=http://localhost:11434/v1`; en local no hace falta clave.

Al terminar, la terminal muestra la clasificación (aquí, la de la demo):

```text
  #   Contendiente     Tareas   Tests   Tiempo   Tokens (ent/sal)        Coste
  ----------------------------------------------------------------------------
  1   A replay:alfa       2/3   31/32   10,1 s          1.401/703   0,0017 USD
  2   C replay:gamma      2/3   30/32    3,7 s          1.314/426   0,0003 USD
  3   B replay:beta       2/3   30/32   28,1 s        1.373/2.132   0,0248 USD
```

Primero cuentan las tareas resueltas, después los tests superados y, si todos los precios son comparables, el coste. Los precios de la demo son ficticios.

## Seguridad

> [!WARNING]
> **El código generado por los modelos se ejecuta en tu máquina.** modelduel crea un directorio temporal propio y lo borra al terminar, ejecuta los tests en un subproceso con límite de tiempo, elimina las variables de entorno que parecen secretos (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `PASS`, `AUTH`, `CREDENTIAL`, `PRIVATE`, `COOKIE`, `SESSION`, `PROXY`, `WEBHOOK` y similares), retira `SSH_AUTH_SOCK` y apunta `HOME`/`USERPROFILE` al temporal. En Linux y macOS aplica además límites del sistema: límite de CPU, archivos de 256 MiB como máximo, 256 descriptores y sin volcados de memoria; en Linux, también 4 GiB de memoria (espacio de direcciones). Al terminar mata el árbol de procesos: en Linux, con un supervisor que recoge también los procesos que intentan desligarse (`setsid`); en macOS, el grupo de procesos; en Windows, un Job Object. `modelduel doctor` te dice qué medidas aplica tu sistema.
>
> Esto **no es un aislamiento real**: el código conserva acceso a la red y al disco mediante rutas absolutas, y el espacio total que puede llenar en disco solo lo acota el tiempo. En Windows no hay límite de memoria. Úsalo con tareas de confianza y, para código en el que no confíes, dentro de un contenedor o una máquina virtual.

**Con un contenedor** (Docker o Podman), desde la carpeta de tu duelo:

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -e HOME=/tmp \
  --cap-drop ALL --security-opt no-new-privileges \
  --memory 4g --cpus 2 --pids-limit 512 \
  -e GEMINI_API_KEY -e OPENAI_API_KEY \
  -v "$PWD":/trabajo -w /trabajo \
  python:3.12-slim \
  sh -c 'pip install --quiet --user "modelduel[pytest]" && ~/.local/bin/modelduel run'
```

- El código de los modelos solo ve la carpeta actual (montada en `/trabajo`), no el resto de tu disco.
- `-e GEMINI_API_KEY` sin valor pasa la clave que ya tienes en la terminal, sin escribirla en la orden.
- `--memory`, `--cpus` y `--pids-limit` ponen techo a la memoria, la CPU y el número de procesos; `--cap-drop ALL` y `no-new-privileges` quitan privilegios.
- La red sigue abierta porque modelduel tiene que hablar con las APIs de los modelos.

## Preguntas frecuentes

**¿Cuesta dinero?** La demo no. Los duelos reales usan la cuenta y la clave del proveedor que elijas; el informe estima el coste si aportas sus tarifas con `--prices`.

**¿Cómo sé si me falta algo?** Ejecuta `modelduel doctor`: revisa la instalación, las claves (sin mostrarlas) y tu `modelduel.toml`, y te dice qué hacer con cada fallo. Con `--red` comprueba también que cada proveedor responde, sin gastar tokens.

**¿Dónde pongo las claves?** En variables de entorno de tu terminal (`export` en Linux y macOS, `$env:` en PowerShell). Nunca en `modelduel.toml` ni en ningún archivo del proyecto.

**¿Necesito claves?** No para `modelduel demo` ni para `replay`. Sí para las APIs que las exijan. Ollama y otros servicios locales pueden funcionar sin clave.

**¿Funciona con Ollama u OpenRouter?** Sí. Ambos se usan mediante `openai:<modelo>` y `OPENAI_BASE_URL`; OpenRouter requiere su clave y Ollama normalmente no.

**¿Es seguro?** Reduce el riesgo con temporales, límites, un entorno limpio y eliminación del árbol de procesos, pero no es un sandbox. No uses tareas de confianza dudosa sobre datos sensibles; usa un contenedor o una máquina virtual cuando puedas.

**¿Puedo usar mis propias tareas?** Sí. `modelduel init` crea una carpeta con tres tareas de ejemplo que puedes copiar y cambiar. Cada tarea pide una función concreta en `task.md` y la comprueba desde `test_task.py`.

**¿Qué significa «una sola ejecución es una señal débil»?** Un modelo puede responder de forma distinta a la misma tarea. Usa `--runs 3` o más y varias tareas antes de sacar conclusiones.

**¿Se guardan mis claves en el informe?** No. Se leen de variables de entorno y nunca se escriben en `results.json`, HTML ni Markdown. Los tests tampoco se envían al modelo: solo se envía el enunciado y las instrucciones de formato.

## Lo que tienes que hacer tú

Solo una cosa, y solo para duelos con modelos reales: crear la clave del proveedor en su web ([Google AI Studio](https://aistudio.google.com/apikey), [OpenAI](https://platform.openai.com/api-keys) u [OpenRouter](https://openrouter.ai/keys)) y definirla en tu terminal. Ollama y la demo no necesitan ninguna.

Novedades: consulta el [registro de cambios](https://github.com/BertMarti/modelduel/blob/main/CHANGELOG.md).

¿Quieres colaborar o ver cómo está hecho? Lee la [guía de desarrollo](https://github.com/BertMarti/modelduel/blob/main/docs/DESARROLLO.md).

Más información: [guía de uso](https://github.com/BertMarti/modelduel/blob/main/docs/USO.md) · [cómo contribuir](https://github.com/BertMarti/modelduel/blob/main/CONTRIBUTING.md) · [licencia MIT](https://github.com/BertMarti/modelduel/blob/main/LICENSE)
