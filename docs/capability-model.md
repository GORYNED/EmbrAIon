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

Routing is intentionally model-agnostic. Concrete model names, provider rates, lifecycle state, and host availability are not canonical Core capabilities.

EmbrAIon does provide reusable **mechanisms** for deployment eligibility, provider-neutral execution, pricing refresh/snapshots, health, and evidence. The concrete models, providers, rates, source URLs, and availability facts remain project- or host-owned.
