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

EmbrAIon is a portable engineering layer for teams that use AI to build software. It gives Codex, GitHub Copilot, Claude Code, and other integrations a consistent project contract: roles, reusable skills, project knowledge, routing, permissions, validation, review, security, and evidence.

EmbrAIon does **not** sit inside your application runtime. Your Unity game, Python service, web app, or library remains a normal project. EmbrAIon organizes how humans and AI engineer it.

## Why use it?

- **One reusable engineering system** across different repositories and technology stacks.
- **Project-owned configuration** under `.embraion/` instead of hidden framework assumptions.
- **Native AI-client projections** for Codex, GitHub Copilot, Claude Code, and a Portable bundle.
- **Model-agnostic routing**: the AI client owns model availability unless your project explicitly overrides it.
- **Executable validation profiles** with structured evidence.
- **Project-specific agents** without copying project semantics into reusable Core.
- **Fail-closed safety boundaries** for privacy, protected paths, configuration, review, and enforcement.
- **Explicit automation**: EmbrAIon does not silently install executable hooks or CI gates.

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
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

The generated host files are projections. The `.embraion/` files remain the canonical project configuration.

## How it fits together

```text
Your repository
     │
     ├── .embraion/ configuration + project knowledge
     │
EmbrAIon Core
     │
     ├── roles / skills / workflows / safety policy
     │
     ▼
Codex / Copilot / Claude Code / Portable
     │
     ▼
AI-assisted engineering work
     │
     ▼
validation → review → evidence → human merge
```

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

Start here: **[goryned.github.io/EmbrAIon](https://goryned.github.io/EmbrAIon/)**

Recommended path:

1. [What is EmbrAIon?](docs/getting-started/what-is-embraion.md)
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

<sub>Last updated: 2026-09-24 18:49 UTC</sub>
