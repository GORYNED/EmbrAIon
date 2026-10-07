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

## Clean-tree guard

Structured profile может требовать, чтобы validation не меняла рабочее дерево:

```yaml
profiles:
  gate:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
    clean-tree: true
```

Без ключа ничего не проверяется, как раньше. При `clean-tree: true` EmbrAIon читает `git status --porcelain=v1 -z --untracked-files=all` перед первой командой и после последней и сравнивает результаты.

- Дерево, которое уже было грязным, допустимо. Его состояние становится baseline, и падают только новые различия. Файл, который уже был изменён и правится снова, считается различием, потому что сравнивается и содержимое.
- Каталог `.embraion/state/` игнорируется, потому что validation пишет туда собственное evidence.
- При сбое называются до 20 изменённых путей, а profile падает с записью в `failure-reasons`, которая начинается с `clean-tree guard failed`.
- Вне Git work tree или без `git` guard получает статус `blocked`, и profile падает. Команды всё равно запускаются, их результаты остаются в evidence.

В записи появляется объект `clean-tree` с полями `status` (`passed`, `failed` или `blocked`), `baseline-dirty`, `changed-count` и `changed-paths`. Profile без команд получает `skipped` и не проверяется.

## Output limit

По умолчанию полный redacted output каждой команды хранится в её log, а запись содержит tail не более 8000 символов на поток. Очень большой вывод может сделать log огромным. Structured profile может ограничить его ключом `output-limit-bytes` (целое число не менее 1024):

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
    output-limit-bytes: 1048576
```

Если поток больше лимита, EmbrAIon оставляет только первую и последнюю половину лимита, обрезанные по границам строк, и ставит между ними маркер в log:

```text
[... output truncated: 9400000 bytes (210000 lines) omitted; total 9500000 bytes, 211000 lines ...]
```

В память читаются только сохранённые части. Каждая часть проходит redaction отдельно. Без ключа log не обрезается.

В обоих случаях, если поток длиннее tail записи, строка команды получает `stdout-head` или `stderr-head` (первые 8000 символов) и объект `output` с итогами `bytes` и `lines` по каждому потоку и `log-truncated`. Короткий вывод не добавляет полей. Запись показывает `output-limit-bytes`, если profile его задаёт.

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
