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

Delegation is owned by the Lead. Every projected non-Lead Core role carries a hard `do not recursively delegate` restriction. Project agents receive the same canonical restriction whether they extend a Core parent or are declared standalone. This keeps the execution tree bounded and prevents workers, reviewers, validators, or specialists from creating uncontrolled child-agent chains.

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

## Mechanisms vs project facts

The most important ownership boundary is simple:

| EmbrAIon Core | Consuming project |
| --- | --- |
| reusable roles and skills | architecture/domain knowledge |
| route and execution contracts | concrete deployments and routing preferences |
| generic security and privacy mechanics | protected paths and project privacy policy |
| generic validation/review mechanics | real project validation commands |
| host projection behavior | project-specific specialists |
| provider-neutral execution/fallback/health | optional execution bindings, credentials references, pricing sources |

A project can narrow or configure Core behavior, but it should not recreate a second generic AI framework inside the repository.

## Prompt flow is host-native

EmbrAIon does not sit in front of Codex, Copilot, or Claude Code as a mandatory prompt proxy.

The host receives the user's request normally. Installed projections teach that host about reusable Core roles/skills and about the repository's canonical `.embraion/` contract. The host then performs the reasoning and tool use.

This is why ordinary tasks can remain ordinary natural-language requests while configuration changes still land in deterministic project-owned files.

## Projected guidance vs deterministic execution

Not every EmbrAIon surface has the same enforcement power.

| Surface | Nature |
| --- | --- |
| Generated agents and skills | Host-native instructions/procedures |
| Routing resolution | Deterministic framework decision |
| Dispatch plan | Deterministic bounded plan |
| Host-native AI work | Executed by Codex/Copilot/Claude under host controls |
| `embraion execute` | Deterministic provider-neutral execution path |
| Project validation | Real project command execution with evidence |
| Enforcement | Deterministic policy/validation/review gate |

This distinction prevents a generated instruction file from being mistaken for a security boundary that only the host or an executable EmbrAIon gate can enforce.

See [How EmbrAIon works](getting-started/how-it-works.md) for the user-facing execution model.

## State and learning

Runtime state is normalized into privacy-safe session, context, validation, and run records. Repeated outcomes may create learning candidates, but canonical capability promotion is always reviewed, validated, and explicitly approved.

Local [task checkpoints](guides/task-continuity.md) retain bounded IDs, project-relative evidence paths, hashes, and the Git review snapshot. Resume only reports freshness; a changed source, pin, evidence record, index, or working file makes earlier conclusions stale. [Knowledge maintenance](guides/knowledge-maintenance.md) uses an explicit baseline and read-only audit to flag documents whose declared sources changed. Neither mechanism grants authorization, rewrites documentation, or promotes learning.

## Integrations

External server/tool configuration is inventoried separately from Core policy. Inventory records metadata and drift, never secret values.

The optional [external capability inventory](configuration/capabilities.md) separates declaration, installed configuration, host discovery, instruction loading, tool readiness, and execution. Local inventory and self-reported observations cannot establish later host stages as verified. The opt-in [Unity bundle](guides/unity-capabilities.md) is an extension, not a Core dependency or bundled third-party plugin.

Core [engineering skills](guides/engineering-skills.md) remain procedures. [Live skill evaluations](guides/skill-evals.md) launch fresh host sessions to compare behavior, whereas `eval run --record` assesses a supplied record. Incremental [code organization](configuration/organization.md) checks use the change baseline to identify new violations without waiving existing rules.

Host adapters translate canonical EmbrAIon concepts into the files understood by Codex, GitHub Copilot, Claude Code, or a Portable bundle. Generated host files are projections rather than a second source of project policy.

## Model ownership

Core routing selects model-agnostic route classes. EmbrAIon does not own a global model catalog.

By default the execution host selects its own model. Projects may optionally store opaque host-specific model, effort, or options overrides in `.embraion/routing.yaml`. Those overrides can change model selection but cannot expand Core privacy, access, ownership, validation, or review policy.

## Spec Kit

Spec Kit is composed as an external capability. EmbrAIon recommends it for substantial specification work but does not vendor its skills, templates, or runtime.
