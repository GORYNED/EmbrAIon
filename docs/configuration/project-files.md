# Project Configuration Files

This page describes every file created by `embraion init` under `.embraion/`.

## `.embraion/project.yaml`

This is the stable project identity and framework-pin file.

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: <pinned-version>

project:
  name: MyProject

capabilities: {}
```

### `framework`

`framework.repository` identifies the upstream EmbrAIon framework. `framework.version` pins the project to an exact EmbrAIon release. Ordinary CLI commands resolve that version and may use an isolated cached runtime when the globally installed launcher is newer.

### `project`

`project.name` is the project identity used by the project overlay.

### `capabilities`

`capabilities` is intentionally open project metadata. It can describe project traits such as an engine, language family, or integration surface.

```yaml
capabilities:
  engine:
    family: ExampleEngine
    language: ExampleLanguage
```

At the current contract level, EmbrAIon does not use arbitrary `capabilities` values to select models or bypass policy. Treat it as an extension point and project metadata, not as a security or routing mechanism.

## `.embraion/knowledge.yaml`

This file points EmbrAIon at project-owned knowledge.

New projects include canonical Project Contract Slots:

```yaml
slots:
  constitution:
  architecture:
  source-authority:
  compatibility:
  persistence:
  engineering-workflow:
  specification:
```

A project binds only the slots it actually owns:

```yaml
slots:
  architecture: docs/architecture.md
  source-authority: docs/references/project-sources.md
  persistence:
    path: docs/persistence.md
    data-class: PRIVATE
```

These slot names are framework-owned semantic extension points. EmbrAIon knows the reusable responsibility of each slot; the consuming repository owns the referenced content. Unbound slots remain null and are not selected.

In v0.10.0 the top-level `slots` key becomes framework-reserved. This is an intentional pre-1.0 contract cleanup rather than a compatibility shim for hypothetical earlier custom entries named `slots`.

Ordinary custom knowledge remains supported alongside slots:

```yaml
product: knowledge/project.md
domain-video: knowledge/video.md
```

The structured form adds context-selection metadata:

```yaml
architecture:
  path: knowledge/architecture.md
  data-class: PRIVATE
  trust: project
  roles:
    - architect
    - lead
  triggers:
    - architecture
