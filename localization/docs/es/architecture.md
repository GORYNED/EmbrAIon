# Arquitectura

## Capas

1. **Core (Núcleo)** — reglas, agentes, habilidades, flujos, enrutamiento y conocimiento independientes de un proveedor concreto.
2. **Adapters (Adaptadores)** — representaciones para clientes, modelos, proveedores, métodos de conexión y paquetes portátiles concretos.
3. **Tools (Herramientas)** — lógica ejecutable determinista: estado de ejecución, aprendizaje, seguridad, inventario MCP, gestión de árboles de trabajo Git, validación, sincronización, instalación, diagnóstico e interfaz de línea de comandos.
4. **Project Overlay (Capa del proyecto)** — agentes, dominios, clases de origen, reglas de compatibilidad y conocimiento de producto específicos de cada proyecto.
5. **External Capabilities (Capacidades externas)** — sistemas complementarios e integraciones de dominio recomendados u opcionales.
6. **Evidence (Evidencia)** — pruebas deterministas, evaluaciones de comportamiento, resultados de referencia e informes.

## Modelo de agentes

Los agentes del Core usan nombres de funciones: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher y Steward.

Los especialistas propios de un dominio concreto permanecen en el proyecto que utiliza EmbrAIon y no se convierten en funciones universales del Core.

## State (Estado) y Learning (Aprendizaje)

El estado de ejecución se normaliza en registros de sesión que no contienen contenido protegido. Los resultados repetidos pueden producir candidatos de mejora, pero toda nueva capacidad canónica requiere revisión y aprobación explícita.

## Integrations (Integraciones)

La configuración de servidores y herramientas externos se inventaría por separado de las reglas del Core. El inventario conserva metadatos y diferencias, pero nunca valores secretos.

## Propiedad de la información de modelos

El enrutamiento del Core selecciona clases abstractas de ruta. Los catálogos de adaptadores contienen identificadores actuales de modelos, niveles de razonamiento, precios, estado del ciclo de vida y parámetros de selección de cada cliente.

## Spec Kit

Spec Kit se conecta como capacidad externa. EmbrAIon lo recomienda para trabajo importante basado en especificaciones, pero no integra sus habilidades, plantillas ni lógica de ejecución dentro del Core.
