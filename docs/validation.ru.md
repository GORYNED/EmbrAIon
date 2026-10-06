# Валидация и evidence

В EmbrAIon есть два связанных, но разных понятия validation.

![Validation, evidence, runs и review](assets/diagrams/en/09-validation-evidence-run-review.svg){ loading=lazy }

## Framework validation

```bash
embraion validate
```

Эта команда валидирует сам установленный framework EmbrAIon: schemas, catalogs, references, localization contracts и другие deterministic framework invariants.

Используйте при проверке установки EmbrAIon или разработке framework.

## Project validation profiles

Consuming repositories определяют executable commands в `.embraion/validation.yaml` и запускают:

```bash
embraion validation run <profile>
```

Сначала настройте profiles: [Настройка validation](configuration/validation.md).

Посмотреть profiles:

```bash
embraion validation list
```

Создать свежее evidence:

```bash
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

## Поведение evidence

Commands выполняются последовательно из project root. Каждый result записывает:

- profile и overall status;
- command identity;
- exit code;
- duration;
- redacted stdout/stderr tails длиной не больше 8000 символов каждый;
- действующий timeout и путь к полному log command;
- optional attached execution run;
- evidence ID/path.

Evidence хранится в:

```text
.embraion/state/validation/
```

Это local runtime state, игнорируемый project-local `.gitignore`. Каждая command также записывает полный redacted stdout и stderr в `.embraion/state/validation/<evidence-id>/command-<index>.log`, поэтому длинный failure можно изучить и за пределами tail в record.

Каждая command запускается в собственной process group (новая session на POSIX, новая process group в Windows). При timeout command или прерывании запуска EmbrAIon завершает всё дерево, включая процессы, запущенные command: на POSIX группа получает `SIGTERM`, затем `SIGKILL`; в Windows дерево завершается через `taskkill /T /F`. Прерванный запуск останавливается и не записывает evidence. Timeouts задаются `--timeout` или ключом profile [`timeout-seconds`](configuration/validation.ru.md#timeouts).

С `--run-id` каждая command получает ID run в environment variable `EMBRAION_RUN_ID`, чтобы запущенные ею tools могли помечать свои artifacts. Без `--run-id` эта variable удаляется из environment command.

Empty profile возвращает `skipped`. Failed/timed-out command делает profile failed. `--fail-fast` используйте только когда дальнейшие commands бессмысленны.

## Validation — evidence, а не обход policy

Green test result не может отменить failed privacy, permission, protected-path, compatibility или security gate.

Так же behavioral eval improvement не превращает deterministic safety failure в pass.

## Прикрепить evidence к structured run

```bash
embraion validation run affected --run-id task-001
```

Run должен быть active. Validation record прикрепляется по evidence ID вместо повторного ввода неподтверждённого claim.

См. [Runs и review](guides/runs-review.md) и [Enforcement](guides/enforcement.md).

## Структура кода и live evals skills

Задайте точные правила namespace, assembly и ассетов в [конфигурации структуры](configuration/organization.ru.md), затем подключите `embraion organization check` к профилям валидации и CI. Инкрементальная проверка отдельно показывает существующий долг; полный аудит сообщает все нарушения. Отсутствующая конфигурация означает `skipped`, а не подтверждение правильной структуры.

Существующий `eval run` оценивает переданные execution records. [Live evals](guides/skill-evals.ru.md) запускают изолированные авторизованные сессии хоста (Codex, Claude Code или любой CLI агента через хост portable) и сравнивают baseline/candidate в повторных английских и русских случаях. Тесты с fake host проверяют механизм, а не семантическое качество skill.
