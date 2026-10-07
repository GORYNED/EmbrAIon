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

## Timeouts

Structured profile может ограничить время каждой command опциональным ключом `timeout-seconds`. Число действует для каждой command в profile; список задаёт по одному значению на command по порядку, а `null` оставляет command без ограничения:

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
      - python tools/package.py
    timeout-seconds: [1800, null]
```

Без ключа commands выполняются без timeout, как раньше. `--timeout SECONDS` в командной строке заменяет настроенное значение для каждой command этого запуска. Список, длина которого не совпадает с числом commands, или значение, не являющееся положительным числом, fail-closed.

## Optional commands and prerequisites

Команда может остаться обычной строкой. Она также может быть mapping, в том же списке `commands` или в простом списке profile:

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
      - command: ./tools/lint.sh
        required: false
      - command: ./tools/device-check.sh
        requires:
          executables: [adb]
          env: [DEVICE_ID]
          platforms: [linux, macos]
```

- `required` необязателен, по умолчанию `true`.
- `requires` необязателен. `executables` ищутся в `PATH` (имя с разделителем пути разрешается от корня проекта), переменные `env` должны быть заданы и не пусты в окружении команды, `platforms` — список из `linux`, `macos`, `windows`.

Команда с отсутствующим prerequisite не запускается. Она получает статус `blocked` с причиной, а не `failed`. Blocked обязательная команда проваливает profile. Blocked необязательная — нет.

Команда с `required: false` всё равно запускается, её сбой или timeout записываются в evidence. Profile из-за них не падает: он остаётся `passed`, а в записи появляется счётчик `warnings`. Команда без `required` и `requires` ведёт себя как раньше. Неизвестные ключи, не-boolean `required`, неизвестная платформа или пустое имя fail-closed.

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

Каждый запуск сохраняет redacted structured evidence в `.embraion/state/validation/` и по одному полному redacted log на command в `.embraion/state/validation/<evidence-id>/`. См. [Валидация и evidence](../validation.ru.md#evidence).

## Безопасность

Validation commands — исполняемая project configuration. По возможности делайте их deterministic и repository-local, review'ьте изменения как code и не помещайте secrets прямо в command strings.

Malformed `validation.yaml` fail-closed по project schema.

Дальше: [Валидация и evidence](../validation.md).
