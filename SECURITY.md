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

En Linux, la red de la solución se corta por defecto con un espacio de nombres de
usuario y de red (sin root; si el sistema no lo permite, se avisa), y en Windows el Job Object
limita la memoria a 1 GiB por proceso.

**Sin contenedor no es un aislamiento completo**: el código puede leer y escribir rutas absolutas
del disco y el disco total que llena solo lo acota el tiempo (256 MiB por archivo); en macOS y
Windows tiene red. En macOS un proceso que se desligue con `setsid()` puede sobrevivir. Una
solución hostil que mate a su supervisor deja la limpieza en manos de una marca en el entorno, que
puede borrar si vuelve a ejecutarse con otro entorno. Para código de modelos en los que no
confíes, usa **`modelduel run --sandbox docker`** (o `podman`): cada ejecución corre en un
contenedor desechable sin red, sin privilegios, de solo lectura y con techos de memoria, CPU y
procesos. También puedes generar con `--solo-generar` y ejecutar los tests en otra máquina con
`--replay`.

Las **tareas en JavaScript y TypeScript** (experimental, desde la 1.1.0) pasan por el mismo runner
y los mismos límites (también el contenedor, con la imagen oficial de Node fijada por digest).
Además, Node corre con su modelo de permisos: solo puede leer y escribir en la carpeta de la
ejecución y no puede lanzar procesos hijos, *workers* ni complementos nativos. Node advierte de que
ese modelo es una red de seguridad y no una barrera frente a código malicioso, así que no cambia la
recomendación: para código que no es tuyo, `--sandbox docker`.

Sí son vulnerabilidades, por ejemplo:

- Que una clave de API (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `OMNIROUTE_API_KEY`) acabe en
  `results.json`, en un informe HTML o Markdown, o en un mensaje de error.
- Que el contenido de una respuesta de un modelo o de un `results.json` ejecute código al abrir
  un informe (los informes no llevan JavaScript y tienen una CSP que lo prohíbe).
- Que el código de un modelo sobreviva al final de la ejecución en Linux (salvo matando antes a su
  supervisor y cambiando de entorno, documentado arriba), o en cualquier sistema sin desligarse a
  propósito del árbol de procesos.
- Que con `--sandbox docker|podman` el código llegue a la red, escriba fuera de su carpeta
  temporal y `/tmp`, reciba variables de tu entorno o se ejecute como root; o que en Linux, con la
  red cortada por defecto, llegue a otra interfaz que no sea `lo`.
- Que el código de una tarea JavaScript o TypeScript se ejecute sin los límites del runner (fuera
  del supervisor, con tus claves en el entorno o, con `--sandbox`, fuera del contenedor).
- Que un `respuestas.json` manipulado haga que `--replay` ejecute algo fuera del runner (el código
  de las respuestas y los tests copiados SÍ se ejecutan, como en cualquier duelo: reprodúcelos con
  `--sandbox docker` si no son tuyos).

No lo son: que sin contenedor el código generado lea archivos con rutas absolutas (en JavaScript
y TypeScript, saltándose el modelo de permisos de Node), o use la red
en macOS, en Windows, con `--sandbox ninguno` o en un Linux que no permite espacios de nombres
(está documentado arriba y `modelduel doctor` lo dice).

Tampoco lo es que una solución escrita para engañar apruebe tests que no resuelve (por ejemplo,
devolviendo un objeto que dice ser igual a cualquier cosa o tocando pytest, con el que comparte
proceso): el marcador mide lo que comprueban los tests de la tarea. El informe enseña el código de
cada modelo para poder revisarlo (ver «Límites conocidos» en `docs/USO.md`).
