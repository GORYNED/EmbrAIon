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
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

The files have focused ownership:

- `project.yaml` — project identity, framework pin, and open capability metadata;
- `knowledge.yaml` — project knowledge references;
- `policy.yaml` — source classes, privacy, review, and enforcement policy;
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

## Model routing is optional

EmbrAIon is model-agnostic. If the AI client's default/automatic model choice is acceptable, configure nothing.

If explicit project routing is useful, ask the AI client to write only confirmed selectors to `.embraion/routing.yaml`. Do not weaken privacy, access, protected-source, validation, or review policy to make a model fit.

## Add project knowledge

Project-specific facts belong with the repository. For example:

```text
knowledge/
├── project.md
└── architecture.md
```

Reference them from `.embraion/knowledge.yaml`. See [Project Knowledge](../configuration/knowledge.md).

## Add real validation early

The default validation profiles are empty. Before relying on validation as evidence, configure real repository commands in `.embraion/validation.yaml`.

See [Validation Profiles](../configuration/validation.md).

## Next

- New/small repository: [Configure EmbrAIon](../configuration/index.md)
- Mature repository: [Adopt an Existing Repository](existing-repository.md)
- Ready to work: [Your First AI Task](first-ai-task.md)
