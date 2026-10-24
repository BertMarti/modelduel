---
name: publicar-version
description: Procedimiento para preparar y sacar una nueva versión del paquete en PyPI.
---

# Skill: Publicar Versión

Este proceso automatiza la publicación en PyPI mediante GitHub Actions y Trusted Publishing.

## Pasos previos al PR
1.  **Versión:** Actualiza `__version__` en `src/modelduel/__init__.py`.
2.  **Changelog:** Mueve el contenido de la sección `[Sin publicar]` en `CHANGELOG.md` a una nueva sección con la versión y fecha actual. Actualiza los enlaces de comparación al final del archivo.
3.  **Memoria:** Registra la decisión y el cambio en `MEMORY.md`.

## Proceso de lanzamiento
1.  **PR:** Abre un PR a `main` con los cambios anteriores.
2.  **Fusión:** Una vez aprobado y fusionado por el mantenedor (Alberto), ve a la pestaña de "Releases" en GitHub.
3.  **Release:** Crea una nueva "Release".
    *   **Tag:** Debe ser `vX.Y.Z` (ej. `v0.8.0`).
    *   **Target:** `main`.
    *   **Título y descripción:** Resume los cambios principales.
4.  **Publicación:** Al guardar la Release, el workflow `release.yml` se disparará, construirá el paquete y lo subirá a PyPI.

## Verificación final
Instala el paquete en un entorno limpio para confirmar que todo funciona:
```bash
pip install "modelduel[pytest]"
modelduel demo
```
