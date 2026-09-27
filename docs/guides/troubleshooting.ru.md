# Решение проблем

Начните с:

```bash
embraion doctor
embraion status
```

Эти команды обычно быстрее отвечают на configuration/runtime вопросы, чем ручной разбор generated files.

## `Invalid .embraion/...`

EmbrAIon валидирует canonical project configuration по schema и fail-closed при malformed values.

Частые причины:

- list записан как string;
- отсутствует required agent field;
- использован unsupported data class/access value;
- configuration записана не в тот `.embraion/` file.

Исправляйте canonical file, а не generated host output. См. [Файлы конфигурации проекта](../configuration/project-files.md).

## `Projection conflicts with user-modified or unowned files`

Preview ownership:

```bash
embraion projection diff --host codex --destination .
```

Для mature repo принимайте только нужные components:

```bash
embraion projection diff --host codex --destination . --component skills
embraion install --host codex --destination . --component skills
```

`--force` используйте только после осознанного решения, что EmbrAIon должен заменить конфликтующий файл.

## Launcher/project version mismatch

Проект pin'ит release EmbrAIon в `.embraion/project.yaml`. Обычные команды могут разрешить эту точную published runtime из cache.

Для намеренного update:

```bash
pipx upgrade embraion
cd MyProject
embraion update
```

Safe normalization целится в installed launcher version. См. [Runtime и разрешение версий](../reference/runtime-version-resolution.md).

## `Validation ... skipped`

Profile существует, но не содержит commands.

```bash
embraion validation list
```

Добавьте реальные commands в `.embraion/validation.yaml`. `skipped` не считается `passed`.

## Validation failed

```bash
embraion validation run affected
```

Исправьте project failure. Не ослабляйте policy только ради зелёного gate.

## Enforcement disabled

Это default.

```bash
embraion enforcement status
```

Когда проект готов, установите enforcement явно. См. [Enforcement](enforcement.md).

## `Unknown validation profile`

CLI/enforcement ссылается на profile, которого нет в `.embraion/validation.yaml`. Настройте его или выберите существующий.

## `Unknown route` или неожиданный `host-default`

`host-default` — нормальный результат: AI client использует свой default/automatic model selection.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

Добавляйте routing overrides только если проекту нужен explicit host-specific selection.

## AI всё равно изменил protected path

Host projection — guidance для AI-клиента, а не filesystem sandbox.

Deterministic protection обеспечивается validation/enforcement:

```bash
embraion enforcement status
embraion enforcement check --base-ref origin/main
```

Если check должен блокировать merge, настройте branch rules.

## Routing override не переключил модель в UI

Для host-native work это ожидаемо.

`.embraion/routing.yaml` описывает project routing contract. EmbrAIon не забирает под свой контроль Codex/Copilot/Claude UI model picker. Host остаётся authoritative для фактической model availability и execution.

Проверить resolution:

```bash
embraion route --host codex --route-class complex --data PRIVATE
```

Provider-neutral `embraion execute` — отдельный путь, где EmbrAIon владеет bounded attempt loop.

## После `embraion update`

```bash
embraion doctor
embraion status
embraion projection diff --host codex --destination .
```

`update` меняет project config/pin, но не reinstall generated host projections. Reinstall нужен только если diff показывает намеренное обновление, которое вы хотите принять.

## Runtime cache problems

```bash
embraion cache list
embraion cache prune --older-than 90
embraion cache prune --older-than 90 --apply
```

Сначала проверяйте dry-run candidates, затем применяйте `--apply`.

## Generated files выглядят stale после update

Это намеренно. Project config update не переписывает host projections.

Сначала:

```bash
embraion projection diff --host codex --destination .
```

Затем reinstall, если он действительно нужен.

## Всё ещё проблема?

См. [Поддержку](../oss/support.md) или откройте focused GitHub Issue с версией EmbrAIon, OS, command, error output и minimal reproduction. Не включайте secrets или private project data.
