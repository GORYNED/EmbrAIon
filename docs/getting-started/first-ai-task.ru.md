# Первая задача для AI

После инициализации EmbrAIon и установки host projection **обычная инженерная работа должна оставаться обычной**.

!!! tip "Простыми словами"
    Вы просите продуктовый или инженерный результат. Правила проекта уже находятся в репозитории.

## Первый рабочий цикл

| Вы делаете | Что происходит за кулисами | Вы проверяете |
| --- | --- | --- |
| Просите: «Добавь retry при ошибке соединения» | Lead применяет project rules и выбирает полезные роли без отдельной просьбы о delegation | Code change |
| AI реализует задачу | Действует существующий routing/default model policy | Protected paths не нарушены |
| Запускаете проверки | EmbrAIon выполняет validation profile | Получен `passed`, а не `skipped` |
| Делаете review существенной работы | Lead получает независимый read-only review, когда Core или более строгая project policy этого требует | Решение о merge |

## 1. Проверьте состояние проекта

```bash
embraion doctor
embraion status
```

Для маленькой задачи в уже проверенном репозитории не нужно запускать diagnostics перед каждым изменением.

## 2. Просите результат

После setup используйте обычный инженерный запрос:

> Добавь retry при ошибке соединения и regression coverage.

Не используйте перегруженные framework prompt'ы вроде:

> Используй EmbrAIon, выбери агента и модель, прочитай эти файлы, запусти эти проверки, а потом сделай retry.

Эта настройка уже должна принадлежать репозиторию.

**После установки вы почти не должны думать про EmbrAIon во время обычной продуктовой работы.** Возвращайтесь к EmbrAIon, когда намеренно меняете сам project contract: knowledge, policy, validation, routing, agents или enforcement.

## 3. Что происходит за кулисами

```text
ваша задача
  ↓
AI host
  ↓
generated EmbrAIon host files
  +
project knowledge / policy / optional routing
  ↓
implementation
```

Reasoning и изменения по-прежнему выполняет AI host. В Codex проекция `config` помещает Lead guidance в корневой `developer_instructions`, поэтому достаточно обычного запроса без названий ролей. Lead выполняет тривиальную работу напрямую; для более крупных задач он сам выбирает только полезные роли: Analyst для requirements, Architect для boundaries, Researcher для неизвестных фактов, Worker для bounded implementation, Validator для проверок, Reviewer для независимого review, Steward для compatibility и persistence.

Каждое делегированное задание ограничено scope, ownership, acceptance criteria и ожидаемыми evidence. Lead может распараллеливать read-only discovery и независимые изменения; общие файлы, shared contracts и зависимости требуют последовательной работы или явной isolation. Перед native spawn Lead классифицирует каждое задание и разрешает его routing, затем объединяет результаты и сохраняет окончательное право приёмки. Пустой project `agents: []` сохраняет Core roles.

Guidance зависит от trusted host config, native capabilities, permissions и инструкций более высокого приоритета. Он не делает orchestration детерминированной: validation и review требуют реальных evidence. Ownership проекций и merge описаны в [Codex](../hosts/codex.md).

Все supported host projections также содержат canonical `orchestration` skill с generated Core Lead contract. Codex, Copilot, Claude Code и Portable получают общий guidance, но загрузку skill выбирает каждый host. Корневые инструкции Codex дают дополнительную точку входа без зависимости от выбора skill.

## 4. Validation

```bash
embraion validation list
embraion validation run affected
```

!!! warning
    `skipped` — не pass. Это значит, что профиль не содержит исполняемых команд.

## 5. Review и завершение

Для meaningful changes собирайте свежие соразмерные проверки и фиксируйте residual risk. Существенная реализация требует независимой read-only оценки Reviewer, когда Core или более строгая project policy этого требует; автор реализации не может дать независимое одобрение собственной работе. Lead разрешает findings, обновляет validation после fixes и запрашивает новый review, если изменения делают прежние evidence неактуальными. Missing, skipped, historical и unavailable checks не являются свежим pass.

Если host projections намеренно менялись:

```bash
embraion projection diff --host codex --destination .
```

![Первая задача для AI](../assets/diagrams/en/08-first-ai-task.svg){ loading=lazy }

Дальше: [Ежедневный процесс](../guides/daily-workflow.md).
