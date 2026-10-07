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

## План validation

Проект может описать, какие проверки подтверждают какую часть кода. Это опционально. Проект без этих ключей работает как раньше.

```yaml
profiles:
  affected:
    - python -m unittest discover -s tests -p "test_*.py"
  full:
    - python -m compileall src
    - python -m unittest discover -s tests -p "test_*.py"
    - python tools/package.py

areas:
  library:
    paths: [src/**]
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
  docs:
    paths: [docs/**, "*.md"]
    commands:
      - python tools/check-links.py
  packaging:
    paths: [tools/package.py]
    profiles: [full]

impact:
  - id: data-format
    paths: [src/schema/**]
    areas: [docs]
    full: data-migration

full-reasons: [data-migration, release-gate]
default-area: library
```

Ключи:

- `areas` сопоставляет имя area с `paths` (globs) и с proof: `commands` (command lines) и/или `profiles` (все commands этих profiles). Нужен хотя бы один proof.
- `impact` — упорядоченный список rules. У каждого rule есть `id`, `paths` (globs) и `areas` и/или `full`. Каждый rule, совпавший с изменённым path, применяется в записанном порядке. `full` называет причину из `full-reasons` и повышает plan до profile `full`. Если повышают несколько rules, причину называет первый в списке.
- `full-reasons` — закрытый список id причин. Rule или значение `--full-justification` вне списка — ошибка. Для причины или rule с `full` нужен profile `full`.
- `default-area` опционален. Изменённый path, не совпавший ни с area, ни с rule, выбирает эту area. Без неё такой path выбирает весь planned profile: проект проверяет больше, а не меньше.

Globs используют тот же matcher, что и source policy в `policy.yaml`. Glob пустой, абсолютный, с `..`, с непарной скобкой или слишком сложный — ошибка. Неизвестные area, profile или причина — ошибка. Ошибки формы ловит schema.

Вычислить и прочитать plan:

```bash
embraion validation plan affected --base-ref origin/main
embraion validation explain affected --base-ref origin/main --include-worktree
```

`plan` пишет детерминированный `plan.json` (по умолчанию `.embraion/state/validation/plan.json` или `--output FILE`). `explain` печатает, почему каждая area и command выбраны или не выбраны, и ничего не пишет. Изменённые paths берутся из Git: diff между merge base для `--base-ref` и `--head-ref` (по умолчанию `HEAD`). `--include-worktree` добавляет staged, unstaged и untracked файлы, которые Git не игнорирует. Файлы в `.embraion/state/` игнорируются.

Файл plan имеет `schema-version: 1` и поля: `profile`, `config-digest`, `inputs` (refs и resolved SHA), `changed-paths`, `matched-rules`, `selected-areas`, `skipped-areas` (с причинами), `escalation`, `fallback`, `selected-commands` (с источниками), `skipped-commands`, `status` (`selected` или `skipped`) и `skip-reason`.

Запуск по plan:

```bash
embraion validation run affected --base-ref origin/main
embraion validation run affected --plan .embraion/state/validation/plan.json
embraion validation run full --base-ref origin/main --full-justification release-gate
```

- `validation run <profile>` без `--base-ref`, `--include-worktree` и `--plan` выполняет все commands profile, как раньше.
- Plan выбирает commands из areas, из `profiles` areas и, при повышении или fallback, из всего profile. Дубликаты выполняются один раз.
- Plan, который ничего не выбрал, например потому что ничего не изменилось, завершается как `skipped` с причиной. Это никогда не pass.
- `--plan` принимает только plan для того же profile, совпадающий с текущей конфигурацией и выбирающий только объявленные commands. Иначе запуск fail-closed.
- Timeouts и parameters profile по-прежнему действуют для commands, к которым относятся.
- Run evidence содержит plan (`plan`) и копию в `.embraion/state/validation/<evidence-id>/plan.json` (`plan-path`).
- Plan options в проекте без `areas` — ошибка.

`validation list` также показывает areas, если они есть.

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
