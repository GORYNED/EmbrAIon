# Настройка валидации

`.embraion/validation.yaml` объявляет **конфигурацию** команд, которые создают реальное project evidence. Эта страница объясняет, как определять profiles; [Валидация и evidence](../validation.md) описывает их выполнение и использование evidence.

Простая форма остаётся валидной:

```yaml
profiles:
  fast:
    - python -m unittest discover -s tests/unit -p "test_*.py"
  affected:
    - python -m unittest discover -s tests -p "test_*.py"
  full:
    - python -m unittest discover -s tests -p "test_*.py"
    - python -m compileall src
```

Пустой profile — валидная конфигурация, но запуск даёт `skipped`, а не ложный pass. Команды выполняются последовательно из корня репозитория.

## Runtime parameters

Structured form подходит, когда значения известны только во время запуска:

```yaml
profiles:
  affected:
    commands:
      - pwsh -NoLogo -NoProfile -File tools/validation/validate.ps1 affected
    parameters:
      base-ref:
        argument: --BaseRef
        default: main
      head-ref:
        argument: --HeadRef
        default: HEAD

  full:
    commands:
      - pwsh -NoLogo -NoProfile -File tools/validation/validate.ps1 full
    parameters:
      justification:
        environment: PROJECT_FULL_JUSTIFICATION
        required: true
```

Передайте значения повторяемым `--param NAME=VALUE`:

```bash
embraion validation run affected   --param base-ref=origin/main   --param head-ref=HEAD

embraion validation run full   --param justification=persistence-migration
```

Parameter направляется либо в один command-line argument, либо в одну environment variable child process. Опциональный `commands` использует one-based indexes для ограничения конкретными командами.

```yaml
parameters:
  test-filter:
    argument: --filter
    commands: [1]
```

Argument values shell-quoted для текущей платформы. В Windows значения с `cmd.exe` metacharacters отклоняются вместо небезопасной интерполяции; используйте environment parameter, если такое значение действительно нужно.

Unknown parameters, missing required values, invalid command indexes, unsafe Windows argument values и malformed configuration fail-closed.

Structured validation evidence сохраняет имена использованных parameters, но не raw values и не expanded command с ними. Runtime parameter values также redacted из stdout/stderr. Не используйте validation parameters вместо secret manager.

## Выбор profiles

Полезная конвенция:

- `fast` — дешёвые проверки для быстрого feedback;
- `affected` — проверки, подходящие текущему изменению;
- `full` — широкий project gate перед high-risk delivery или release.

Schema разрешает дополнительные profile names.

## Запуск validation

```bash
embraion validation list
embraion validation run fast
embraion validation run affected
embraion validation run full
```

Полезные options:

```bash
embraion validation run affected --json
embraion validation run affected --fail-fast
embraion validation run affected --timeout 120
embraion validation run full --run-id task-001
```

Каждый запуск сохраняет redacted structured evidence в `.embraion/state/validation/`.

## Безопасность

Validation commands — исполняемая project configuration. По возможности делайте их deterministic и repository-local, review'ьте изменения как code и не помещайте secrets прямо в command strings.

Malformed `validation.yaml` fail-closed по project schema.

Дальше: [Валидация и evidence](../validation.md).
