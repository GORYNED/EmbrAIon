# Project Agents

Core already provides reusable roles such as Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward.

Use `.embraion/agents.yaml` only when the repository needs a **project-specific specialist** beyond those generic roles.

An empty `agents: []` adds no project specialists. It does not disable Core roles or Lead orchestration. Users can ask for ordinary engineering outcomes without naming roles or explicitly requesting delegation.

Lead selects the smallest useful role set by purpose: Analyst clarifies requirements, Architect resolves architecture and boundaries, Researcher checks uncertain facts, Worker implements bounded changes, Validator gathers fresh checks, Reviewer independently evaluates substantial implementation, and Steward handles compatibility and persistence. Lead handles trivial work directly and proactively delegates when specialists materially improve quality, ownership, evidence, or safe parallelism.

Assignments include bounded intent, owned paths or read-only scope, contracts, dependencies, acceptance criteria, and expected evidence. Read-only discovery and independent writes may run in parallel; overlapping files, shared contracts, and dependent work require serialization or explicit isolation. Substantial implementation receives independent read-only review when Core or stricter project policy requires it. Lead integrates results, resolves findings, refreshes evidence after fixes, and retains final acceptance authority. These responsibilities are canonical in the [Core Lead role](https://github.com/GORYNED/EmbrAIon/blob/main/core/agents/lead.yaml).

Role, access, route class, execution host, and model choice remain independent. Lead classifies each concrete assignment and queries project routing before native spawn; role names do not define model tiers. See [Routing](../model-routing.md).

## Example

```yaml
agents:
  - id: domain-specialist
    title: Domain Specialist
    extends: reviewer
    purpose: Review project-specific domain behavior.
    access: read-only
    responsibilities:
      - focus review on project-specific domain contracts
    restrictions:
      - do not modify project files
    triggers:
      - domain-focused review
    outputs:
      - domain review findings
```

## Required fields

- `id` — unique kebab-case project agent ID;
- `purpose` — concise project-specific responsibility;
- `access` — `read-only` or `workspace-write`;
- `responsibilities` — one or more project-specific responsibilities.

## Optional inheritance

A project agent may `extend` an existing non-Lead Core role.

When it does, EmbrAIon appends the project-specific responsibilities/restrictions/triggers/outputs but preserves the inherited access boundary.

A project agent cannot:

- shadow a Core agent ID;
- extend the Core `lead` role;
- widen a read-only inherited role into writable access.

## Host projection

During project installation, project agents are emitted as native host files:

```text
Codex          .codex/agents/<id>.toml
GitHub Copilot .github/agents/<id>.agent.md
Claude Code    .claude/agents/<id>.md
```

Each project specialist profile includes its `triggers` and `outputs`, and the projected `orchestration` skill lists project specialists in a compact `Project specialists` section so Lead knows when to delegate. Nothing is added when the project declares no specialists.

`embraion sync` without a consuming project remains Core-only and does not invent project specialists.

For Codex, the `config` component also projects Lead orchestration into root `developer_instructions`; the `agents` component provides specialist files. Generated Codex role files omit model/effort choices so native spawn can apply the resolved assignment choice. Host-default assignments use Codex defaults or inheritance. Trust, permissions, higher-priority instructions, and host capabilities determine how guidance can execute; static files do not guarantee delegation or replace executable evidence gates. See [Codex](../hosts/codex.md) for merge ownership and host limits.

Codex, Copilot, Claude Code, and Portable projections also carry the canonical `orchestration` skill with the generated Core Lead contract. This supplies common guidance through native skill surfaces, with skill loading selected by each host.

## Preview before writing

```bash
embraion projection diff --host codex --destination . --component agents
```

Then install intentionally:

```bash
embraion install --host codex --destination . --component agents
```

For every supported field, see [Project Configuration Files](project-files.md).
