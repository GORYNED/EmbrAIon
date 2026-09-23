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

> Этот файл — перевод канонического английского README. Если версии расходятся, источником истины является английская версия.

EmbrAIon — переносимая AI-First Engineering System для организации агентов, skills, workflows, маршрутизации моделей, валидации, ревью, инструментов и оркестрации проектов.

Этот репозиторий является upstream-источником истины для переиспользуемой инженерной системы. Знания и ограничения конкретного продукта должны находиться в project overlays, а не в EmbrAIon Core.

## Core

Core разделён по типам capabilities:

- **Rules** — обязательное, запрещённое или защищённое поведение.
- **Agents** — роли-должности: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher и Steward.
- **Skills** — повторяемые процедуры.
- **Workflows** — порядок выполнения и orchestration.
- **Routing** — complexity, privacy, fallback и health policy.
- **Knowledge** — общие факты, concepts и terminology.

Агенты model-neutral. Актуальные конкретные модели, effort, lifecycle, pricing и host selectors хранятся в model catalogs соответствующих adapters.

## Архитектура

```text
EmbrAIon Core
    +
Tool / provider adapters
    +
Project overlay
    =
Эффективный инженерный контекст
```

## Структура репозитория

```text
brand/         спецификация бренда и README assets
core/          vendor-neutral rules, agents, skills, workflows, routing, knowledge
adapters/      Codex, Copilot, provider и transport integrations
tools/         runtime, worktree, CLI, install, doctor, sync, validation
schemas/       machine-readable contracts
templates/     project overlay templates
docs/          архитектурная и инженерная документация
examples/      reference integrations
tests/         framework validation
localization/  переводы README
```

## Spec Kit

Spec Kit рекомендуется как дополнительная внешняя capability для substantial features, cross-cutting architecture и specification-driven работы.

Он не встроен в EmbrAIon и не заменяет Core rules, project architecture, product truth, compatibility contracts или validation evidence.

## Project overlays

Подключаемый проект хранит собственную доменную истину в своём репозитории и ссылается на зафиксированную версию EmbrAIon через `.embraion/project.yaml`.

Generic reusable behavior поднимается upstream в EmbrAIon. Product semantics, compatibility contracts, domain agents и application-specific knowledge остаются в проекте.

## Статус

EmbrAIon находится на этапе foundation. Начальные model catalogs были сформированы из валидированного routing registry и наблюдаемого model snapshot и дальше поддерживаются соответствующими adapters.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **by GORYNED**

<sub>Последнее обновление: 2026-09-23 19:04 UTC</sub>
