# EmbrAIon

![EmbrAIon — Where sparks become AI-built products](assets/hero-dark.png)

<div class="embraion-lead" markdown>

**EmbrAIon** is a portable **AI-First Engineering System** for making AI-assisted software development structured, reusable, reviewable, and trustworthy.

It does not replace your application runtime. It sits around the engineering process: roles, skills, project knowledge, routing, permissions, validation, and host-specific projections.

</div>

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **Start in minutes**

    ---

    Install one launcher, initialize a project, and install the host projection you use.

    [Get started](getting-started/installation.md)

-   :material-brain:{ .lg .middle } **One canonical Core**

    ---

    Keep reusable engineering policy upstream while project-specific truth stays with each consuming repository.

    [Understand the model](concepts/index.md)

-   :material-connection:{ .lg .middle } **Multiple AI hosts**

    ---

    Project the same Core into Codex, GitHub Copilot, Claude Code, or a host-neutral Portable bundle.

    [Explore hosts](hosts/index.md)

-   :material-check-decagram-outline:{ .lg .middle } **Evidence, not assumptions**

    ---

    Deterministic validation, behavioral evals, security checks, reference E2E, and release gates make changes observable.

    [See validation](validation.md)

</div>

## The basic idea

A software project keeps its normal source code and runtime:

```text
Application / Library / Game
          ↑
      your code
```

EmbrAIon adds an engineering layer around that repository:

```text
                 EmbrAIon Core
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
      Codex        Copilot      Claude Code
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ↓
               Consuming project
                      │
                      ↓
                Product runtime
```

The final application does not need an EmbrAIon runtime dependency. EmbrAIon is used to organize how humans and AI agents engineer the project.

## Quick start

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
embraion status
```

The project now has a pinned EmbrAIon version plus a generated host projection.

## What EmbrAIon owns

| Area | Purpose |
| --- | --- |
| Core | Canonical reusable rules, roles, skills, workflows, routing, and knowledge |
| Project overlay | Project identity, version pin, domain knowledge, local capabilities |
| Adapters | Codex, Copilot, Claude Code, Portable, and provider-specific facts |
| Tools | Validation, security, worktrees, sessions, learning, evals, install/sync |
| Evidence | Unit/integration tests, reference E2E, behavioral evals, release gates |

## See it in a real project

The repository ships with executable reference projects:

- [Minimal](examples/minimal.md) — the smallest complete EmbrAIon consumer.
- [Python](examples/python.md) — ordinary application code and tests wrapped by EmbrAIon.
- [Unity](examples/unity.md) — a runnable Unity 6 example showing that EmbrAIon lives around the project, not inside the game runtime.

## Status

EmbrAIon is pre-1.0. Patch releases are intended to remain migration-free; minor releases may evolve public framework contracts while release notes and project pinning preserve intentional upgrades.

[Start with installation](getting-started/installation.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/GORYNED/EmbrAIon){ .md-button }
