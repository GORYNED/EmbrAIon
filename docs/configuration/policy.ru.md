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

Выбор модели не может расширить эти границы.

## Enforcement policy

По умолчанию enforcement выключен:

```yaml
enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

Не меняйте этот block вручную в надежде, что CI появится сам. Когда готовы установить GitHub Actions surface, используйте явную команду:

```bash
embraion enforcement install   --surface github-actions   --validation-profile affected
```

Полный процесс — в [Enforcement](../guides/enforcement.md).

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
- Host overrides в `overrides.<host>` файла `.embraion/routing.yaml` проверяются вместе с их fallbacks. `roles` и `route-roles` должны держать каждую role в пределах ceiling `roles` этого provider (`ceiling-role`), а `task-classes` проверяются так же, как task classes из routing. Override в `routes` действует на все roles и data classes, поэтому если он выбирает deployment с ceiling, а provider ограничивает `roles` или `data-classes`, это finding `ceiling-unbounded`; используйте вместо него override для role, route-role или task class.
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

## Посмотреть effective policy

```bash
embraion policy show
embraion policy show --json
```

Некорректная project configuration fail-closed, а не интерпретируется эвристически.
