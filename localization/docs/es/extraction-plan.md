# Plan de extracción del sistema

**Framework (Sistema)** debe separarse de proyectos existentes de forma no destructiva.

## Secuencia

1. Auditar el material reutilizable y el material específico de cada proyecto.
2. Establecer la estructura canónica de EmbrAIon.
3. Extraer las capacidades reutilizables a un repositorio superior independiente.
4. Cuando sea práctico, mantener temporalmente las rutas antiguas y nuevas hasta completar la validación de equivalencia.
5. Comprobar la equivalencia de comportamiento, enrutamiento, revisión y herramientas.
6. Migrar los proyectos consumidores a una versión determinada de EmbrAIon.
7. Eliminar definiciones antiguas duplicadas únicamente después de demostrar la equivalencia.

El objetivo es evitar movimientos destructivos antes de que los límites de propiedad hayan quedado demostrados.
