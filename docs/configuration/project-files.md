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

The shortest form maps an ID directly to a file:

```yaml
project: knowledge/project.md
architecture: knowledge/architecture.md
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

Keep commands deterministic and repository-local where possible.

## `.embraion/agents.yaml`

This file declares project-specific agent IDs:

```yaml
agents:
  - domain-specialist
  - release-specialist
```

The current project-agent contract is intentionally minimal. EmbrAIon's generated built-in agent definitions still come from canonical `core/agents/`. Declaring an arbitrary ID in `agents.yaml` does not by itself generate a complete new host-native agent definition.

Use this file for explicit project declarations while keeping reusable canonical agent behavior in Core.

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
