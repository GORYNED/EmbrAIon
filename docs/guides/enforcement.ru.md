# Enforcement

EmbrAIon разделяет **политику проекта** и **enforcement при merge**.

Политика может существовать без исполняемого CI. Enforcement включается явно и только по желанию проекта.

![Валидация и enforcement](../assets/diagrams/en/06-enforcement.svg){ loading=lazy }

## Перед включением enforcement

Сначала убедитесь, что этим настройкам можно доверять:

1. protected/canonical/generated/external paths в `.embraion/policy.yaml`;
2. выбранному validation profile в `.embraion/validation.yaml`;
3. правилам review, если review будет обязательным.

Проверьте их:

```bash
embraion doctor
embraion policy show
embraion validation list
embraion validation run affected
```

Не используйте пустой validation profile как merge gate: он вернёт `skipped`, а не `passed`.

## Проверить статус enforcement

```bash
embraion enforcement status
```

По умолчанию enforcement выключен.

## Установить механизм GitHub Actions

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

Чтобы дополнительно требовать актуальное одобренное review PR:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected \
  --require-review
```

Команда явно создаёт:

```text
.github/workflows/embraion-enforcement.yml
```

и включает соответствующий блок policy проекта.

Существующий workflow с другим содержимым не заменяется молча; намеренная замена требует `--force`.

## Что проверяет gate

Enforcement check объединяет:

- обнаружение изменений protected-source;
- свежий результат исполняемого validation profile;
- evidence о review, если оно требуется.

Проверка protected paths учитывает удаления, исходные пути rename и dot-prefixed paths.

При необходимости запустите её вручную:

```bash
embraion enforcement check --base-ref origin/main
```

Со structured run evidence:

```bash
embraion enforcement check \
  --base-ref origin/main \
  --run-id task-001
```

## Сделать gate обязательным для merge

Установка workflow **не меняет** branch rules репозитория автоматически.

Если GitHub должен блокировать merge при провале gate, настройте сгенерированный status check **EmbrAIon enforcement** как required в ruleset или branch rules репозитория.

Это разделение намеренное: администрирование репозитория остаётся явным решением человека.

## Что EmbrAIon не делает молча

`embraion init`, host `install` и `harness audit` не устанавливают исполняемые hooks или enforcement workflows без явного запроса.

`harness audit` сообщает о доступных surfaces, но не устанавливает их.
