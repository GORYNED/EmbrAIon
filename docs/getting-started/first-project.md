# Your First Project

Start inside an existing repository or an empty project directory.

```bash
cd MyProject
embraion init
```

This creates:

```text
.embraion/
└── project.yaml
```

The manifest records the current EmbrAIon version and project identity.

## Inspect the project

```bash
embraion status
embraion doctor
```

`status` explains the launcher, project pin, resolved runtime, cache, and detected host projections.

`doctor` checks framework health and, when a project is detected, project-level diagnostics.

## Install a host projection

For Codex:

```bash
embraion install --host codex --destination .
```

Other supported projections:

```bash
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
embraion install --host portable --destination vendor/embraion
```

Generated host files are projections. Canonical reusable policy remains in EmbrAIon Core.

## Add project knowledge

Project-specific facts belong with the consuming project rather than in reusable Core.

A common layout is:

```text
knowledge/
├── project.md
└── architecture.md
```

Reference these files from `.embraion/project.yaml`:

```yaml
knowledge:
  project: knowledge/project.md
  architecture: knowledge/architecture.md
```

See [Project knowledge](../concepts/knowledge.md) and [Project overlay](../project-overlay.md).
