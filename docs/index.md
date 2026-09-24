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

    See how EmbrAIon fits into a project, install the launcher, and add it to a repository.

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

## How EmbrAIon fits into your project

```text
Installed EmbrAIon
Core + CLI + schemas + tools
          │
          │ combines with project-specific configuration
          ▼
Your repository
application code + knowledge + .embraion/
          │
          │ projects engineering instructions into
          ▼
Codex / Copilot / Claude Code
          │
          ▼
AI works on your repository
          │
          ▼
Validation → Review → Evidence
```

EmbrAIon does **not** sit between your application and its runtime. It is used while the repository is being engineered. Your finished application, library, or game remains an ordinary product.

## What lives where

```text
INSTALLED EMBRAION                 YOUR REPOSITORY
------------------                 ------------------------------
Core roles and skills              application source code
CLI                                tests and project files
schemas and tools                  knowledge/
                                   .embraion/       canonical config
                                   .codex/          generated for Codex
                                   .github/         Copilot / optional CI
                                   .claude/         generated for Claude Code
```

EmbrAIon reads the project-owned `.embraion/` configuration and project knowledge, combines them with the reusable Core, and generates the host-specific files your AI client understands.

`embraion init` creates the canonical project configuration:

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
