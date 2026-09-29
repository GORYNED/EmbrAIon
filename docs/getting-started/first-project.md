# Add EmbrAIon to a Project

Start inside an existing repository or an empty project directory:

```bash
cd MyProject
embraion init
```

This creates the canonical project-owned configuration:

```text
.embraion/
├── .gitignore
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── deployments.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

The files have focused ownership:

- `project.yaml` — project identity, framework pin, and open capability metadata;
- `knowledge.yaml` — project knowledge references;
- `policy.yaml` — source classes, privacy, review, and enforcement policy;
- `deployments.yaml` — reusable project-owned model/provider choices when the project needs them;
- `routing.yaml` — optional host-specific model/effort/options overrides;
- `validation.yaml` — executable project validation profiles;
- `agents.yaml` — project-specific agent declarations;
- `.gitignore` — keeps `.embraion/state/` and `.embraion/cache/` local.

## Inspect the project

```bash
embraion status
embraion doctor
```

Resolve configuration errors before adding host projections.

## Install the AI client you use

Codex:

```bash
embraion install --host codex --destination .
```

GitHub Copilot:

```bash
embraion install --host copilot --destination .
```

Claude Code:

```bash
embraion install --host claude-code --destination .
```

Portable bundle:

```bash
embraion install --host portable --destination vendor/embraion
```

A repository may install multiple projections.

If the repository already owns host configuration, agents, or skills, use the safer incremental flow in [Adopt an Existing Repository](existing-repository.md) instead of overwriting files blindly.

## Configure the project with one request

Open the repository in your AI host and ask:

> Configure EmbrAIon for this project.

The canonical Core `project-bootstrap` skill inspects the repository first, then binds existing knowledge documents, preserves policy, and configures real validation commands. You do not need to assemble YAML manually. Core roles normally suffice: `agents: []` does not disable them. Routing can remain `overrides: {}` and host-default.

Bootstrap verifies the result and reports skips, infrastructure limitations, and ambiguity. Repeated setup preserves intentional settings and invents neither sources of truth nor commands. Then ask ordinary engineering questions. See [Project Bootstrap](../configuration/bootstrap.md).

## Next

- New/small repository: [Configure EmbrAIon](../configuration/index.md)
- Mature repository: [Adopt an Existing Repository](existing-repository.md)
- Ready to work: [Your First AI Task](first-ai-task.md)
