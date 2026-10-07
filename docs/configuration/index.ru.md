# Настройка EmbrAIon для проекта

После `embraion init` и установки host projection напишите:

> Настрой EmbrAIon для этого проекта.

Lead использует канонический Core skill [Project Bootstrap](bootstrap.md): изучает репозиторий, связывает существующие источники истины, сохраняет safety policy и находит реальные validation commands. Вам не нужно вручную знать каждый YAML-файл. Routing и custom agents остаются необязательными.

Для явного tuning моделей используйте полный запрос на странице Bootstrap. Ручное редактирование остаётся доступным; таблица ниже — справочник ownership.

## Карта конфигурации: вопрос → файл

| Вопрос | Канонический файл |
| --- | --- |
| Что это за проект и какую версию EmbrAIon он использует? | `project.yaml` |
| Какие факты и архитектуру AI должен знать? | `knowledge.yaml` |
| Какие пути canonical, protected, generated или external? | `policy.yaml` |
| Какие privacy/review/enforcement rules действуют? | `policy.yaml` |
| Какие конкретные execution/model choices проект переиспользует? | `deployments.yaml` |
| Нужно ли переопределять model selection host? | `routing.yaml` |
| Какие команды доказывают корректность? | `validation.yaml` |
| Нужны ли domain-specific AI specialists? | `agents.yaml` |
| Используется ли provider-neutral execution? | опциональный `execution.yaml` |
| Нужны ли проверенные pricing sources? | опциональный `pricing.yaml` |
| Какие внешние программы или возможности хоста объявлены? | опциональный `external-capabilities.yaml` |
| Какие MCP servers должна содержать host configuration проекта? | опциональный `integrations.yaml` |
| Какие изменения источников требуют проверки документа? | опциональный `knowledge-maintenance.yaml` |
| Какие ограничения структуры кода проверяются постепенно? | опциональный `organization.yaml` |
| Какая роль и политика записи у каждого источника? | опциональный `sources.yaml` |
| Какие архитектурные изменения требуют записи о решении? | опциональный `decisions.yaml` |

![Карта конфигурации проекта](../assets/diagrams/en/04-configuration-map.svg){ loading=lazy }

## Правило ownership

**EmbrAIon Core владеет переиспользуемыми механизмами.**

**Репозиторий владеет фактами и настройками проекта.**

Generated host files — это projections канонического контракта, а не второе место для поддержания project policy.

## Разговорные примеры

Можно сказать AI:

> Зарегистрируй наш architecture document как architecture source of truth.

> Пометь `vendor/**` как protected, а generated build outputs — как generated.

> Добавь integration test command в affected validation.

> Оставь model selection на host-default.

> Добавь read-only domain specialist только если существующих Core roles недостаточно.

Смысл не в том, чтобы человек запоминал YAML, а в том, чтобы для каждого типа настройки было одно корректное место.

## Проверьте изменения

```bash
embraion doctor
embraion policy show
embraion validation list
embraion status
```

Для routing:

```bash
embraion route --host codex --route-class complex --data PRIVATE
```

Для generated host files:

```bash
embraion projection diff --host codex --destination .
```

## Дальше по темам

- [Файлы проекта](project-files.md)
- [Знания проекта](knowledge.md)
- [Policy и protected paths](policy.md)
- [Настройка validation](validation.md)
- [Агенты проекта](agents.md)
- [Deployments проекта](deployments.md)
- [Model routing](../model-routing.md)
- [Execution и провайдеры](execution.md)
- [Pricing и стоимость](pricing.md)
- [Разговорная настройка](ai-hosts.md)
- [Внешние возможности](capabilities.md)
- [Организация кода](organization.md)
- [Реестр источников](sources.md)
- [Записи об архитектурных решениях](decisions.md)
- [Поддержка знаний](../guides/knowledge-maintenance.md)
