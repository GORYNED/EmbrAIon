# Arquitectura

## Capas

1. **Core (Núcleo)** — reglas, agentes, habilidades, flujos, routing y conocimiento independientes de modelos y proveedores concretos.
2. **Adapters (Adaptadores)** — proyecciones para clientes de IA, transportes y paquetes portátiles.
3. **Tools (Herramientas)** — lógica determinista para estado, aprendizaje, seguridad, MCP, Git worktrees, validación, sincronización, instalación, diagnóstico y CLI.
4. **Project Overlay (Capa del proyecto)** — conocimiento, restricciones y routing overrides opcionales específicos del proyecto.
5. **External Capabilities** — sistemas e integraciones complementarios recomendados u opcionales.
6. **Evidence (Evidencia)** — pruebas, evaluaciones de comportamiento, referencias e informes.

## Modelo de agentes

Los agentes de Core usan nombres de funciones: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher y Steward. Elegir una función no determina un modelo concreto.

## Propiedad de la selección de modelos

Core clasifica el trabajo con route classes orientadas a la tarea. EmbrAIon no mantiene un catálogo global de modelos, precios ni lifecycle. El AI host controla la disponibilidad y la selección predeterminada/automática. El proyecto guarda solo sus overrides host-specific en `.embraion/project.yaml` cuando los necesita.

## State y Learning

El estado de ejecución se normaliza en registros privacy-safe. Los resultados repetidos pueden producir candidatos de mejora, pero cambiar Core requiere revisión y aprobación explícita.

## Spec Kit

Spec Kit se conecta como capacidad externa y no sustituye las reglas de Core, la verdad del proyecto ni la evidencia de validación.
