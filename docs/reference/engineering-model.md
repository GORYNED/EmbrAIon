# Engineering Model Deep Dive

This page is the precise engineering model behind the simpler Getting Started flow.

## Projected guidance vs deterministic surfaces

| Surface | Meaning | Who executes it? |
| --- | --- | --- |
| Generated agents / skills | Host-native instructions and procedures | AI host |
| `embraion route` | Resolve routing policy | EmbrAIon CLI |
| `embraion dispatch` | Build a bounded plan | EmbrAIon CLI |
| Host-native edits/search/tools | Actual engineering work | AI host |
| `embraion execute` | Bounded provider-neutral request | EmbrAIon runtime |
| `embraion validation run` | Real project commands + evidence | EmbrAIon CLI + project commands |
| `embraion enforcement check` | Protected-path / validation / review gate | EmbrAIon CLI |
| GitHub enforcement workflow | Merge-time CI surface | GitHub Actions |

Instruction delivery and deterministic enforcement are different mechanisms.

## Core vs project ownership

| EmbrAIon Core owns | Project owns |
| --- | --- |
| generic roles and skills | architecture/domain knowledge |
| route/execution contracts | deployments and routing preferences |
| generic privacy/security mechanics | protected paths and project policy |
| validation/review mechanics | real validation commands |
| host projection behavior | project-specific agents |
| provider-neutral fallback/health | execution bindings and pricing sources |

## Deployments vs routing vs execution vs pricing

| Concept | Question | Project file |
| --- | --- | --- |
| Deployment | **What** reusable concrete choice exists? | `.embraion/deployments.yaml` |
| Routing | **When** should a route/role select it? | `.embraion/routing.yaml` |
| Execution binding | **How** may it be invoked safely? | `.embraion/execution.yaml` |
| Pricing | **How** is cost interpreted/refreshed? | `.embraion/pricing.yaml` |

![Deployment → Routing → Execution → Pricing](../assets/diagrams/en/15-deployment-routing-execution-pricing.svg){ loading=lazy }

## Route classes

| Route | Meaning |
| --- | --- |
| `bounded-read` | narrow read-only discovery/research |
| `bounded-write` | mechanical or tightly bounded writable work |
| `ordinary` | limited ordinary engineering |
| `substantial` | substantial engineering + standard review |
| `complex` | cross-domain, lifecycle, concurrency, or difficult review |
| `critical` | exceptional protected-decision risk such as persisted-data loss, recovery failure, systemic security exposure, or a breaking contract migration; size alone is not critical |

Route classes describe work and risk, not permanent model tiers.

## Host-native vs provider-neutral execution

### Host-native

The AI host owns reasoning and tools. EmbrAIon supplies project knowledge/policy/roles/routing and validation/review contracts.

### Provider-neutral

`embraion execute` owns a bounded external/API attempt path through explicit project bindings. It can normalize failures/health and apply eligible fallback without widening the original request ceilings.

A routable deployment is not automatically executable; without a binding, the runtime can return `handoff-required`.

## Evidence and acceptance

Transport completion is not project correctness. A project can still require deterministic validation, project-specific acceptance, independent review, and human merge approval.

## Related

- [How EmbrAIon Works](../getting-started/how-it-works.md)
- [Project Configuration](../configuration/index.md)
- [Model Routing](../model-routing.md)
- [Execution & Providers](../configuration/execution.md)
- [Pricing & Cost](../configuration/pricing.md)
- [Validation & Evidence](../validation.md)
