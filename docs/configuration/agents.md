# Project Agents

Core already provides reusable roles such as Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward.

Use `.embraion/agents.yaml` only when the repository needs a **project-specific specialist** beyond those generic roles.

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

`embraion sync` without a consuming project remains Core-only and does not invent project specialists.

## Preview before writing

```bash
embraion projection diff --host codex --destination . --component agents
```

Then install intentionally:

```bash
embraion install --host codex --destination . --component agents
```

For every supported field, see [Project Configuration Files](project-files.md).
