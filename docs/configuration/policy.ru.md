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

## Посмотреть effective policy

```bash
embraion policy show
embraion policy show --json
```

Некорректная project configuration fail-closed, а не интерпретируется эвристически.
