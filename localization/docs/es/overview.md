# Resumen

EmbrAIon es un **AI-First Engineering System (Sistema de ingeniería AI-First)** reutilizable.

**Core (Núcleo)** utiliza agentes con nombres de funciones, reglas separadas por tipos de capacidad, enrutamiento independiente del proveedor y herramientas deterministas. La información de clientes y modelos concretos se mantiene aislada en **Adapters (Adaptadores)**, por lo que EmbrAIon puede evolucionar sin quedar ligado a Codex, GitHub Copilot, Claude Code ni a un único proveedor.

Spec Kit se recomienda como complemento externo para trabajo importante que se beneficie de una especificación formal.

El repositorio que utiliza EmbrAIon aporta su conocimiento de dominio y sus restricciones mediante **Project Overlay (Capa del proyecto)**.
