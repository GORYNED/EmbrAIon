# Architecture

## Layers

1. **Core** — vendor-neutral rules, agents, skills, workflows, routing, and reusable knowledge.
2. **Adapters** — concrete AI clients, transports, and package projections.
3. **Tools** — deterministic runtime, learning, security, MCP inventory, worktree, validation, sync, install, doctor, and CLI behavior.
4. **Project overlay** — consuming-project identity, agents, source classes, compatibility rules, validation, and product/domain knowledge.
5. **External capabilities** — recommended or optional companion systems and domain-specific integrations.
6. **Evidence** — deterministic tests, behavioral evals, validation records, reviews, baselines, and reports.

The project overlay may make local policy stricter, but it must not silently weaken Core hard gates. The consuming repository remains the source of truth for its product specification, architecture, compatibility contracts, validation commands, domain semantics, and project-specific knowledge.

## Roles and skills

EmbrAIon deliberately separates **responsibility** from **procedure**.

Core uses job-like roles:

| Role | Responsibility |
| --- | --- |
| Lead | Own task framing, delegation, integration, and completion |
| Worker | Implement bounded changes inside explicit ownership |
| Reviewer | Independently inspect correctness, risk, and regressions |
| Architect | Analyze boundaries, dependencies, and structural change |
| Analyst | Investigate evidence and turn it into actionable findings |
| Validator | Verify deterministic contracts and validation evidence |
| Researcher | Gather external or repository evidence without mutating product code |
| Steward | Maintain framework consistency and controlled evolution |

An **agent** expresses responsibility and ownership. A **skill** describes a repeatable engineering procedure. The same role can use several skills, and the same skill can serve more than one role.

Project-specific domain specialists belong in the consuming repository rather than generic Core. They are declared in `.embraion/agents.yaml` and can optionally extend a compatible non-Lead Core role while preserving its access boundary.

A task is therefore composed from more than a persona:

```text
responsibility
    +
procedure
    +
project facts
    +
routing / access constraints
    +
validation and review
```

This separation keeps roles small, procedures reusable, and project facts outside reusable Core.

## State and learning

Runtime state is normalized into privacy-safe session, context, validation, and run records. Repeated outcomes may create learning candidates, but canonical capability promotion is always reviewed, validated, and explicitly approved.

## Integrations

External server/tool configuration is inventoried separately from Core policy. Inventory records metadata and drift, never secret values.

Host adapters translate canonical EmbrAIon concepts into the files understood by Codex, GitHub Copilot, Claude Code, or a Portable bundle. Generated host files are projections rather than a second source of project policy.

## Model ownership

Core routing selects model-agnostic route classes. EmbrAIon does not own a global model catalog.

By default the execution host selects its own model. Projects may optionally store opaque host-specific model, effort, or options overrides in `.embraion/routing.yaml`. Those overrides can change model selection but cannot expand Core privacy, access, ownership, validation, or review policy.

## Spec Kit

Spec Kit is composed as an external capability. EmbrAIon recommends it for substantial specification work but does not vendor its skills, templates, or runtime.
