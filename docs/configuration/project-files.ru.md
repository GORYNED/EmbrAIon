# Файлы конфигурации проекта

Эта страница описывает каноническую project-owned конфигурацию в `.embraion/`.

Полезное правило: **факты и предпочтения проекта хранятся здесь; переиспользуемые инженерные механизмы остаются в EmbrAIon Core.** Generated host files должны проецировать этот контракт, а не становиться вторым местом его поддержки.

Большинство файлов создаёт `embraion init`. Проекты с provider-neutral execution или pricing могут добавить optional runtime configuration.

## `.embraion/project.yaml`

Стабильный файл identity проекта и framework pin.

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: <pinned-version>

project:
  name: MyProject

capabilities: {}
```

### `framework`

`framework.repository` идентифицирует upstream EmbrAIon. `framework.version` фиксирует проект на точной release. Обычные CLI commands разрешают эту версию и могут использовать isolated cached runtime, даже если глобальный launcher новее.

### `project`

`project.name` — identity проекта в project overlay.

### `capabilities`

`capabilities` — открытые project metadata, например engine, language family или integration surface.

```yaml
capabilities:
  engine:
    family: ExampleEngine
    language: ExampleLanguage
```

На текущем уровне contract EmbrAIon не использует arbitrary `capabilities` для model selection или обхода policy.

## `.embraion/knowledge.yaml`

Указывает EmbrAIon на project-owned knowledge.

Новые проекты содержат canonical Project Contract Slots:

```yaml
slots:
  constitution:
  architecture:
  source-authority:
  compatibility:
  persistence:
  engineering-workflow:
  specification:
```

Проект связывает только те slots, которыми реально владеет:

```yaml
slots:
  architecture: docs/architecture.md
  source-authority: docs/references/project-sources.md
  persistence:
    path: docs/persistence.md
    data-class: PRIVATE
```

Slot names framework-owned; referenced content project-owned. Unbound slots остаются null.

Ordinary custom knowledge поддерживается рядом со slots:

```yaml
product: knowledge/project.md
domain-video: knowledge/video.md
```

Structured form:

```yaml
architecture:
  path: knowledge/architecture.md
  data-class: PRIVATE
  trust: project
  roles:
    - architect
    - lead
  triggers:
    - architecture