```

Supported structured fields are:

- `path` — required path inside the consuming repository;
- `data-class` — `PUBLIC`, `PRIVATE`, or `CONFIDENTIAL`;
- `trust` — `project`, `external`, or `generated`;
- `roles` — optional roles eligible to receive that knowledge;
- `triggers` — optional task terms used for context selection.

Knowledge files remain ordinary repository files. `knowledge.yaml` stores references and selection metadata, not duplicated knowledge content.

## `.embraion/policy.yaml`

This file owns project safety and source classification policy.

```yaml
sources:
  canonical:
    - src/**
  protected:
    - vendor/**
  generated:
    - build/**
  external:
    - external/**

review:
  substantial-required: true

privacy:
  default-class: PRIVATE

enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

### `sources`

The four path classes are:

- `canonical` — project-owned source-of-truth paths;
- `protected` — paths that should not be mutated through ordinary writable work;
- `generated` — generated artifacts rather than canonical authored source;
- `external` — externally sourced material.

### `review`

`substantial-required: true` requires review evidence for substantial work where the execution contract calls for it.

### `privacy`

`default-class` defines the project default when a more specific data classification is not supplied. Valid values are `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`.

Model selection never widens these policy boundaries.

### `enforcement`

Enforcement is disabled by default. The policy records whether an explicitly installed gate is active, which validation profile it must run, and whether independent review is required:

```yaml
enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

Enable a CI surface only by an explicit command:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected \
  --require-review
```

This creates `.github/workflows/embraion-enforcement.yml`, enables the policy gate, runs protected-path and validation checks on pull requests, and optionally requires at least one current approved GitHub review. Existing different workflow content is refused unless `--force` is deliberately supplied.

EmbrAIon does not silently install host-native hooks. `harness audit` continues to report native hook capability, while enforcement installation remains an explicit project action.

## `.embraion/routing.yaml`

This file contains optional model-selection overrides for specific AI hosts.

The default is:

```yaml
overrides: {}
```

That means EmbrAIon resolves the route as `host-default`, and the active AI client chooses its own default/automatic model.

A project can override a route:

```yaml
overrides:
  codex:
    routes:
      complex:
        model: "<selector reported by the host>"
        effort: "<host-supported effort>"
```

Or a role:

```yaml
overrides:
  codex:
    roles:
      reviewer:
        model: "<selector reported by the host>"
```

Role overrides are more specific and merge over route overrides.

EmbrAIon deliberately does not maintain a model catalog. `model`, `effort`, and `options` are opaque host-owned values. Only use selectors and settings confirmed by the active host.

## `.embraion/validation.yaml`

This file declares project validation profiles.

```yaml
profiles:
  fast:
    - python -m unittest discover -s tests
  affected:
    - python -m unittest discover -s tests
  full:
    - python -m unittest discover -s tests
    - python -m compileall src
```

`fast`, `affected`, and `full` are the default profile names, but the schema permits additional named profiles.

The effective policy exposes these profiles through:

```bash
embraion policy show
embraion policy show --json
```

Profiles are executable first-class project configuration:

```bash
embraion validation list
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

Commands run sequentially from the project root. Each invocation writes redacted structured evidence under `.embraion/state/validation/`. A failed command makes the profile fail; by default remaining commands still run so the result captures complete evidence. Use `--fail-fast` when later commands would be meaningless after the first failure.

An empty profile is reported as `skipped`, never as a false pass. `--timeout` can apply a per-command timeout. When `--run-id` names an active EmbrAIon execution run, the validation result is attached to that run by evidence ID.

Keep commands deterministic and repository-local where possible. Project validation commands are executable project code and run only when `embraion validation run` is explicitly invoked.

## `.embraion/agents.yaml`

This file defines project-specific agents that are projected into Codex, GitHub Copilot, and Claude Code together with the reusable Core roles.

A project agent can extend one existing non-Lead Core role:

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

Required fields:

- `id` — unique kebab-case project agent ID; it must not shadow a Core agent ID;
- `purpose` — concise project-specific responsibility;
- `access` — explicit `read-only` or `workspace-write` boundary;
- `responsibilities` — one or more project-specific responsibilities.

Optional fields:

- `title` — display title; defaults to the title-cased ID;
- `extends` — an existing non-Lead Core agent ID;
- `restrictions`, `triggers`, and `outputs` — additional project-specific contract items.

When `extends` is present, EmbrAIon inherits the Core role's responsibilities, restrictions, triggers, and outputs, then appends the project-specific items. The project agent must preserve the Core role's access level. It cannot extend `lead`, widen a read-only role into a writable role, or replace a canonical Core agent.

Without `extends`, the definition is a standalone project agent with its explicitly declared access and responsibilities.

During `embraion install` or `embraion projection diff`, these definitions are resolved from the consuming project's `.embraion/agents.yaml` and emitted as host-native files:

```text
Codex          .codex/agents/<id>.toml
GitHub Copilot .github/agents/<id>.agent.md
Claude Code    .claude/agents/<id>.md
```

Framework-only `embraion sync` remains deterministic and generates Core agents only; project agents belong to a consuming repository and are resolved during project projection.

## `.embraion/.gitignore`

The project-local ignore file protects runtime-only state:

```gitignore
state/
cache/
```

During normal operation EmbrAIon may create:

```text
.embraion/state/
.embraion/cache/
```

These are not canonical project configuration and should normally remain untracked.

## Canonical configuration vs generated host projection

The `.embraion/` files above are project-owned configuration. Host files generated by `embraion install` are projections.

Examples:

```text
.codex/...       # Codex
.github/...      # GitHub Copilot
.claude/...      # Claude Code
```

When you want to change project policy, knowledge, validation, or routing, prefer the canonical `.embraion/` file rather than editing a generated host projection to represent the same intent.

See [AI host examples](ai-hosts.md) for concrete workflows.
