# EmbrAIon

![EmbrAIon — Where sparks become AI-built products](assets/hero-dark.png)

<div class="embraion-lead" markdown>

**EmbrAIon** is a portable **AI-First Engineering System** that makes AI-assisted software development structured, reusable, reviewable, and safer to operate.

It sits around your engineering process — not inside your product runtime — and gives AI clients a consistent project contract for knowledge, roles, skills, routing, permissions, validation, review, and evidence.

</div>

## Start with what you want to do

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **I am new to EmbrAIon**

    ---

    Understand the mental model, install the launcher, and add it to a repository.

    [Start here](getting-started/what-is-embraion.md)

-   :material-source-repository:{ .lg .middle } **I have an existing repository**

    ---

    Adopt EmbrAIon conservatively without replacing host files you already own.

    [Adopt an existing repo](getting-started/existing-repository.md)

-   :material-tune-variant:{ .lg .middle } **I need to configure my project**

    ---

    Configure knowledge, policy, validation, agents, and optional model routing.

    [Configure EmbrAIon](configuration/index.md)

-   :material-shield-check:{ .lg .middle } **I want validation or CI enforcement**

    ---

    Run project validation, collect evidence, and optionally install explicit merge-time enforcement.

    [Use validation & enforcement](guides/enforcement.md)

</div>

## The shortest working path

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
embraion status
```

Use `copilot` or `claude-code` when that is your AI client.

Then continue with [Your First AI Task](getting-started/first-ai-task.md).

## The mental model

```text
Your application / library / game
              ↑
        ordinary source code
              ↑
        consuming repository
              ↑
 project knowledge + .embraion/
              ↑
          EmbrAIon Core
              ↓
 Codex / Copilot / Claude Code
              ↓
 AI-assisted engineering work
              ↓
 validation → review → evidence
```

The final product does not need an EmbrAIon runtime dependency. EmbrAIon organizes **how the project is engineered**.

## What lives in your project

`embraion init` creates a small, explicit configuration surface:

```text
.embraion/
├── .gitignore
├── project.yaml      # project identity + EmbrAIon version pin
├── knowledge.yaml    # project knowledge references
├── policy.yaml       # source classes, privacy, review, enforcement
├── routing.yaml      # optional host-specific model overrides
├── validation.yaml   # executable project validation profiles
└── agents.yaml       # project-specific agent declarations
```

The project owns these files. Generated Codex/Copilot/Claude files are projections of the canonical configuration and reusable EmbrAIon Core.

## Important defaults

- **Model selection is host-owned by default.** You do not need to configure model names.
- **Validation runs only when requested.** Put real commands in `validation.yaml` and invoke them explicitly.
- **Enforcement is opt-in.** `init` and host installation do not silently add executable CI or hooks.
- **Project updates are intentional.** Projects pin exact releases and update only when you run `embraion update`.
- **State/cache stay local.** `.embraion/state/` and `.embraion/cache/` are ignored by the project-local `.gitignore`.

## Recommended next steps

1. [What is EmbrAIon?](getting-started/what-is-embraion.md)
2. [Install EmbrAIon](getting-started/installation.md)
3. [Add it to a project](getting-started/first-project.md)
4. [Configure the project](configuration/index.md)
5. [Run your first AI task](getting-started/first-ai-task.md)
6. [Use the daily workflow](guides/daily-workflow.md)

[Start here](getting-started/what-is-embraion.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/GORYNED/EmbrAIon){ .md-button }
