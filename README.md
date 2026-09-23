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

## Core model

The canonical Core is organized by capability type:

- **Rules** — required, prohibited, or protected behavior.
- **Agents** — job-like roles: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward.
- **Skills** — discoverable procedures loaded only when relevant.
- **Workflows** — ordered orchestration across roles, skills, validation, review, and learning.
- **Routing** — access, complexity, privacy, fallback, and health policy.
- **Knowledge** — shared facts, concepts, and terminology.

`core/catalog.yaml` indexes capabilities and their triggers so an agent can load relevant context instead of the entire framework.

## Operational layers

EmbrAIon also defines reusable operational infrastructure:

- **Runtime** — normalized task/session state and bounded execution coordination.
- **Learning** — repeated outcome patterns become reviewed improvement candidates, never automatic Core mutations.
- **Security** — deterministic scanning of permissions, credentials, routes, integrations, and generated configuration.
- **MCP inventory** — normalized external server state and drift without persisting secret values.
- **Worktrees** — lifecycle-managed isolated writable workspaces with fail-closed cleanup and salvage.
- **Evals** — behavioral cases, baselines, and comparison reports.

## Repository layout

```text
brand/         Brand specification and README-facing assets
core/          Canonical rules, agents, skills, workflows, routing, knowledge
adapters/      Portable package, host, provider, and transport integrations
tools/         Runtime, learning, security, MCP, worktree, validation, sync, install
schemas/       Machine-readable contracts
templates/     Project overlay templates
docs/          Architecture and engineering documentation
examples/      Reference integrations
tests/         Deterministic framework tests
evals/         Behavioral cases, baselines, graders, and reports
localization/  README translations
```

## Documentation

Full documentation: [docs/](docs/README.md).

## Skills

Skills live in individual directories with a `SKILL.md` entry point. Current generic skills cover planning, implementation, research, review, validation, debugging, and final verification.

## Recommended companion: Spec Kit

Spec Kit is a recommended external companion for substantial features, cross-cutting architecture, and specification-driven work. It remains independent from EmbrAIon and does not replace Core rules, project truth, compatibility contracts, or validation evidence.

## Project overlays

A consuming repository keeps product/domain-specific agents, knowledge, compatibility constraints, and stricter local policy in its project overlay.

## Status

EmbrAIon is in active framework foundation development.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **by GORYNED**

<sub>Last updated: 2026-09-23 19:58 UTC</sub>
