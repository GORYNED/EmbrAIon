# Инженерная модель

Эта страница описывает точную инженерную модель за упрощённым Getting Started flow.

## Projected guidance vs deterministic surfaces

| Surface | Значение | Кто выполняет |
| --- | --- | --- |
| Generated agents / skills | Host-native instructions и procedures | AI host |
| `embraion route` | Разрешить routing policy | EmbrAIon CLI |
| `embraion dispatch` | Построить bounded plan | EmbrAIon CLI |
| Host-native edits/search/tools | Фактическая инженерная работа | AI host |
| `embraion execute` | Bounded provider-neutral request | EmbrAIon runtime |
| `embraion validation run` | Реальные project commands + evidence | EmbrAIon CLI + project commands |
| `embraion enforcement check` | Protected-path / validation / review gate | EmbrAIon CLI |
| GitHub enforcement workflow | Merge-time CI surface | GitHub Actions |

Instruction delivery и deterministic enforcement — разные механизмы.

## Core vs project ownership

| EmbrAIon Core владеет | Проект владеет |
| --- | --- |
| generic roles и skills | architecture/domain knowledge |
| route/execution contracts | deployments и routing preferences |
| generic privacy/security mechanics | protected paths и project policy |
| validation/review mechanics | реальные validation commands |
| host projection behavior | project-specific agents |
| provider-neutral fallback/health | execution bindings и pricing sources |

## Deployment vs Routing vs Execution vs Pricing

| Concept | Вопрос | Project file |
| --- | --- | --- |
| Deployment | **Что** за reusable concrete choice существует? | `.embraion/deployments.yaml` |
| Routing | **Когда** route/role должна выбрать его? | `.embraion/routing.yaml` |
| Execution binding | **Как** его безопасно вызвать? | `.embraion/execution.yaml` |
| Pricing | **Как** интерпретировать/обновлять стоимость? | `.embraion/pricing.yaml` |

## Route classes

| Route | Значение |
| --- | --- |
| `bounded-read` | narrow read-only discovery/research |
| `bounded-write` | mechanical/tightly bounded writable work |
| `ordinary` | limited ordinary engineering |
| `substantial` | substantial engineering + standard review |
| `complex` | cross-domain, lifecycle, concurrency или difficult review |
| `critical` | exceptional protected-decision risk |

Route classes описывают работу и риск, а не постоянные model tiers.

## Host-native vs provider-neutral execution

### Host-native

AI host владеет reasoning и tools. EmbrAIon предоставляет project knowledge/policy/roles/routing и validation/review contracts.

### Provider-neutral

`embraion execute` владеет bounded external/API attempt path через explicit project bindings. Он может нормализовать failures/health и применять eligible fallback без расширения исходных request ceilings.

Routable deployment не автоматически executable: без binding runtime может вернуть `handoff-required`.

## Evidence и acceptance

Transport completion не означает project correctness. Проект может требовать deterministic validation, project-specific acceptance, independent review и human merge approval.

## Связанные страницы

- [Как работает EmbrAIon](../getting-started/how-it-works.md)
- [Настройка проекта](../configuration/index.md)
- [Model Routing](../model-routing.md)
- [Execution и провайдеры](../configuration/execution.md)
- [Pricing и стоимость](../configuration/pricing.md)
- [Валидация и evidence](../validation.md)
