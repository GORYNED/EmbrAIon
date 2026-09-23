# Архитектура

## Слои

1. **Core** — vendor-neutral rules, agents, skills, workflows, routing и knowledge.
2. **Adapters** — конкретные hosts, модели, providers, transports и package projections.
3. **Tools** — детерминированные runtime, learning, security, MCP inventory, worktree, validation, sync, install, doctor и CLI.
4. **Project overlay** — project-specific agents, domains, source classes, compatibility rules и product knowledge.
5. **External capabilities** — рекомендуемые или опциональные companion systems и domain-specific integrations.
6. **Evidence** — deterministic tests, behavioral evals, baselines и reports.

## Модель агентов

Core-агенты называются как роли-должности: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher и Steward.

Project-specific специалисты остаются в подключаемом проекте и не превращаются в generic Core roles.

## State и learning

Runtime state нормализуется в privacy-safe session records. Повторяющиеся результаты могут создавать learning candidates, но promotion в canonical capability всегда проходит review и approval.

## Integrations

Конфигурация внешних servers/tools инвентаризируется отдельно от Core policy. Inventory хранит metadata и drift, но никогда secret values.

## Ownership моделей

Core routing выбирает provider-neutral route classes. Adapter catalogs владеют актуальными model identities, effort, pricing, lifecycle и host selectors.

## Spec Kit

Spec Kit подключается как внешняя capability. EmbrAIon рекомендует его для substantial specification work, но не включает его skills, templates или runtime внутрь Core.
