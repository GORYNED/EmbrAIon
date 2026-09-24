# Modelo de capacidades

**Capability (Capacidad)** es una parte independiente de EmbrAIon con una responsabilidad claramente definida.

EmbrAIon utiliza tipos de capacidad explícitos para no mezclar reglas, responsabilidad, procedimientos, orden de ejecución y conocimiento factual.

| Tipo | Finalidad |
| --- | --- |
| **Rule (Regla)** | Comportamiento obligatorio, prohibido o protegido |
| **Agent (Agente)** | Responsabilidad y ámbito de propiedad |
| **Skill (Habilidad)** | Procedimiento repetible |
| **Workflow (Flujo de trabajo)** | Secuencia ordenada de ejecución |
| **Routing (Enrutamiento)** | Clasificación de tarea/riesgo, restricciones de ejecución, resolución del host y overrides opcionales del proyecto |
| **Tool (Herramienta)** | Operación determinista |
| **Adapter (Adaptador)** | Integración y proyección de host/transport |
| **Knowledge (Conocimiento)** | Hechos e información arquitectónica |

Cada capacidad canónica debe tener un único tipo principal. Cuando varias capacidades están relacionadas, es preferible utilizar referencias cruzadas en lugar de duplicar el mismo contenido.

El routing es deliberadamente agnóstico respecto a modelos. Los nombres de modelos, precios, lifecycle y disponibilidad no son capacidades canónicas de EmbrAIon.
