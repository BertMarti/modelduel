# modelduel

![modelduel: modelo contra modelo](https://raw.githubusercontent.com/BertMarti/modelduel/main/docs/img/banner.svg)

**Dos modelos, una tarea, los mismos tests.** Compara modelos de IA con problemas de programación de tu propio trabajo, no con rankings hechos para otra persona.

[![PyPI](https://img.shields.io/pypi/v/modelduel.svg)](https://pypi.org/project/modelduel/)
[![CI](https://github.com/BertMarti/modelduel/actions/workflows/ci.yml/badge.svg)](https://github.com/BertMarti/modelduel/actions/workflows/ci.yml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-b5e853.svg)](https://github.com/BertMarti/modelduel/blob/main/LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-ff7eb6.svg)](https://www.python.org/downloads/)
[![web](https://img.shields.io/badge/web-modelduel-4fd1e5.svg)](https://bertmarti.github.io/modelduel/)

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

1. Instala modelduel y pytest:

   ```bash
   pip install "modelduel[pytest]"
   ```

2. Prueba la demo sin claves ni coste:

   ```bash
   modelduel demo
   ```

   La demo enfrenta respuestas grabadas de `alfa`, `beta` y `gamma`, y deja el informe en `modelduel-demo/`.

3. Define la clave del proveedor que quieras y lanza un duelo real. Por ejemplo, en Linux o macOS:

   ```bash
   export GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"
   export OPENAI_API_KEY="PEGA_AQUI_TU_CLAVE"
   modelduel run MIS-EJEMPLOS/tasks --a gemini:<modelo> --b openai:<modelo> --runs 3 --out runs/duelo
   ```

   Para OmniRoute, usa `OMNIROUTE_API_KEY` si tu instalación la necesita. Las claves se leen de variables de entorno, nunca se escriben en el proyecto.

4. Abre `runs/duelo/index.html` en el navegador. Es un informe autocontenido, sin JavaScript y con versión para imprimir. Para compartirlo en GitHub, genera además `informe.md` con `--format html,md`.

5. Empieza tus propias tareas a partir de una plantilla:

   ```bash
   modelduel demo --copy MIS-EJEMPLOS
   ```

   Cambia el enunciado y los tests de `MIS-EJEMPLOS/tasks` y vuelve a lanzar `modelduel run`.

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
> **El código generado por los modelos se ejecuta en tu máquina.** modelduel crea un directorio temporal propio y lo borra al terminar, ejecuta los tests en un subproceso con límite de tiempo, elimina las variables de entorno que parecen secretos (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `PASS`, `AUTH`, `CREDENTIAL`, `PRIVATE`, `COOKIE`, `SESSION` y similares), retira `SSH_AUTH_SOCK` y apunta `HOME`/`USERPROFILE` al temporal. En Linux y macOS aplica además límites del sistema: 1 GiB de memoria, límite de CPU, archivos de 64 MiB como máximo, 256 descriptores y sin volcados de memoria. Al terminar mata el árbol de procesos (Job Object en Windows y grupo de procesos en POSIX).
>
> Esto **no es un aislamiento real**: el código conserva acceso a la red y al disco mediante rutas absolutas. Úsalo con tareas de confianza e, idealmente, dentro de un contenedor o una máquina virtual.

## Preguntas frecuentes

**¿Cuesta dinero?** La demo no. Los duelos reales usan la cuenta y la clave del proveedor que elijas; el informe estima el coste si aportas sus tarifas con `--prices`.

**¿Necesito claves?** No para `modelduel demo` ni para `replay`. Sí para las APIs que las exijan. Ollama y otros servicios locales pueden funcionar sin clave.

**¿Funciona con Ollama u OpenRouter?** Sí. Ambos se usan mediante `openai:<modelo>` y `OPENAI_BASE_URL`; OpenRouter requiere su clave y Ollama normalmente no.

**¿Es seguro?** Reduce el riesgo con temporales, límites, un entorno limpio y eliminación del árbol de procesos, pero no es un sandbox. No uses tareas de confianza dudosa sobre datos sensibles; usa un contenedor o una máquina virtual cuando puedas.

**¿Puedo usar mis propias tareas?** Sí. `modelduel demo --copy MIS-EJEMPLOS` crea una plantilla. Cada tarea pide una función concreta en `task.md` y la comprueba desde `test_task.py`.

**¿Qué significa «una sola ejecución es una señal débil»?** Un modelo puede responder de forma distinta a la misma tarea. Usa `--runs 3` o más y varias tareas antes de sacar conclusiones.

**¿Se guardan mis claves en el informe?** No. Se leen de variables de entorno y nunca se escriben en `results.json`, HTML ni Markdown. Los tests tampoco se envían al modelo: solo se envía el enunciado y las instrucciones de formato.

Novedades: consulta el [registro de cambios](https://github.com/BertMarti/modelduel/blob/main/CHANGELOG.md).

¿Quieres colaborar o ver cómo está hecho? Lee la [guía de desarrollo](https://github.com/BertMarti/modelduel/blob/main/docs/DESARROLLO.md).

Más información: [guía de uso](https://github.com/BertMarti/modelduel/blob/main/docs/USO.md) · [cómo contribuir](https://github.com/BertMarti/modelduel/blob/main/CONTRIBUTING.md) · [licencia MIT](https://github.com/BertMarti/modelduel/blob/main/LICENSE)
