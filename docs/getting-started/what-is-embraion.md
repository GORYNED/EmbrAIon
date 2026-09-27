# Why EmbrAIon?

EmbrAIon is an **AI-First Engineering System** for software repositories.

Its purpose is not to make an AI model smarter. Its purpose is to make AI-assisted engineering **repeatable, project-aware, reviewable, and portable across sessions and AI clients**.

## The problem it solves

A useful AI coding session quickly accumulates rules:

- where architecture truth lives;
- which files are protected or generated;
- what may leave the repository;
- which agent or specialist should own a concern;
- which model or provider is appropriate for a class of work;
- which tests are required;
- whether independent review is mandatory;
- what evidence should exist before a human merges the change.

Without a framework, those rules tend to end up in several places at once: prompts, `AGENTS.md`, host-specific instruction files, model settings, shell scripts, CI, and a developer's memory.

That works until the project grows, another AI client is introduced, the available models change, or a fresh session does not know the assumptions from the previous one.

EmbrAIon gives the repository one durable contract for those concerns.

## Why not just use `AGENTS.md` or host-native instructions?

You can — and EmbrAIon can coexist with them.

The difference is that an instruction file is mainly **guidance for one host surface**, while EmbrAIon also provides repository-owned configuration and deterministic engineering tools.

| Concern | Native instructions | EmbrAIon |
| --- | --- | --- |
| Tell an AI how to behave | Yes | Yes, through generated host projections |
| Share the same contract across supported hosts | Manual duplication is common | Canonical Core + project settings are projected per host |
| Select project knowledge deterministically | Usually host-specific | Project knowledge registry + context selection |
| Classify canonical/protected/generated/external sources | Usually prose conventions | Explicit project policy |
| Define reusable task/risk routing | Usually host-specific | Stable model-agnostic route classes |
| Run project validation | External to the instruction file | Executable validation profiles |
| Record review/validation evidence | External/ad hoc | Structured run and validation evidence |
| Enforce protected-path/validation/review gates | Not by text alone | Optional deterministic enforcement |

The host-native file is still useful as a delivery surface. EmbrAIon makes it a **projection of a larger engineering contract** instead of the only place the contract exists.

## The simplest mental model

> **EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.**

This is an analogy. EmbrAIon is not literally an operating system and it does not intercept every prompt.

The important separation is:

- **EmbrAIon Core owns reusable mechanisms** that should work across projects.
- **The repository owns project facts and preferences** in `.embraion/`.
- **The AI host owns the actual conversation, reasoning, and host capabilities.**

## Practical use cases

### Protect sensitive or fragile source paths

Suppose a Unity repository treats vendor SDK files or selected metadata as protected.

The project can classify those paths in `.embraion/policy.yaml`. Host projections tell the AI not to mutate them, and deterministic enforcement can reject a delivery/merge when a protected path was changed.

This is intentionally precise: EmbrAIon does **not** claim that a text projection can physically prevent every host-native write. Hard blocking comes from the host's own controls or from executable EmbrAIon validation/enforcement surfaces.

### Keep a technology decision consistent across AI hosts

Suppose a project has standardized on Unity UI Toolkit and does not want new uGUI code.

A robust contract uses more than a prompt:

```text
knowledge
  → records UI Toolkit as project architecture / source of truth

host projections
  → deliver that guidance to Codex/Copilot/Claude

validation
  → detects forbidden legacy APIs or project-specific violations

enforcement
  → can require that validation before merge
```

Knowledge explains the rule; validation proves the change satisfies it. This distinction prevents project guidance from being mistaken for a hard gate.

### Keep model strategy out of ad hoc prompts

