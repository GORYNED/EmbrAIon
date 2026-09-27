# EmbrAIon

![EmbrAIon — Where sparks become AI-built products](assets/hero-dark.png)

<div class="embraion-lead" markdown>

**One repository-owned engineering contract for AI context, safety policy, model routing, validation, and review — projected into Codex, GitHub Copilot, Claude Code, and portable integrations.**

EmbrAIon keeps project rules with the repository instead of scattering them across prompts, AI-client settings, CI scripts, and individual sessions.

</div>

## What it gives your repository

<div class="grid cards" markdown>

-   :material-source-repository:{ .lg .middle } **One project contract**

    ---

    Keep architecture knowledge, source ownership, privacy, review, routing, and validation in canonical project-owned configuration.

-   :material-swap-horizontal:{ .lg .middle } **Multiple AI hosts**

    ---

    Project the same reusable roles and skills into Codex, GitHub Copilot, Claude Code, or a host-neutral Portable bundle.

-   :material-shield-check:{ .lg .middle } **Deterministic controls**

    ---

    Combine AI guidance with executable validation, protected-path checks, review evidence, and optional merge enforcement.

-   :material-routes:{ .lg .middle } **Model-agnostic routing**

    ---

    Classify work by risk and complexity while letting the host choose models by default or applying explicit project-owned overrides.

</div>

> **Mental model:** EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.

EmbrAIon does **not** replace your AI client and does not intercept every prompt. The host still performs the conversation, reasoning, edits, searches, and tool use.

## Quick start

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
embraion status
```

Use `copilot` or `claude-code` instead of `codex` when that is the host you use.

Not ready to touch a real repository? [Try EmbrAIon in a five-minute sandbox](getting-started/playground.md).

## How it fits

![How EmbrAIon fits into your project](assets/diagrams/en/01-how-embraion-fits.svg){ loading=lazy }

The project owns its facts and preferences under `.embraion/`. EmbrAIon Core owns reusable mechanisms. Generated host files are projections of that contract, not a second configuration authority.

[See the full execution model](getting-started/how-it-works.md).

## Why not just use a native instruction file?

Native files such as repository instructions or `AGENTS.md` remain useful. EmbrAIon does not require you to abandon them; it adds a shared engineering contract and deterministic tooling around host-native instructions.

| Native instruction file | EmbrAIon project contract |
| --- | --- |
| Usually scoped to one host or instruction surface | Can project shared behavior into multiple supported hosts |
| Primarily text guidance | Guidance **plus** deterministic CLI/runtime surfaces |
| Project rules can drift between clients | Canonical project-owned settings under `.embraion/` |
| Validation is typically separate/ad hoc | Executable validation profiles with structured evidence |
| Model selection is usually host-specific | Stable route classes plus optional project overrides |
| No shared generated-file ownership model | Ownership-aware host projections and verification |
| Merge policy is separate | Optional enforcement can combine protected paths, validation, and review |

EmbrAIon is therefore not “a bigger prompt file.” It coordinates host-native instructions from a common project contract and adds the deterministic parts that plain instructions cannot provide by themselves.

[Read the detailed comparison and practical use cases](getting-started/what-is-embraion.md).

## Choose your next step

<div class="grid cards" markdown>

-   :material-help-circle-outline:{ .lg .middle } **Understand the idea**

    ---

    [Why EmbrAIon?](getting-started/what-is-embraion.md)

-   :material-flask-outline:{ .lg .middle } **Try it safely**

    ---

    [Five-minute sandbox](getting-started/playground.md)

-   :material-source-repository:{ .lg .middle } **Adopt an existing repository**

    ---

    [Existing-repository workflow](getting-started/existing-repository.md)

-   :material-tune-variant:{ .lg .middle } **Configure the project**

    ---

    [Project configuration](configuration/index.md)

</div>

[Start here](getting-started/what-is-embraion.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/GORYNED/EmbrAIon){ .md-button }
