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
apuntando al temporal y, en Linux y macOS, con límites de memoria, CPU, tamaño de archivo y
descriptores; al terminar mata todo el árbol de procesos. **No es un aislamiento real**: el código
tiene red y puede leer y escribir rutas absolutas del disco. Para código de modelos en los que no
confíes, ejecuta modelduel dentro de un contenedor o una máquina virtual.

Sí son vulnerabilidades, por ejemplo:

- Que una clave de API (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `OMNIROUTE_API_KEY`) acabe en
  `results.json`, en un informe HTML o Markdown, o en un mensaje de error.
- Que el contenido de una respuesta de un modelo o de un `results.json` ejecute código al abrir
  un informe (los informes no llevan JavaScript y tienen una CSP que lo prohíbe).
- Que el código de un modelo sobreviva al final de la ejecución sin desligarse a propósito.

No lo son: que el código generado use la red o lea archivos con rutas absolutas (está documentado
arriba).
