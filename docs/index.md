# EmbrAIon

![EmbrAIon — Where sparks become AI-built products](assets/hero-dark.png)

<div class="embraion-lead" markdown>

**EmbrAIon keeps all the important rules for AI-assisted engineering in one repository-owned contract — knowledge, protected paths, routing, validation, review, and evidence — instead of spreading them across prompts and AI-client settings.**

</div>

## When you need it

EmbrAIon becomes useful when:

- project rules no longer fit in one prompt;
- several AI clients should follow the same repository rules;
- protected paths and validation need real checks, not only instructions;
- architecture knowledge must survive new sessions and model changes;
- model/routing/review choices should be reusable project settings.

> **Mental model:** EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.

## Before / after

| Before | After |
| --- | --- |
| Rules live in prompts, `AGENTS.md`, host settings, CI, and people's memory | Project rules have one canonical home under `.embraion/` |
| Each AI client can drift | Shared behavior is projected into supported hosts |
| “Please run tests” is just an instruction | Validation profiles run real project commands |
| “Do not touch this path” may be only prose | Policy + validation/enforcement can reject protected-path changes |
| Model choices are repeated manually | Stable task/risk classes can map to host defaults or project overrides |

## Choose your path

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **I just want AI to follow my project rules**

    ---

    Read the one-minute overview, try the sandbox, install EmbrAIon, then give your AI client normal engineering tasks.

    [EmbrAIon in 60 Seconds](getting-started/in-60-seconds.md)

-   :material-console-line:{ .lg .middle } **I want the engineering model**

    ---

    Learn ownership, projections, routing, execution, validation, evidence, and enforcement.

    [Engineering Model Deep Dive](reference/engineering-model.md)

</div>

## Quick start

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
```

Then open the repository in your AI client and ask for the engineering outcome:

> Fix the retry flow and add regression coverage.

Use `copilot` or `claude-code` instead of `codex` when that is your host.

Not ready to touch a real repository? [Try the Five-Minute Sandbox](getting-started/playground.md).

## How it fits

![How EmbrAIon fits into your project](assets/diagrams/en/01-how-embraion-fits.svg){ loading=lazy }

!!! tip "In plain English"
    You still talk directly to Codex, Copilot, or Claude Code. EmbrAIon gives that host the repository's shared engineering contract and provides deterministic commands for things such as validation and enforcement.

## Why not just use a native instruction file?

Native instructions remain useful. EmbrAIon adds the parts that should be shared, versioned, and executable.

| Native instruction file | EmbrAIon |
| --- | --- |
| Mostly host-specific text guidance | Shared project contract projected into supported hosts |
| Easy to duplicate and drift | Canonical project-owned settings |
| Validation is separate/ad hoc | Executable validation profiles + evidence |
| No shared routing vocabulary | Stable task/risk route classes |
| Merge checks are separate | Optional protected-path / validation / review enforcement |

## Next

- [Why EmbrAIon?](getting-started/what-is-embraion.md)
- [EmbrAIon in 60 Seconds](getting-started/in-60-seconds.md)
- [Five-Minute Sandbox](getting-started/playground.md)
- [Installation](getting-started/installation.md)
- [FAQ](faq.md) — direct answers to common conceptual questions.
- [Glossary](glossary.md) — short definitions for EmbrAIon terminology.
