# Configuration

EmbrAIon is designed to be customized per repository without forking or editing the framework Core.

After `embraion init`, the consuming project owns a small configuration surface under `.embraion/`. These files describe the project, its knowledge, safety policy, model-routing preferences, validation profiles, and project-specific agent declarations. EmbrAIon Core remains reusable and version-pinned separately.

## Configuration layout

A newly initialized project has this canonical shape:

```text
.embraion/
├── .gitignore
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

Runtime state may later appear under `.embraion/state/` and `.embraion/cache/`, but those directories are intentionally ignored by the project-local `.gitignore`.

## What is project-owned

| File | Purpose |
| --- | --- |
| `project.yaml` | Framework pin, project identity, and the intentionally open `capabilities` metadata |
| `knowledge.yaml` | References to project knowledge plus optional context-selection metadata |
| `policy.yaml` | Source classes, substantial-review requirement, and default privacy class |
| `routing.yaml` | Optional host-specific model/effort/options overrides |
| `validation.yaml` | Fast, affected, full, or custom validation profiles |
| `agents.yaml` | Project-specific agent declarations |
| `.gitignore` | Keeps local EmbrAIon state/cache out of Git |

The consuming repository is the source of truth for these files. EmbrAIon Core does not overwrite them as part of ordinary host projection generation.

## Full baseline template

The following is the baseline configuration created by `embraion init`, with project-specific values shown generically.

### `.embraion/project.yaml`

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: <pinned-version>

project:
  name: <project-name>

capabilities: {}
```

### `.embraion/knowledge.yaml`

```yaml
{}
```

### `.embraion/policy.yaml`

```yaml
sources:
  canonical: []
  protected: []
  generated: []
  external: []

review:
  substantial-required: true

privacy:
  default-class: PRIVATE
```

### `.embraion/routing.yaml`

```yaml
overrides: {}
```

With this default, the selected AI host owns model selection.

### `.embraion/validation.yaml`

```yaml
profiles:
  fast: []
  affected: []
  full: []
```

### `.embraion/agents.yaml`

```yaml
agents: []
```

Add project-specific agents here when the project needs domain or workflow specialists beyond the reusable Core roles. See [Project files](project-files.md) for the full `extends` contract and host projection behavior.

### `.embraion/.gitignore`

```gitignore
state/
cache/
```

## A practical customized example

A normal project can keep the identity file small while moving project-specific behavior into the focused configuration files:

```yaml
# .embraion/project.yaml
framework:
  repository: GORYNED/EmbrAIon
  version: <pinned-version>

project:
  name: MyProject

capabilities:
  engine:
    family: ExampleEngine
```

```yaml
# .embraion/knowledge.yaml
project:
  path: knowledge/project.md
  data-class: PRIVATE
  trust: project

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

```yaml
# .embraion/policy.yaml
sources:
  canonical:
    - src/**
    - knowledge/**
  protected:
    - vendor/**
  generated:
    - build/**
  external: []

review:
  substantial-required: true

privacy:
  default-class: PRIVATE
```

```yaml
# .embraion/routing.yaml
overrides: {}
```

```yaml
# .embraion/validation.yaml
profiles:
  fast:
    - python -m unittest discover -s tests
  affected:
    - python -m unittest discover -s tests
  full:
    - python -m unittest discover -s tests
    - python -m compileall src
```

```yaml
# .embraion/agents.yaml
agents: []
```

## Recommended customization flow

1. Run `embraion init`.
2. Fill in project identity, knowledge, policy, and validation.
3. Install the projection for the AI host you use.
4. Leave `routing.yaml` on `host-default` unless you actually want explicit model routing.
5. When explicit routing is useful, ask the active AI client to inspect the models available to your account and configure only the relevant host override.
6. Verify the result with `embraion doctor`, `embraion policy show`, and `embraion route`.

Continue with [Project files](project-files.md) for the complete file-by-file contract, then see [AI host examples](ai-hosts.md) for Codex, GitHub Copilot, and Claude Code.
