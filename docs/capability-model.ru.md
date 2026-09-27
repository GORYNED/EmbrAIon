# Модель возможностей

EmbrAIon использует явные типы capabilities, чтобы не смешивать policy, responsibility, procedure, orchestration и facts.

| Type | Purpose |
| --- | --- |
| Rule | Required / prohibited / protected behavior |
| Agent | Responsibility и ownership |
| Skill | Повторяемая procedure |
| Workflow | Ordered orchestration |
| Routing | Task/risk classification, execution constraints, host resolution и optional project overrides |
| Tool | Deterministic operation |
| Adapter | Host/transport integration и projection |
| Knowledge | Facts и architecture |

Canonical capability должна иметь один primary type. Cross-references предпочтительнее, чем дублирование одного content в нескольких types.

Routing намеренно model-agnostic. Concrete model names, provider rates, lifecycle state и host availability не являются canonical Core capabilities.

EmbrAIon предоставляет reusable **механизмы** deployment eligibility, provider-neutral execution, pricing refresh/snapshots, health и evidence. Конкретные models, providers, rates, source URLs и availability facts остаются project- или host-owned.
