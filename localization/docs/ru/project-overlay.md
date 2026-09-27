# Project Overlay: настройки проекта

`.embraion/` — канонический проектный слой EmbrAIon.

**Core владеет механизмами. Проект владеет фактами и предпочтениями.**

## Основные файлы

```text
.embraion/
├── project.yaml       # identity + точный pin EmbrAIon
├── knowledge.yaml     # ссылки на архитектуру и project truth
├── policy.yaml        # protected/generated/external, privacy, review
├── deployments.yaml   # переиспользуемые конкретные model/provider choices
├── routing.yaml       # когда использовать deployment/model override
├── validation.yaml    # реальные команды проверки проекта
└── agents.yaml        # project-specific специалисты
```

Опционально для provider-neutral runtime:

```text
execution.yaml         # как безопасно вызвать deployment
pricing.yaml           # откуда брать цены и как их интерпретировать
pricing.snapshot.json  # валидированный локальный snapshot
usage-evidence/        # evidence семантики usage, если требуется
```

## Четыре runtime-понятия

| Понятие | Вопрос |
| --- | --- |
| Deployment | **Что** можно использовать? |
| Routing | **Когда** это выбирать? |
| Execution | **Как** это физически вызвать? |
| Pricing | **Как** определить стоимость? |

Например:

```text
deployment: analysis-api
routing: substantial → analysis-api
execution: analysis-api → adapter + selector + credentialRef
pricing: analysis-api → official source + SKU → snapshot
```

## Generated projections

Файлы вроде:

```text
.codex/...
.github/agents/...
.github/skills/...
.claude/...
```

— это представления канонического контракта для конкретного host.

Их не следует использовать как второй source of truth. Если меняется policy/routing/agents проекта, меняйте `.embraion/`, затем проверяйте/обновляйте projection.

## Что не надо класть в Project Overlay

Не копируйте в проект generic-механику EmbrAIon:

- общий fallback engine;
- generic health/failure taxonomy;
- определения стандартных Core roles;
- generic validation engine;
- generic projection logic.

Проект может **настроить** механизм, но не должен создавать рядом второй framework.
