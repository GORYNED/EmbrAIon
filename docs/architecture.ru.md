# Архитектура

## Слои

1. **Core** — vendor-neutral rules, agents, skills, workflows, routing и reusable knowledge.
2. **Adapters** — конкретные AI clients, transports и package projections.
3. **Tools** — deterministic runtime, learning, security, MCP inventory, worktree, validation, sync, install, doctor и CLI behavior.
4. **Project overlay** — identity consuming project, agents, source classes, compatibility rules, validation и product/domain knowledge.
5. **External capabilities** — рекомендуемые или optional companion systems и domain-specific integrations.
6. **Evidence** — deterministic tests, behavioral evals, validation records, reviews, baselines и reports.

Project overlay может делать local policy строже, но не может молча ослаблять Core hard gates. Consuming repository остаётся source of truth для product specification, architecture, compatibility contracts, validation commands, domain semantics и project-specific knowledge.

## Roles и skills

EmbrAIon намеренно разделяет **responsibility** и **procedure**.

Core использует job-like roles:

| Role | Responsibility |
| --- | --- |
| Lead | Framing задачи, delegation, integration и completion |
| Worker | Реализация bounded changes внутри explicit ownership |
| Reviewer | Независимая проверка correctness, risk и regressions |
| Architect | Анализ boundaries, dependencies и structural changes |
| Analyst | Исследование evidence и превращение его в actionable findings |
| Validator | Проверка deterministic contracts и validation evidence |
| Researcher | Сбор external/repository evidence без изменения product code |
| Steward | Поддержание framework consistency и controlled evolution |

**Agent** выражает responsibility и ownership. **Skill** описывает повторяемую инженерную procedure. Одна role может использовать несколько skills, а один skill — несколько roles.

Project-specific domain specialists принадлежат consuming repository, а не generic Core. Они объявляются в `.embraion/agents.yaml` и могут extend совместимую non-Lead Core role, сохраняя её access boundary.

Delegation принадлежит Lead. Каждая projected non-Lead Core role содержит hard restriction `do not recursively delegate`. Project agents получают то же ограничение. Это сохраняет bounded execution tree и предотвращает uncontrolled child-agent chains.

Задача состоит не только из persona:

```text
responsibility
    +
procedure
    +
project facts
    +
routing / access constraints
    +
validation and review
```

## Механизмы vs факты проекта

| EmbrAIon Core | Consuming project |
| --- | --- |
| reusable roles и skills | architecture/domain knowledge |
| route и execution contracts | concrete deployments и routing preferences |
| generic security/privacy mechanics | protected paths и project privacy policy |
| generic validation/review mechanics | реальные project validation commands |
| host projection behavior | project-specific specialists |
| provider-neutral execution/fallback/health | optional execution bindings, credential references, pricing sources |

Проект может сузить или настроить Core behavior, но не должен создавать второй generic AI framework внутри репозитория.

## Prompt flow остаётся host-native

EmbrAIon не стоит перед Codex, Copilot или Claude Code как обязательный prompt proxy.

Host получает запрос пользователя напрямую. Installed projections объясняют host reusable Core roles/skills и канонический `.embraion/` contract репозитория. Reasoning и tool use выполняет сам host.

Поэтому ordinary tasks остаются обычными natural-language requests, а изменения configuration попадают в deterministic project-owned files.

## Projected guidance vs deterministic execution

Не все surfaces EmbrAIon обладают одинаковой enforcement power.

| Surface | Nature |
| --- | --- |
| Generated agents и skills | Host-native instructions/procedures |
| Routing resolution | Deterministic framework decision |
| Dispatch plan | Deterministic bounded plan |
| Host-native AI work | Выполняется Codex/Copilot/Claude под контролями host |
| `embraion execute` | Deterministic provider-neutral execution path |
| Project validation | Реальный запуск project commands с evidence |
| Enforcement | Deterministic policy/validation/review gate |

Это различие не позволяет спутать generated instruction file с security boundary, который может обеспечить только host или executable EmbrAIon gate.

См. [Как работает EmbrAIon](getting-started/how-it-works.md).

## State и learning

Runtime state нормализуется в privacy-safe session, context, validation и run records. Повторяющиеся outcomes могут создавать learning candidates, но canonical capability promotion всегда проходит review, validation, appropriate eval coverage и explicit approval.

## Integrations

External server/tool configuration инвентаризируется отдельно от Core policy. Inventory сохраняет metadata и drift, но не secret values.

Host adapters переводят канонические concepts EmbrAIon в файлы Codex, GitHub Copilot, Claude Code или Portable bundle. Generated host files — projections, а не второй source of project policy.

## Model ownership

Core routing выбирает model-agnostic route classes. EmbrAIon не владеет глобальным model catalog.

По умолчанию execution host выбирает модель сам. Проекты могут хранить opaque host-specific model/effort/options overrides в `.embraion/routing.yaml`. Эти overrides не могут расширить Core privacy, access, ownership, validation или review policy.

## Spec Kit

Spec Kit подключается как external capability. EmbrAIon рекомендует его для substantial specification work, но не vendor'ит его skills, templates или runtime.
