# Агенты проекта

Core уже предоставляет переиспользуемые roles: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher и Steward.

Используйте `.embraion/agents.yaml` только если репозиторию нужен **project-specific specialist** сверх generic roles.

Пустой `agents: []` не добавляет project specialists, но не отключает Core roles или Lead orchestration. Пользователь может просить обычный инженерный результат без названий ролей и отдельной просьбы о delegation.

Lead выбирает минимальный полезный набор ролей по назначению: Analyst уточняет requirements, Architect решает architecture и boundaries, Researcher проверяет неизвестные факты, Worker выполняет bounded implementation, Validator собирает свежие проверки, Reviewer независимо оценивает существенную реализацию, Steward отвечает за compatibility и persistence. Lead выполняет тривиальную работу напрямую и сам делегирует задания, когда специалисты улучшают качество, ownership, evidence или safe parallelism.

Задание содержит bounded intent, owned paths или read-only scope, contracts, dependencies, acceptance criteria и ожидаемые evidence. Read-only discovery и независимые изменения можно выполнять параллельно; общие файлы, shared contracts и зависимая работа требуют последовательности или явной isolation. Существенная реализация получает независимый read-only review, когда Core или более строгая project policy этого требует. Lead объединяет результаты, разрешает findings, обновляет evidence после fixes и сохраняет окончательное право приёмки. Канонические responsibilities находятся в [Core Lead role](https://github.com/GORYNED/EmbrAIon/blob/main/core/agents/lead.yaml).

Role, access, route class, execution host и model choice независимы. Lead классифицирует конкретное задание и запрашивает project routing перед native spawn; названия ролей не задают model tiers. См. [Маршрутизация](../model-routing.md).

## Пример

```yaml
agents:
  - id: domain-specialist
    title: Domain Specialist
    extends: reviewer
    purpose: Review project-specific domain behavior.
    access: read-only
    responsibilities:
      - focus review on project-specific domain contracts
    restrictions:
      - do not modify project files
    triggers:
      - domain-focused review
    outputs:
      - domain review findings
```

## Обязательные поля

- `id` — уникальный kebab-case project agent ID;
- `purpose` — краткая project-specific responsibility;
- `access` — `read-only` или `workspace-write`;
- `responsibilities` — одна или больше project-specific responsibilities.

## Опциональное наследование

Project agent может `extend` существующую non-Lead Core role.

EmbrAIon добавляет project-specific responsibilities/restrictions/triggers/outputs, но сохраняет inherited access boundary.

Project agent не может:

- shadow Core agent ID;
- extend Core `lead`;
- расширить inherited read-only role до writable access.

## Host projection

При установке проекта project agents генерируются в native host files:

```text
Codex          .codex/agents/<id>.toml
GitHub Copilot .github/agents/<id>.agent.md
Claude Code    .claude/agents/<id>.md
```

`embraion sync` без consuming project остаётся Core-only и не придумывает project specialists.

В Codex component `config` также проецирует Lead orchestration в корневой `developer_instructions`, а `agents` предоставляет specialist files. Generated Codex role files не содержат model/effort, чтобы native spawn применял resolved assignment choice. Host-default задания используют Codex defaults или inheritance. Trust, permissions, инструкции более высокого приоритета и host capabilities определяют исполнение guidance; static files не гарантируют delegation и не заменяют исполняемые evidence gates. Merge ownership и host limits описаны в [Codex](../hosts/codex.md).

Codex, Copilot, Claude Code и Portable projections также содержат canonical `orchestration` skill с generated Core Lead contract. Общий guidance передаётся через native skill surfaces; загрузку skill выбирает каждый host.

## Preview перед записью

```bash
embraion projection diff --host codex --destination . --component agents
```

Затем установите намеренно:

```bash
embraion install --host codex --destination . --component agents
```

Полный список полей — в [Файлах конфигурации проекта](project-files.md).
