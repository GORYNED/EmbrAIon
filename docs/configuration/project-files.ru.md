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

Эти metadata отличаются от необязательного [инвентаря внешних возможностей](capabilities.md) со строгой schema. Декларация в нём не устанавливает интеграцию и не доказывает загрузку возможности хостом.

### `worktree`

`worktree.lfs` необязателен. Значение по умолчанию — `none`: новые worktrees создаются как раньше. Для репозитория с Git LFS задайте `hydrate`:

```yaml
worktree:
  lfs: hydrate
```

Новый checkout такого репозитория содержит текстовые pointer-файлы, пока содержимое не загружено. При `hydrate` команда `embraion worktree create` (и `worktree register` для worktree, созданного вашим host) загружает LFS-содержимое точного HEAD из собственного LFS-remote репозитория, делает checkout и проверяет каждый LFS-файл по размеру и SHA-256. Если проверка не прошла, команда завершается с ненулевым кодом, но worktree сохраняется. Любое другое значение и неизвестный ключ в `worktree` — ошибка. См. [руководство по инструменту worktree](https://github.com/GORYNED/EmbrAIon/blob/main/tools/worktree/README.md#git-lfs-hydration).

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
  deferred-tasks:
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

Шаблоны путей сохраняют прежние правила, включая `*` через разделители папок. Отдельный сегмент `**/` также соответствует нулю папок: `private/**/*.cs` защищает и `private/file.cs`, и вложенные файлы. Шаблоны длиннее 4 096 символов или с более чем восемью необязательными сегментами `**/` отклоняются, чтобы не пропустить защищённый путь молча.

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

Профиль каждого project agent содержит объединённые `triggers` и `outputs`. Если объявлен хотя бы один project agent, projected skill `orchestration` получает компактный раздел `Project specialists`: ID, наследуемая роль Core, purpose, а также triggers и outputs, объявленные проектом, чтобы Lead знал, когда делегировать. Профили ролей Core не меняются; без project agents раздел не создаётся.

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

## Опциональный `.embraion/external-capabilities.yaml`

Строгий версионированный инвентарь описывает независимо установленные возможности хоста. По умолчанию файла нет. Указывайте версию или digest, источник, лицензию, требования к хосту, доступ, класс данных и **имена** переменных окружения. Декларация не означает установку, разрешение или подтверждённую загрузку хостом. `embraion capabilities --path . --host codex --json` показывает границы локальных свидетельств; последующие этапы работы хоста остаются непроверенными без доверенного наблюдения. См. [Внешние возможности](capabilities.ru.md).

Схема v1 может читать устаревшие декларации `builtin:unity` для диагностики, но пакет больше не поставляется. Явно удалите такую запись перед установкой для выбранного хоста или обновлением; нужную замену сначала установите независимо через хост. См. [Внешние возможности](capabilities.ru.md).

## Опциональный `.embraion/integrations.yaml`

Строгий версионированный файл объявляет MCP servers, которые должна содержать host configuration проекта: `id`, `host`, `command`, `args`, `transport`, `access`, **имена** environment variables и опциональные `portable`, `cwd` и `required` (`cwd` и `required` только для записей Codex). По умолчанию файла нет, и сравнение integrations не выполняется. Если файл есть, `embraion security scan` сообщает об отсутствующих, неожиданных, расходящихся и непереносимых servers как о high-severity findings `integration-drift`. См. [Объявленные integrations](../security.ru.md#integrations).

## Опциональный `.embraion/knowledge-maintenance.yaml`

Задайте связи документов и исходных файлов, затем после проверки явно запустите `embraion knowledge snapshot --path .`. `embraion knowledge audit --path .` сравнивает локальные хеши и показывает изменённые или отсутствующие источники для проверки. Команда не переписывает документы и не выводит изменение внешней версии без наблюдаемых metadata. См. [Поддержка знаний](../guides/knowledge-maintenance.md).

## Опциональный `.embraion/organization.yaml`

Проект может задать ограничения на организацию кода. `embraion organization check --path . --base-ref main --head-ref HEAD --include-worktree --json` проверяет изменения постепенно. Старые нарушения не освобождают новый код от правил. См. [Организация кода](organization.md).

## Опциональный `.embraion/sources.yaml`

Этот строгий версионируемый файл перечисляет стабильные source ID с `role`, политикой записи `write` (`read-only`, `workspace-write` или `forbidden`) и необязательными `description`, `doc` и повышенным `data-class`. Путей машины в нём нет. По умолчанию файла нет, и тогда ничего не меняется. Если он есть, `embraion validate` его проверяет, `embraion sources` его показывает, а execution request с `workspace-write` может называть только источники, в которые разрешена запись. См. [Реестр источников](sources.md).

## Опциональный `.embraion/skills/`

Собственные skills проекта используют layout Core: один каталог на skill с entry point `SKILL.md`.

```text
.embraion/skills/<name>/SKILL.md
.embraion/skills/<name>/references/...   # необязательные вспомогательные файлы
```

Component `skills` проецирует их рядом со skills Core для Codex (`.agents/skills/`), GitHub Copilot (`.github/skills/`) и Claude Code (`.claude/skills/`). Файлы записываются в projection ownership ledger, поэтому `projection diff` и `projection verify` показывают изменённые копии как conflicts, а удалённые skills как obsolete; `install --prune` удаляет неизменённые obsolete-копии. Portable bundle остаётся только Core.

Projection завершается ошибкой до записи, если запись не является каталогом skill, имя не в lowercase kebab-case (не длиннее 64 символов), имя совпадает со skill Core, нет `SKILL.md`, в его front matter нет совпадающего `name` или непустого `description`, либо skill содержит символическую ссылку.

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

Ссылки контрольных точек и базовые снимки аудита знаний также хранятся в `state/`; они не заменяют policy проекта, Git и свидетельства review.

Projection ownership ledgers также находятся в `.embraion/state/projections/`. В свежем worktree ledger может отсутствовать; во время намеренного framework update EmbrAIon может восстановить ownership только по byte-for-byte совпадению с projection точного previous pin. Изменённые или недоказанные файлы остаются conflicts.

## Каноническая конфигурация vs generated host projection

Файлы `.embraion/` выше — project-owned configuration. Файлы, создаваемые `embraion install`, — projections.

```text
.codex/...       # Codex
.github/...      # GitHub Copilot
.claude/...      # Claude Code
```

Для изменения policy, knowledge, validation или routing редактируйте канонический `.embraion/` file, а не generated projection.

Projected host guidance ссылается на файлы Core, которых нет в consuming project (например, worktree workflow), через release tag EmbrAIon для projected framework version.

См. [Разговорную настройку](ai-hosts.md).

Projection ownership разделён по host и canonical destination: `.embraion/state/projections/<host>/<destination-id>.json` и соответствующий `<destination-id>.recovery.json`. Root projection использует `root`; alternate destinations используют SHA-256 канонического относительного пути внутри проекта либо абсолютного пути для внешнего destination. Filenames не содержат абсолютных путей. Installs, inventories, config-mode evidence и pruning независимы для каждого destination. Совпадающий legacy host-only ledger читается без mutation и автоматически мигрирует после successful install; несовпадающее или неоднозначное evidence не присваивается другому destination. Перенесённый проект не наследует ownership автоматически от recorded absolute destination.

## `.embraion/claude-native.yaml`

Необязательные привязки ролей к native агентам Claude и список сочетаний role, route-class, data-class и access для установки. Файл не задаёт model или effort: определения выводятся из routing и deployments. Компонент `scoped-agents` и защитные hooks включаются явно; см. [Claude Code](../hosts/claude-code.md).
