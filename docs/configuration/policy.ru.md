# Policy и защищённые пути

`.embraion/policy.yaml` содержит safety policy, которой владеет проект.

![Модель ownership и защиты sources](../assets/diagrams/en/13-source-ownership-protection.svg){ loading=lazy }

Пример:

```yaml
sources:
  canonical:
    - src/**
    - knowledge/**
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

## Source classes

### `canonical`

Project-owned source of truth. Обычные авторские файлы проекта.

### `protected`

Пути, которые обычная writable work не должна изменять. Используйте для материалов, требующих отдельного approval или ownership path.

Protected-path checks учитывают modifications, additions где применимо, deletions, rename sources и dot-prefixed paths вроде `.github/**`.

### `generated`

Build output и другие derived files, которые не должны восприниматься как canonical authored source.

Файлы, которые `embraion install` записал в журнал projection в `.embraion/state/projections`, тоже считаются generated, поэтому для установленных projection хостов не нужны записи, которые ведутся вручную. Явные записи по-прежнему поддерживаются и идут первыми. Файлы, которые projection сливает с пользовательским содержимым, `.claude/settings.json` и `.codex/config.toml` в merge mode, не добавляются. Журналы являются локальным состоянием: в новом checkout без них действуют только явные записи, а `security scan --all-files` всегда использует только явные записи. `embraion policy show --json` показывает выведенные записи в `derived-sources.generated`, а `embraion validate` предупреждает, если Git игнорирует файл из журнала.

### `external`

Материалы из внешнего источника, управляемые отдельно от project-owned source.

## Review policy

```yaml
review:
  substantial-required: true
```

Это правило проекта: substantial work требует review evidence там, где execution contract это предусматривает.

## Privacy default

```yaml
privacy:
  default-class: PRIVATE
```

Допустимые классы: `PUBLIC`, `PRIVATE` и `CONFIDENTIAL`.

Необязательная секция `sources` задаёт data class каждого стабильного source ID:

```yaml
privacy:
  default-class: PRIVATE
  sources:
    PublicDocs: PUBLIC
    App: PRIVATE
    VendorSdk: CONFIDENTIAL
```

Когда `sources` объявлена, execution request может называть только перечисленные source IDs, а его data class должен быть не ниже самого высокого класса этих sources; иначе request отклоняется до выбора provider. Без `sources` requests проверяются как раньше.

Необязательный [реестр источников](sources.md) добавляет для каждого ID роль и политику записи, а также `data-class`, который может только повысить объявленный здесь класс.

Выбор модели не может расширить эти границы.

## Enforcement policy

По умолчанию enforcement выключен:

```yaml
enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

Необязательный ключ `protected-sources` выбирает способ проверки protected paths:

```yaml
enforcement:
  protected-sources: base-tree
```

- `name` (по умолчанию, если ключ опущен): сопоставлять имена изменённых файлов со списком protected из политики текущего дерева.
- `base-tree`: читать список protected с merge base и сравнивать защищённые пути по ID объектов Git. Любое другое значение не проходит validation. Побеждает более строгий режим из политики head и политики merge base, поэтому изменение не может выключить `base-tree`, если он уже есть в базе; первый pull request, который его включает, опирается на политику head. См. [Защита источников по идентичности объектов Git](../guides/enforcement.ru.md#protect-sources-by-git-object-identity).

Не меняйте этот block вручную в надежде, что CI появится сам. Когда готовы установить GitHub Actions surface, используйте явную команду:

```bash
embraion enforcement install   --surface github-actions   --validation-profile affected
```

Полный процесс — в [Enforcement](../guides/enforcement.md).

## Режим merge

```yaml
merge:
  mode: human-only
```

Необязательный `merge.mode` определяет, кто может выполнить merge pull request по [правилу human merge](https://github.com/GORYNED/EmbrAIon/blob/main/core/rules/human-merge.md):

- `human-only` (по умолчанию, если `merge` не задан): агенты останавливаются на pull request, готовом к review, а merge выполняет человек.
- `owner-permission`: агент может выполнить merge pull request только с явного разрешения владельца для этого pull request, после того как required checks прошли на его финальном head и независимый reviewer подтвердил именно этот head.

Auto-merge не включается ни в одном режиме. Любое другое значение не проходит validation и projection. Установка хоста указывает выбранный режим одной строкой в projected Core rules (`.claude/rules/embraion-core.md`, `.github/instructions/embraion-core.instructions.md` и managed-блок Codex); после изменения снова выполните `embraion install`, до этого `projection verify` сообщает об устаревшей строке.

## Policy ceilings

`ceilings` объявляет максимум того, что разрешает проект. Deployments, execution bindings и routing могут сужать эти границы, но не расширять их, поэтому обычная правка YAML не может незаметно дать provider больше данных, доступа или источников:

```yaml
ceilings:
  providers:
    deepseek:
      data-classes: [PUBLIC]
      access-modes: [read-only]
      roles: [research]
      sources: [PublicOfficialUpstream]
    anthropic:
      data-classes: [PUBLIC, PRIVATE]
      access-modes: [read-only]
      roles: [independent-review]
      binding-required-billing-modes: [api]
  data-classes:
    CONFIDENTIAL: {providers: [openai]}
  sources:
    VendorSdk: {providers: [openai]}
  task-classes:
    protected-decision: {route-class: critical}
  critical:
    justifications: [security-critical, migration-data-loss, recovery-integrity, exceptional-systemic-risk]
```

- `providers.<provider>` ограничивает каждый включённый deployment этого provider. Если deployment не указывает измерение, заданное в ceiling, это считается отсутствием ограничения и ошибкой. `sources` ограничивает `sourceIds` execution binding этого deployment. Когда ограничены `data-classes` или `roles`, binding обязан перечислить `taskClasses`, и каждый task class, который binding или routing направляет на deployment, должен оставаться в пределах ceiling. `binding-required-billing-modes` требует execution binding для этих billing modes.
- Host overrides в `overrides.<host>` файла `.embraion/routing.yaml` проверяются вместе с их fallbacks. Каждый запрос, который подходит под override, должен оставаться в пределах ceiling. Routing отклоняет data class, которого нет в `capabilities.data-classes` выбранного deployment, поэтому deployment, чьи data classes в пределах ceiling, ограничивает data class любого запроса. Override в `routes` подходит и для запросов с любой role или без неё, поэтому выбор deployment с ceiling даёт `ceiling-unbounded`, если provider ограничивает `roles` или ограничивает `data-classes` сильнее, чем это делают capabilities deployment. Override в `roles` или `route-roles` должен называть role в пределах ceiling `roles` (`ceiling-role`), и он даёт `ceiling-unbounded`, если provider ограничивает `data-classes`, а capabilities deployment не удерживают их в этих пределах. Overrides в `task-classes` проверяются так же, как task classes из routing.
- `data-classes.<class>.providers` разрешает этот data class только перечисленным providers. Deployment без списка `data-classes` считается разрешающим все классы.
- `sources.<sourceId>.providers` разрешает execution source только перечисленным providers.
- `task-classes.<id>` закрепляет route class, role или data class task class из routing, чтобы их нельзя было понизить.
- `critical.justifications` делает обоснование critical-маршрута закрытым списком. Тогда `embraion route`, `dispatch` и `execute` принимают только `<reason>` или `<reason>: details` с причиной из списка.

Проверить ceilings можно отдельно или в составе `embraion validate` внутри проекта:

```bash
embraion policy check
embraion policy check --json
embraion validate
```

Каждый finding называет место в файле и ceiling, который превышен. Проекты без `ceilings` работают как раньше.

## Projection root checks

Codex merge mode сохраняет пользовательское содержимое в `.codex/config.toml`. Необязательная секция `projection` определяет, как `embraion projection verify --config-mode merge` относится к этому содержимому:

```yaml
projection:
  codex:
    strict-root: true
    forbidden-root-keys:
      - profiles.*.model
    allowed-root-keys:
      - mcp_servers
```

- `forbidden-root-keys` добавляет dotted-шаблоны ключей к Core defaults `model`, `model_reasoning_effort` и `agents.default_subagent_*`. Проект может расширить defaults, но не может их убрать.
- `allowed-root-keys` — необязательный allowlist ключей верхнего уровня. `developer_instructions` и `agents` разрешены всегда, потому что EmbrAIon управляет блоками внутри них.
- Текст корневых `developer_instructions` вне managed orchestration block сообщается всегда.
- `strict-root: true` превращает эти findings в ошибки проверки, так же как `--strict-root`. Без него это предупреждения, и результат verify зависит только от projection drift.

`components` объявляет, какие установленные projection components [`embraion check`](../reference/cli.md#embraion-check) проверяет для каждого host; host без `components` там не проверяется. Для Codex есть ещё `config-mode` (`replace` по умолчанию или `merge`) для component `config`:

```yaml
projection:
  codex:
    components: [config, agents, skills]
    config-mode: merge
  copilot:
    components: [agents, skills]
  claude-code:
    components: [agents, skills, scoped-agents, hooks]
```

Объявленные Claude Code `scoped-agents` и `hooks` также заставляют `embraion check` требовать их через `claude-native status --require`.

## Параметры check

Необязательная секция `check` выбирает, что запускает [`embraion check`](../reference/cli.md#embraion-check), поэтому в CI нет флагов проекта:

```yaml
check:
  organization: [full, compare]
  fail-on: medium
  all-files: true
  validation-profiles: [affected]
```

- `organization` перечисляет режимы organization check. `full` проверяет всю структуру. `compare` сравнивает с `--base-ref`, поэтому падают только новые findings, перемещения и смена GUID; без base ref он отмечается как `NOT RUN`. Без секции `embraion check` запускает `full` без `--base-ref` и `compare` с ним. Объявленные режимы называются `organization-full` и `organization-compare` и работают только при наличии `.embraion/organization.yaml`.
- `fail-on` задаёт минимальную серьёзность находки security scan, при которой проверка падает (`info`, `low`, `medium`, `high` или `critical`); по умолчанию `high`.
- `all-files` дополнительно сканирует все остальные текстовые файлы на приватные ключи, токены и машинные пути, как `--all-files` в [`security scan`](../security.md#scan-findings); по умолчанию `false`.
- `validation-profiles` перечисляет [validation profiles](../reference/cli.md#embraion-validation) проекта из `.embraion/validation.yaml`. `embraion check` запускает каждый после всех остальных проверок как шаг `validation-<profile>` так же, как `embraion validation run <profile>`, и записывает то же evidence в `.embraion/state/validation/`. Шаг проходит, только если результат профиля `passed`. Профили со статусом failed и timed-out его проваливают. Объявленный профиль должен что-то доказывать, поэтому неизвестный профиль, пустой профиль (`skipped`) и профиль с обязательным параметром без значения по умолчанию тоже проваливают шаг. Без ключа ни один профиль не запускается.

Флаг `--fail-on` переопределяет `fail-on`, а `--all-files` включает полное сканирование; у остальных значений флагов нет. Проект без секции ведёт себя как раньше. Для запусков без base pull request, например при push, передайте `base-ref` (или объявите `full`): `compare` там не запускается. Секцию принимает только release, который её содержит, поэтому сначала переведите pin проекта на такой release.

## Посмотреть effective policy

```bash
embraion policy show
embraion policy show --json
```

Некорректная project configuration fail-closed, а не интерпретируется эвристически.
