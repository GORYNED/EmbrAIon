# EmbrAIon

![EmbrAIon — Where sparks become AI-built products](assets/hero-dark.png)

<div class="embraion-lead" markdown>

**EmbrAIon** is a portable **AI-First Engineering System** that gives a repository a reusable operating model for AI-assisted development.

It turns project knowledge, AI roles, routing, permissions, validation, review, and evidence into one repository-owned contract instead of leaving those rules scattered across prompts and AI-client configuration.

</div>

## Why EmbrAIon exists

AI coding is easy when the important context fits in one chat. Real repositories are different: they have architecture rules, private or protected sources, project-specific specialists, model choices, validation requirements, and review gates that must survive across sessions and across AI clients.

EmbrAIon makes that engineering contract explicit.

> **Mental model:** EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.

Your AI client still receives your prompt and performs the reasoning. EmbrAIon does not sit in the middle of every conversation. It gives Codex, Copilot, Claude Code, and other hosts the repository-specific rules and reusable engineering behavior they need to work consistently.

## What normal use feels like

Once the host projection is installed, ordinary work can remain ordinary:

> Add a retry action when the connection fails.

The repository already tells the AI what knowledge to use, what it may touch, which roles or specialists exist, how routing works, and which validation proves the change.

Configuration can be conversational too:

> Configure model routing for this project. Keep simple work inexpensive, use stronger reasoning for complex architecture, and reserve critical routing for exceptional risk.

The host should update the canonical `.embraion/` settings for that intent instead of creating a new parallel source of truth.

## Start with what you want to do

<div class="grid cards" markdown>

-   :material-help-circle-outline:{ .lg .middle } **I want to understand why this exists**

    ---

    See the problem EmbrAIon solves, what it owns, and what remains project-owned.

    [Why EmbrAIon?](getting-started/what-is-embraion.md)

-   :material-source-repository:{ .lg .middle } **I have an existing repository**

    ---

    Adopt EmbrAIon conservatively without replacing host files you already own.

    [Adopt an existing repo](getting-started/existing-repository.md)

-   :material-tune-variant:{ .lg .middle } **I need to configure my project**

    ---

    Configure knowledge, policy, validation, agents, deployments, and optional model routing.

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

## How the pieces fit

```text
Human intent
    │
    ▼
AI client
    │
    ├── host-native projections
    ▼
EmbrAIon Core ───── reusable mechanisms
    +
.embraion/ ───────── project facts and settings
    │
    ▼
engineering work
    │
    ▼
validation → review → evidence → human merge
```

EmbrAIon does **not** run inside the finished application. It is used while the repository is being engineered.

## Core owns mechanisms; the project owns facts

EmbrAIon Core owns reusable roles, skills, routing/execution mechanics, security contracts, validation/review behavior, and projection rules.

The consuming repository owns the settings that make those mechanisms correct for this project:

```text
.embraion/
├── .gitignore
├── project.yaml      # identity + exact EmbrAIon pin
├── knowledge.yaml    # architecture/domain knowledge references
├── policy.yaml       # source classes, privacy, review, enforcement
├── deployments.yaml  # reusable concrete execution choices
├── routing.yaml      # optional host/model routing overrides
├── validation.yaml   # commands that prove changes work
└── agents.yaml       # project-specific specialists
```

Optional execution/pricing configuration can be added by projects that use EmbrAIon's provider-neutral execution runtime.

Generated Codex/Copilot/Claude files are projections of the canonical contract, not a second place to maintain the same policy.

## Important defaults

- **Model selection is host-owned by default.** You do not need to configure model names.
- **Normal prompts stay normal.** You do not need to mention EmbrAIon in every task once the host projection is installed.
- **Configuration can be conversational.** The host can update the appropriate `.embraion/` file from natural-language intent.
- **Validation runs only when requested.** Put real commands in `validation.yaml` and invoke them explicitly.
- **Enforcement is opt-in.** `init` and host installation do not silently add executable CI or hooks.
- **Project updates are intentional.** Projects pin exact releases and update only when you run `embraion update`.
- **State/cache stay local.** `.embraion/state/` and `.embraion/cache/` are ignored by the project-local `.gitignore`.

## Recommended next steps

1. [Why EmbrAIon?](getting-started/what-is-embraion.md)
2. [Install EmbrAIon](getting-started/installation.md)
3. [Add it to a project](getting-started/first-project.md)
4. [Configure the project](configuration/index.md)
5. [Run your first AI task](getting-started/first-ai-task.md)
6. [Use the daily workflow](guides/daily-workflow.md)

[Start here](getting-started/what-is-embraion.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/GORYNED/EmbrAIon){ .md-button }
