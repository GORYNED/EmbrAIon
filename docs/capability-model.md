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

Core [engineering skills](guides/engineering-skills.md) cover reusable procedures such as compatibility migration, test design, dependency upgrades, performance investigation, and skill authoring. A [live skill evaluation](guides/skill-evals.md) can compare baseline and candidate behavior in fresh host sessions; a supplied execution record only checks recorded data. A skill-read event is narrow evidence of reading, not proof that the skill caused an outcome.

Optional [external capabilities](configuration/capabilities.md) have their own declared and observed lifecycle. An inventory declaration does not prove installation, host discovery, instruction loading, tool readiness, or execution. The [Unity skill pack](guides/unity-capabilities.md) is an opt-in extension outside vendor-neutral Core. Project facts and review gates still govern it.

Deterministic [organization checks](configuration/organization.md) apply incrementally to changed code. Existing debt is a baseline to distinguish new violations, not an exemption. [Checkpoints](guides/task-continuity.md) and [knowledge audits](guides/knowledge-maintenance.md) retain local freshness references; neither promotes learning or grants approval.