```

Поддерживаемые поля: `path`, `data-class`, `trust`, `roles`, `triggers`.

Knowledge files остаются обычными файлами репозитория; YAML хранит references и selection metadata.

## `.embraion/policy.yaml`

Владеет safety и source classification policy проекта.

```yaml
sources:
  canonical:
    - src/**
  protected:
    - vendor/**
  generated:
    - build/**
  external:
    - external/**

review:
  substantial-required: true

privacy:
  default-class: PRIVATE

enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

### `sources`

- `canonical` — project-owned source of truth;
- `protected` — paths, которые ordinary writable work не должна менять;
- `generated` — generated artifacts;
- `external` — externally sourced material.

### `review`

`substantial-required: true` требует review evidence для substantial work там, где это предусмотрено execution contract.

### `privacy`

`default-class` задаёт default data class: `PUBLIC`, `PRIVATE` или `CONFIDENTIAL`. Model selection не расширяет policy boundaries.

### `enforcement`

По умолчанию выключен. Установка CI surface выполняется явно:

```bash
embraion enforcement install   --surface github-actions   --validation-profile affected   --require-review
```

Команда создаёт `.github/workflows/embraion-enforcement.yml` и включает project gate. Отличающийся существующий workflow не перезаписывается без `--force`.

## `.embraion/deployments.yaml`

Reusable project-owned execution deployments без framework-owned model catalog:

```yaml
providers: {}
deployments: {}
```

Deployment именует concrete host/model choice и может содержать provider identity, effort, billing metadata, capabilities, options и non-secret metadata. Routes/roles ссылаются на deployment id из `.embraion/routing.yaml`.

## `.embraion/routing.yaml`

Содержит optional model-selection overrides для AI hosts.

Default:

```yaml
overrides: {}
```

Это означает `host-default`: активный AI client выбирает default/automatic model.

Route override:

```yaml
overrides:
  codex:
    routes:
      complex:
        model: "<selector reported by the host>"
        effort: "<host-supported effort>"
```

Role overrides более специфичны и merge поверх route overrides.

EmbrAIon не поддерживает глобальный model catalog; `model`, `effort` и `options` — opaque host-owned values.

## `.embraion/validation.yaml`

Объявляет project validation profiles:

```yaml
profiles:
  fast:
    - python -m unittest discover -s tests
  affected:
    - python -m unittest discover -s tests
  full:
    - python -m unittest discover -s tests
    - python -m compileall src
```

`fast`, `affected` и `full` — default names, но schema разрешает дополнительные.

```bash
embraion validation list
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

Команды выполняются последовательно из project root и записывают redacted structured evidence в `.embraion/state/validation/`. Empty profile возвращает `skipped`, а не false pass.

## `.embraion/agents.yaml`

Определяет project-specific agents, которые проецируются вместе с reusable Core roles.

```yaml
agents:
  - id: domain-specialist
    title: Domain Specialist
    extends: reviewer
    purpose: Review project-specific domain behavior.
    access: read-only
    responsibilities:
      - focus review on project-specific domain contracts
```

Project agent может наследовать одну non-Lead Core role, но обязан сохранять её access boundary. Нельзя shadow Core ID, extend `lead` или расширять read-only до write.

Host output:

```text
Codex          .codex/agents/<id>.toml
GitHub Copilot .github/agents/<id>.agent.md
Claude Code    .claude/agents/<id>.md
```

## Опциональный `.embraion/execution.yaml`

Проекты с `embraion execute` могут объявить reviewed executable bindings. Они связывают deployments с adapter и ограничивают selector/provider, credential references, source IDs, trust levels, aliases, timeout/options ceilings и observed model/provider evidence.

Secret values не должны храниться в config.

`dataClassAliases` — compatibility mapping на execution boundary и не создаёт новый Core data class.

См. [Execution и провайдеры](execution.md).

## Опциональный `.embraion/pricing.yaml`

Для deterministic cost calculation проект объявляет approved official pricing sources и SKU mappings.

```bash
embraion pricing refresh
embraion pricing status
```

Runtime calculation использует validated local snapshot. Rates, URLs, SKU mappings, freshness и applicability dates принадлежат проекту.

См. [Pricing и стоимость](pricing.md).

## Project settings не должны переопределять Core

Не копируйте generic-механизмы EmbrAIon в project configuration.

- проект выбирает **какой** deployment использовать, Core владеет routing contract;
- проект объявляет **какие** paths protected, Core владеет generic policy/enforcement mechanics;
- проект определяет **какие** validation commands доказывают correctness, Core владеет validation execution/evidence;
- проект может добавить domain specialist, но generic Architect/Reviewer/Validator остаются Core concerns.

## `.embraion/.gitignore`

Project-local ignore:

```gitignore
state/
cache/
```

Runtime может создать:

```text
.embraion/state/
.embraion/cache/
```

Это не каноническая project configuration и обычно не должно отслеживаться Git.

Projection ownership ledgers также находятся в `.embraion/state/projections/`. В свежем worktree ledger может отсутствовать; во время намеренного framework update EmbrAIon может восстановить ownership только по byte-for-byte совпадению с projection точного previous pin. Изменённые или недоказанные файлы остаются conflicts.

## Каноническая конфигурация vs generated host projection

Файлы `.embraion/` выше — project-owned configuration. Файлы, создаваемые `embraion install`, — projections.

```text
.codex/...       # Codex
.github/...      # GitHub Copilot
.claude/...      # Claude Code
```

Для изменения policy, knowledge, validation или routing редактируйте канонический `.embraion/` file, а не generated projection.

См. [Разговорную настройку](ai-hosts.md).
