<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System by GORYNED" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="localization/README.ru.md">Русский</a> ·
  <a href="localization/README.zh-CN.md">简体中文</a> ·
  <a href="localization/README.es.md">Español</a> ·
  <a href="localization/README.hi.md">हिन्दी</a>
</p>

# EmbrAIon

**AI-First Engineering System [by GORYNED](https://goryned.com)**

> Where sparks become AI-built products

EmbrAIon gives a software repository a reusable **operating model for AI-assisted engineering**.

Instead of scattering project knowledge, AI roles, model choices, protected paths, test commands, review rules, and host-specific prompt files across the repository, EmbrAIon turns them into one project contract. Codex, GitHub Copilot, Claude Code, and other integrations can then work from the same engineering rules.

EmbrAIon does **not** sit inside your application runtime and it does **not** intercept every prompt. Your Unity game, Python service, web app, or library remains a normal project. EmbrAIon organizes how humans and AI engineer it.

## Why would I use this?

AI coding works well when the task is small and the important rules fit in one conversation. It becomes harder when a real project has:

- architecture and compatibility rules the AI must not forget;
- protected or private source boundaries;
- several AI clients, agents, or models;
- different models for cheap, ordinary, complex, or critical work;
- project-specific specialists;
- required validation and independent review;
- generated host files that should not become competing sources of truth.

Without a system, those rules tend to drift between prompts, `AGENTS.md`, host settings, CI, scripts, and individual sessions.

EmbrAIon makes them explicit and reusable.

A useful mental model is:

> **EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.**

That is an analogy, not a runtime architecture. Your AI client still receives your prompt and performs the reasoning. EmbrAIon supplies the project contract around that work.

## What the experience should feel like

After EmbrAIon is installed, normal work should still start with a normal request:

> Add retry behavior when the service connection drops.

You should not need to manually select every agent, model, validation command, or policy file. The AI client can use the projected EmbrAIon roles and skills together with the repository's `.embraion/` settings.

Configuration can also be conversational:

> Configure AI routing for this repository. Use inexpensive models for bounded work, a stronger model for complex architecture, and reserve the most expensive route for genuinely critical work.

The AI client should know that the canonical place for this intent is `.embraion/routing.yaml` and, when reusable concrete choices are needed, `.embraion/deployments.yaml`. It should change the project contract there instead of duplicating the rule in arbitrary prompt files.

## Core vs project settings

EmbrAIon **Core owns reusable mechanisms**:

- generic engineering roles and reusable skills;
- routing, execution, fallback, health, security, and evidence contracts;
- validation and review mechanics;
- host projection behavior.

The **project owns project facts and preferences** under `.embraion/`:

- project identity and framework pin;
- architecture and project knowledge;
- protected paths, privacy, review, and enforcement policy;
- concrete deployments and optional routing overrides;
- project validation commands;
- project-specific agents;
- optional execution bindings and pricing configuration.

Generated Codex, Copilot, or Claude files are projections of that contract. They are not a second configuration authority.

## Quick start

Install the launcher once:

```bash
pipx install embraion
```

Add EmbrAIon to a repository:

```bash
cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
embraion status
```

Use `copilot` or `claude-code` instead of `codex` when that is the AI client you use.

`embraion init` creates the project-owned configuration surface:

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

The generated host files are projections. The `.embraion/` files remain the canonical project configuration.

## How it fits together

```text
You describe the engineering outcome
              │
              ▼
Codex / Copilot / Claude Code
              │
              ├── reads host-native EmbrAIon projections
              │
              ▼
        EmbrAIon Core
              +
     project .embraion/
              │
              ▼
roles / knowledge / routing / policy / validation
              │
              ▼
      engineering work
              │
              ▼
validation → review → evidence → human merge
```

EmbrAIon does not replace the AI host. It gives the host a durable, repository-owned engineering contract.

By default EmbrAIon does not pin a specific AI model. The selected host uses its own default or automatic choice. Optional project overrides belong only in `.embraion/routing.yaml`.

## Validation and enforcement

Projects declare real commands in `.embraion/validation.yaml` and run them explicitly:

```bash
embraion validation run affected
```

Enforcement is opt-in. When a project wants a GitHub Actions gate:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

EmbrAIon never installs that workflow silently. Repository branch rules decide whether its status check is mandatory for merge.

## Updating

Upgrade the launcher first, then intentionally update a project:

```bash
pipx upgrade embraion
cd MyProject
embraion update
embraion doctor
```

Safe configuration normalization targets the installed launcher version. Existing project-owned values are preserved, missing compatible defaults may be added, and incompatible configuration fails before mutation.

## Documentation

Start here: **[embraion.goryned.com](https://embraion.goryned.com/)**

Recommended path:

1. [Why EmbrAIon?](docs/getting-started/what-is-embraion.md)
2. [Installation](docs/getting-started/installation.md)
3. [Add EmbrAIon to a project](docs/getting-started/first-project.md)
4. [Adopt an existing repository](docs/getting-started/existing-repository.md)
5. [Run your first AI task](docs/getting-started/first-ai-task.md)
6. [Configure your project](docs/configuration/index.md)
7. [Daily workflow](docs/guides/daily-workflow.md)

Full command details live in the [CLI reference](docs/reference/cli.md).

## Examples

The repository includes executable reference projects for:

- [Minimal](examples/minimal/) — the smallest complete EmbrAIon consumer.
- [Python](examples/python/) — ordinary application code and tests with EmbrAIon layered around them.
- [Unity](examples/unity/) — a runnable Unity 6 project showing that EmbrAIon remains outside the game runtime.

CI exercises the real consuming-project lifecycle across Windows, macOS, and Linux.

## Status

EmbrAIon is pre-1.0. Patch releases are intended for compatible fixes and improvements; minor releases may evolve public framework contracts. Projects pin exact published versions so upgrades remain intentional.

## License and brand

Source code and documentation are licensed under the [MIT License](LICENSE) except where explicitly stated otherwise. The **EmbrAIon** and **GORYNED** names, logos, wordmarks, visual marks, and files under `brand/assets/` are governed separately by [TRADEMARKS.md](TRADEMARKS.md).

---

<sub>Last updated: 2026-09-27 01:20 UTC</sub>
