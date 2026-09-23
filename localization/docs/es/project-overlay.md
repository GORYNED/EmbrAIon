# Project Overlay (Capa del proyecto)

Un repositorio se incorpora explícitamente a EmbrAIon mediante `.embraion/project.yaml`.

La capa del proyecto registra:

- el repositorio de EmbrAIon y la versión del sistema declarados;
- la identidad del proyecto;
- la ubicación del conocimiento del proyecto;
- los Agent (Agentes) específicos del proyecto;
- las capacidades externas.

La capa del proyecto puede añadir reglas más estrictas, pero no puede debilitar silenciosamente las restricciones obligatorias del Core.

## Resolución automática de versiones

La versión pública `v0.1.0` registra una versión del proyecto, pero todavía no la resuelve automáticamente. El `main` actual implementa el resolver para la siguiente versión.

Para los comandos normales, el launcher global encuentra el `.embraion/project.yaml` más cercano, lee `framework.version` y lo compara con su propia versión. Si son diferentes, EmbrAIon prepara un runtime aislado en `~/.embraion/versions/<version>/` e instala allí la distribución exacta `embraion==<version>` desde PyPI.

A continuación, el comando se ejecuta con esa versión almacenada en caché. Así, una sola máquina puede tener un launcher global y distintos repositorios pueden permanecer en diferentes versiones de EmbrAIon.

`embraion init` y `embraion update` omiten intencionadamente la delegación al runtime del proyecto:

- `init` escribe la versión del launcher global en un nuevo Project Overlay;
- `update` cambia únicamente el pin del repositorio actual;
- `--framework-version` permite seleccionar explícitamente una versión publicada concreta.

El pin heredado `0.1.0-dev` escrito por la primera versión se normaliza automáticamente a la distribución publicada `0.1.0`.

`EMBRAION_HOME` es un override explícito para desarrollo y desactiva la delegación automática de versión en ese proceso.

El propio repositorio del proyecto sigue siendo la fuente canónica de la especificación del producto, la arquitectura, los contratos de compatibilidad, la evidencia de validación y el conocimiento del dominio.
