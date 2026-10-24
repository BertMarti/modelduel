# Política de seguridad

## Versiones con soporte

Solo la última versión publicada en [PyPI](https://pypi.org/project/modelduel/) recibe correcciones de seguridad.

## Cómo avisar de una vulnerabilidad

No abras un issue público. Usa el aviso privado de GitHub:
[«Report a vulnerability»](https://github.com/BertMarti/modelduel/security/advisories/new).
Cuenta qué pasa, cómo reproducirlo y qué versión usas. Intentaremos responder en una semana.

## Qué cubre y qué no

modelduel **ejecuta en tu máquina el código que generan los modelos**. Lo hace en un directorio
temporal, con límite de tiempo, sin las variables de entorno que parecen secretos, con `HOME`
apuntando al temporal y, en Linux y macOS, con límites de CPU, tamaño de archivo (256 MiB) y
descriptores, más un límite de memoria (4 GiB de espacio de direcciones) que solo aplica Linux; al
terminar mata todo el árbol de procesos. En Linux lo hace un supervisor «subreaper»
(`prctl(PR_SET_CHILD_SUBREAPER)`), así que tampoco sobreviven los procesos que se desligan con
`setsid()` o un doble fork. `modelduel doctor` muestra qué medidas aplica tu sistema.

**No es un aislamiento real**: el código tiene red, puede leer y escribir rutas absolutas del
disco y el disco total que llena solo lo acota el tiempo (256 MiB por archivo). En macOS un proceso
que se desligue con `setsid()` puede sobrevivir; en Windows no hay límite de memoria. Una solución
hostil que mate a su supervisor deja la limpieza en manos de una marca en el entorno, que puede
borrar si vuelve a ejecutarse con otro entorno. Para código de modelos en los que no confíes,
ejecuta modelduel dentro de un contenedor (hay una orden `docker run` lista para copiar en el
README, apartado «Seguridad») o en una máquina virtual.

Sí son vulnerabilidades, por ejemplo:

- Que una clave de API (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `OMNIROUTE_API_KEY`) acabe en
  `results.json`, en un informe HTML o Markdown, o en un mensaje de error.
- Que el contenido de una respuesta de un modelo o de un `results.json` ejecute código al abrir
  un informe (los informes no llevan JavaScript y tienen una CSP que lo prohíbe).
- Que el código de un modelo sobreviva al final de la ejecución en Linux (salvo matando antes a su
  supervisor y cambiando de entorno, documentado arriba), o en cualquier sistema sin desligarse a
  propósito del árbol de procesos.

No lo son: que el código generado use la red o lea archivos con rutas absolutas (está documentado
arriba).