A project can classify work as `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, or `critical`, then leave model selection to the host or define project-owned deployment/routing overrides.

The rule survives new sessions and does not require every developer to remember which model to pick for every task.

### Move between AI clients without rewriting the project contract

The same repository can project EmbrAIon roles/skills into Codex, GitHub Copilot, and Claude Code. Host-specific files differ, but project knowledge, policy, validation, and routing remain canonical under `.embraion/`.

## What EmbrAIon Core owns

Reusable mechanisms include:

- generic engineering roles such as Lead, Architect, Reviewer, Validator, and Worker;
- reusable skills and workflow procedures;
- project-contract schemas;
- model-agnostic route classes;
- host projections;
- generic validation, review, security, worktree, evidence, and enforcement mechanics;
- provider-neutral execution, failure/fallback, health, and cost contracts where a project opts into them.

These belong in Core because another repository should not have to reinvent them.

## What the project owns

The consuming repository knows facts that Core cannot know:

- its architecture and source-of-truth documents;
- protected, generated, canonical, and external paths;
- default privacy and review policy;
- which concrete deployments/models/providers it wants to reuse;
- optional routing preferences;
- validation commands that actually prove this project works;
- domain-specific agents or specialists;
- optional execution bindings, credential references, and pricing sources.

Those belong to the repository's `.embraion/` configuration.

The project can make policy stricter, but it should not reimplement generic EmbrAIon mechanisms just to customize project behavior.

## What happens when you send a normal prompt

Suppose you write:

> Fix the reconnect flow when a network operation fails.

EmbrAIon does not receive that message first and forward it to Codex or Copilot.

Instead, the AI client is already operating inside a repository that contains generated EmbrAIon projections. Those projections tell the host where the canonical project contract lives and which reusable roles/skills are available.

![How EmbrAIon fits into your project](../assets/diagrams/en/01-how-embraion-fits.svg){ loading=lazy }

The host still performs the reasoning and code changes. EmbrAIon supplies the engineering contract.

## What configuration feels like

You can edit YAML directly, but that is not the intended requirement.

A normal user can tell the AI already working in the repository:

> Configure routing for this project. Use inexpensive models for bounded work, stronger reasoning for complex architecture, and reserve the critical route for exceptional risk.

The AI should map that intent to the canonical project files rather than duplicate the rule in arbitrary Markdown or generated host files.

Likewise:

> Mark the vendor SDK as protected.

maps to project policy, and:

> Add the repository's integration tests to affected validation.

maps to project validation.

The point is not that the user must memorize the files. The point is that **the AI knows where the source of truth belongs**.

## Why routing is model-agnostic

Model names, subscription access, and host capabilities change faster than project architecture.

EmbrAIon therefore defines stable route classes such as `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, and `critical`.

By default the host chooses its own model. A project may explicitly map those classes to known deployments, but the reusable framework does not need a release every time a host introduces a new model.

## What EmbrAIon is not

EmbrAIon is **not**:

- an application runtime or SDK dependency;
- a replacement for Codex, GitHub Copilot, or Claude Code;
- a proxy that must receive every user prompt;
- a global catalog of current AI models;
- a substitute for project architecture, tests, or product specifications;
- a claim that text instructions alone can enforce filesystem or security boundaries;
- a system that silently installs hooks or CI into every repository.

## Common questions

### Do I have to mention EmbrAIon in every prompt?

No. Once the host projection is installed, ordinary engineering should feel ordinary. Mention EmbrAIon explicitly when you want to configure or inspect the engineering system itself.

### Does EmbrAIon run inside my finished application?

No. It is used while engineering the repository.

### Do I have to edit YAML manually?

No. You can ask the AI client already working in the repository to configure EmbrAIon.

### Can I use more than one AI client?

Yes. Install each host projection you want the repository to support.

### Does EmbrAIon automatically block unsafe merges?

No. Project validation and enforcement are explicit. Repository branch rules still decide whether an installed status check is mandatory for merge.

### Is a specific model required?

No. Core is intentionally independent of current model names.

## Next

- [How EmbrAIon works](how-it-works.md)
- [Try the five-minute sandbox](playground.md)
- [Install EmbrAIon](installation.md)
