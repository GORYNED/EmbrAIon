# Capability Model

EmbrAIon uses explicit capability types to avoid mixing policy, responsibility, procedure, orchestration, and facts.

| Type | Purpose |
| --- | --- |
| Rule | Required / prohibited / protected behavior |
| Agent | Responsibility and ownership |
| Skill | Repeatable procedure |
| Workflow | Ordered orchestration |
| Routing | Task/risk classification, execution constraints, host resolution, and optional project overrides |
| Tool | Deterministic operation |
| Adapter | Host/transport integration and projection |
| Knowledge | Facts and architecture |

A canonical capability should have one primary type. Cross-references are preferred over duplicating the same content in several types.

Routing is intentionally model-agnostic. Model names, pricing, lifecycle, and availability are not canonical EmbrAIon capabilities.
