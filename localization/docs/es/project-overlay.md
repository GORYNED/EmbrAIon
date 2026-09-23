# Project Overlay (Capa del proyecto)

Un repositorio se incorpora explícitamente a EmbrAIon mediante `.embraion/project.yaml`.

La capa del proyecto registra:

- el repositorio de EmbrAIon y la versión del sistema declarados;
- la identidad del proyecto;
- la ubicación del conocimiento del proyecto;
- los Agent (Agentes) específicos del proyecto;
- las capacidades externas.

La capa del proyecto puede añadir reglas más estrictas, pero no puede debilitar silenciosamente las restricciones obligatorias del Core.

## Comportamiento actual de versiones en v0.1.x

`embraion init` escribe en `.embraion/project.yaml` la versión del sistema expuesta por la instalación de EmbrAIon que se está ejecutando.

La implementación actual `v0.1.x` no resuelve automáticamente esa versión registrada al ejecutar después `install` o `sync`. Esos comandos generan representaciones con los datos del sistema disponibles para el CLI que se está ejecutando. Por tanto, el campo de versión es actualmente una declaración de compatibilidad y un límite explícito de actualización, no todavía un resolvedor automático de runtime por proyecto.

Para una reproducibilidad exacta, utilice la distribución del CLI/sistema que coincida con la versión registrada por el proyecto.

El propio repositorio del proyecto sigue siendo la fuente canónica de la especificación del producto, la arquitectura, los contratos de compatibilidad, la evidencia de validación y el conocimiento del dominio.
