# Project Overlay (Capa del proyecto)

Un repositorio consumidor guarda la configuración de EmbrAIon dentro de `.embraion/`.

Responsabilidad de cada archivo:

- `project.yaml`: repositorio/versión de EmbrAIon, identidad del proyecto y `capabilities`;
- `knowledge.yaml`: referencias al conocimiento del proyecto y metadatos de selección de contexto;
- `policy.yaml`: clases de fuentes, política de review y privacy;
- `routing.yaml`: overrides opcionales de model/effort/options;
- `validation.yaml`: perfiles de validación;
- `agents.yaml`: agentes específicos del proyecto.

La capa del proyecto puede añadir reglas más estrictas, pero no puede debilitar silenciosamente las restricciones obligatorias del Core.

## Resolución automática de versiones

Para los comandos normales, el launcher global encuentra el `.embraion/project.yaml` más cercano, lee `framework.version` y lo compara con su propia versión. Si son diferentes, EmbrAIon prepara un runtime aislado en `~/.embraion/versions/<version>/` e instala allí la distribución exacta `embraion==<version>` desde PyPI.

A continuación, el comando se ejecuta con esa versión almacenada en caché. Así, una sola máquina puede tener un launcher global y distintos repositorios pueden permanecer en diferentes versiones de EmbrAIon.

`embraion init` y `embraion update` omiten intencionadamente la delegación al runtime del proyecto:

- `init` crea la configuración modular y escribe la versión del launcher global;
- `update` cambia únicamente el pin del repositorio actual;
- `--framework-version` permite seleccionar explícitamente una versión publicada concreta.

`EMBRAION_HOME` es un override explícito para desarrollo y desactiva la delegación automática de versión en ese proceso.

El propio repositorio del proyecto sigue siendo la fuente canónica de la especificación del producto, la arquitectura, los contratos de compatibilidad, la evidencia de validación y el conocimiento del dominio.
