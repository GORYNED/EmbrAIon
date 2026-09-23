# Modelo de capacidades

**Capability (Capacidad)** es una parte independiente de EmbrAIon con una responsabilidad claramente definida.

EmbrAIon utiliza tipos de capacidad explícitos para no mezclar reglas, responsabilidad, procedimientos, orden de ejecución y conocimiento factual.

| Tipo | Finalidad |
| --- | --- |
| **Rule (Regla)** | Comportamiento obligatorio, prohibido o protegido |
| **Agent (Agente)** | Responsabilidad y ámbito de propiedad |
| **Skill (Habilidad)** | Procedimiento repetible |
| **Workflow (Flujo de trabajo)** | Secuencia ordenada de ejecución |
| **Routing (Enrutamiento)** | Selección de modelo, proveedor, nivel de razonamiento y modo de ejecución |
| **Tool (Herramienta)** | Operación determinista |
| **Adapter (Adaptador)** | Integración con un cliente o proveedor concreto |
| **Knowledge (Conocimiento)** | Hechos e información arquitectónica |

Cada capacidad canónica debe tener un único tipo principal. Cuando varias capacidades están relacionadas, es preferible utilizar referencias cruzadas en lugar de duplicar el mismo contenido.
