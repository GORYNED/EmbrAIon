# Resumen

EmbrAIon es un **AI-First Engineering System (Sistema de ingeniería AI-First)** reutilizable.

**Core (Núcleo)** utiliza agentes con nombres de funciones, reglas por tipos de capacidad, routing orientado al tipo de tarea y agnóstico respecto a modelos, y herramientas deterministas. EmbrAIon no es propietario de los nombres actuales de modelos: el cliente de IA controla la disponibilidad y la selección predeterminada/automática, mientras que el proyecto guarda solo overrides host-specific cuando los necesita.

Esto permite que EmbrAIon evolucione sin quedar ligado a Codex, GitHub Copilot, Claude Code, un proveedor concreto o una generación concreta de modelos.

Spec Kit se recomienda como complemento externo para trabajo importante que se beneficie de una especificación formal.

El repositorio consumidor aporta conocimiento de dominio, restricciones y overrides opcionales mediante **Project Overlay (Capa del proyecto)**.
