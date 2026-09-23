<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System от GORYNED" width="100%">
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <strong>Русский</strong> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

# EmbrAIon

**AI-First Engineering System от GORYNED**

> Where sparks become AI-built products

> Это перевод канонического английского README. Если версии расходятся, источником истины является английская версия.

EmbrAIon — переносимая AI-First Engineering System для организации agents, skills, workflows, model routing, validation, review, tooling и project orchestration.

## Core

Core разделён по типам capabilities:

- **Rules** — обязательное, запрещённое или защищённое поведение.
- **Agents** — роли-должности: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher и Steward.
- **Skills** — процедуры, которые загружаются только когда они нужны.
- **Workflows** — orchestration работы, review и learning.
- **Routing** — access, complexity, privacy, fallback и health.
- **Knowledge** — общие concepts и terminology.

`core/catalog.yaml` определяет, какие capabilities действительно нужны конкретной задаче.

## Operational layers

- **Runtime** — единый privacy-safe session/task state.
- **Learning** — повторяющиеся паттерны превращаются в reviewed candidates, но не меняют Core автоматически.
- **Security** — deterministic scan permissions, credentials, routes, integrations и generated configuration.
- **MCP inventory** — единый inventory серверов и drift без хранения secret values.
- **Worktrees** — lifecycle isolated workspaces, safe cleanup и salvage.
- **Evals** — behavioral cases, baselines и comparison reports.

## Spec Kit

Spec Kit рекомендуется как независимая дополнительная capability для substantial specification-driven работы. Он не заменяет Core rules, project truth, compatibility contracts или validation evidence.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **by GORYNED**

<sub>Последнее обновление: 2026-09-23 19:34 UTC</sub>
