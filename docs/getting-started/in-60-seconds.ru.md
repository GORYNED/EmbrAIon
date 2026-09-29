# EmbrAIon за 60 секунд

!!! tip "Простыми словами"
    Вы храните правила AI-работы **вместе с репозиторием**. AI-клиент получает сгенерированные native-инструкции, а EmbrAIon хранит project knowledge, safety boundaries, validation и routing в одном повторно используемом контракте проекта.

## Путь настройки

```text
pipx install embraion
  ↓
embraion init
  ↓
embraion install --host codex --destination .
  ↓
«Настрой EmbrAIon для этого проекта»
  ↓
контракт проекта настроен и проверен
  ↓
обычные инженерные запросы
```

Для других хостов используйте `copilot` или `claude-code`. [Project Bootstrap](../configuration/bootstrap.md) находит знания, policy и реальные проверки; optional routing остаётся на host-default. Portable переносит capability, но сам не исполняет AI-сессию.

## Что вы получаете

1. **Project knowledge** — укажите AI на важные архитектурные документы и источники истины.
2. **Project policy** — классифицируйте canonical, protected, generated и external paths.
3. **Validation** — задайте реальные команды, которые доказывают, что изменение работает.
4. **Host projections** — генерируйте native agent/skill-файлы, понятные Codex, Copilot или Claude Code.

> **Host projection** = сгенерированные native-файлы для вашего AI-клиента. Они доставляют инструкции EmbrAIon host'у и **не являются** вторым source of truth.

5. **Опциональный routing** — классифицируйте работу по сложности/риску и оставляйте host-default model selection, пока проекту не нужен явный override.
6. **Опциональный enforcement** — делайте требования к protected paths, validation и review детерминированными на этапе delivery/merge.

## Обычный опыт работы

Настройте репозиторий один раз, затем работайте обычно:

> Добавь retry behavior при потере соединения.

Не нужно начинать каждую задачу с framework prompt.

## Минимальная полезная настройка

Для большинства репозиториев сначала достаточно трёх вещей:

| Что | Файл |
| --- | --- |
| Что AI должен знать? | `.embraion/knowledge.yaml` |
| Какие правила он должен соблюдать? | `.embraion/policy.yaml` |
| Чем доказать, что изменение работает? | `.embraion/validation.yaml` |

Всё остальное может оставаться на безопасных значениях по умолчанию, пока реально не понадобится.

## Два пути дальше

- **Простой:** install → init → host projection → Project Bootstrap → обычные AI-задачи.
- **Инженерный:** ownership → projections → routing → execution → evidence/enforcement.

## Одно важное различие

Сгенерированные agent/skill-файлы — это **инструкции для AI host**.

Команды вроде:

```bash
embraion validation run affected
embraion enforcement check --base-ref origin/main
```

— это **реально исполняемые проверки**.

## Дальше

[Попробуйте безопасно в песочнице](playground.md).
