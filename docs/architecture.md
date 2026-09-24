# Architecture

## Layers

1. **Core** — vendor-neutral rules, agents, skills, workflows, routing, and knowledge.
2. **Adapters** — concrete hosts, transports, and package projections.
3. **Tools** — deterministic runtime, learning, security, MCP inventory, worktree, validation, sync, install, doctor, and CLI behavior.
4. **Project overlay** — consuming-project agents, domains, source classes, compatibility rules, and product knowledge.
5. **External capabilities** — recommended or optional companion systems and domain-specific integrations.
6. **Evidence** — deterministic tests, behavioral evals, baselines, and reports.

## Agent model

Core agents use job-like names: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward.

Project-specific domain specialists remain in the consuming project rather than becoming generic Core roles.

## State and learning

Runtime state is normalized into privacy-safe session records. Repeated outcomes may create learning candidates, but canonical capability promotion is always reviewed and approved.

## Integrations

External server/tool configuration is inventoried separately from Core policy. Inventory records metadata and drift, never secret values.

## Model ownership

Core routing selects model-agnostic route classes. EmbrAIon does not own a global model catalog.

By default the execution host selects its own model. Projects may optionally store opaque host-specific model/effort/options overrides in the Project Overlay. Those overrides can change model selection but cannot expand Core privacy, access, ownership, validation, or review policy.

## Spec Kit

Spec Kit is composed as an external capability. EmbrAIon recommends it for substantial specification work but does not vendor its skills, templates, or runtime.
