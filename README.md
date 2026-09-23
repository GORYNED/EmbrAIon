<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System by GORYNED" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="localization/README.ru.md">Русский</a> ·
  <a href="localization/README.zh-CN.md">简体中文</a>
</p>

# EmbrAIon

**AI-First Engineering System by GORYNED**

> Where sparks become AI-built products

EmbrAIon is a portable AI-First Engineering System for structuring agents, skills, workflows, model routing, validation, review, tooling, and project orchestration.

The repository is the upstream source of truth for the reusable engineering system. Product-specific knowledge and constraints belong in project overlays rather than in EmbrAIon Core.

## Core model

The canonical Core is organized by capability type:

- **Rules** — required, prohibited, or protected behavior.
- **Agents** — job-like roles: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward.
- **Skills** — repeatable task procedures used by those roles.
- **Workflows** — ordered orchestration across roles, skills, validation, and review.
- **Routing** — complexity, privacy, fallback, and health policy.
- **Knowledge** — shared facts, concepts, and terminology.

Agent roles are model-neutral. Concrete Codex, Copilot, and provider model identities live in their adapter catalogs.

## Architecture

EmbrAIon separates reusable engineering policy from tool-specific integrations and project-specific context:

```text
EmbrAIon Core
    +
Tool / provider adapters
    +
Project overlay
    =
Effective engineering context
```

The canonical capability taxonomy is:

- **Rules** — required, prohibited, or protected behavior.
- **Agents** — responsibilities and ownership.
- **Skills** — repeatable task procedures.
- **Workflows** — ordered execution sequences.
- **Routing** — model, provider, effort, and execution selection.
- **Tools** — deterministic operations.
- **Adapters** — integrations with Codex, Copilot, and providers.
- **Knowledge** — facts and architecture, not commands.

## Repository layout

```text
brand/         Brand specification and README-facing assets
core/          Vendor-neutral rules, agents, skills, workflows, routing, knowledge
adapters/      Codex, Copilot, provider, and transport integrations
tools/         Runtime, worktree, CLI, installation, diagnostics, sync, validation
schemas/       Machine-readable framework and project contracts
templates/     Bootstrap templates for project overlays
docs/          Architecture and engineering documentation
examples/      Reference integrations
tests/         Framework validation
localization/  README translations
```

## Recommended companion: Spec Kit

[Spec Kit](https://github.com/github/spec-kit) is a recommended external companion for substantial features, cross-cutting architecture, and specification-driven work.

It is not bundled into EmbrAIon and never replaces Core rules, project architecture, product truth, compatibility contracts, or validation evidence.

## Project overlays

A consuming repository keeps its own domain truth and references a pinned EmbrAIon version through `.embraion/project.yaml`.

Generic reusable engineering behavior belongs upstream in EmbrAIon. Product semantics, compatibility contracts, domain agents, and application-specific knowledge remain in the consuming repository.

## Status

EmbrAIon is in active framework foundation development. Initial model catalogs were bootstrapped from a validated routing registry and observed model snapshot and are maintained by their owning adapters.

## Brand

Canonical brand copy and usage rules live under [`brand/`](brand/README.md). Figma is the visual design workspace; Git is the canonical source for versioned brand text and approved README-facing assets.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **by GORYNED**

<sub>Last updated: 2026-09-23 19:04 UTC</sub>
