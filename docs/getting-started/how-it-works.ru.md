# Как работает EmbrAIon

!!! tip "Простыми словами"
    Вы по-прежнему пишете обычный запрос в Codex, Copilot или Claude Code. У host уже есть сгенерированные native-файлы, которые связывают его с контрактом EmbrAIon в репозитории. EmbrAIon не перехватывает чат — он даёт host общие правила проекта и реальные команды для validation, enforcement и опционального provider execution.

## Простой путь: host-native работа

Так работает большинство проектов каждый день.

```text
вы просите инженерный результат
          ↓
Codex / Copilot / Claude Code
          ↓
generated host-native EmbrAIon files
          +
project .embraion/ settings
          ↓
AI reasoning / edits / tools
          ↓
project validation
          ↓
review / evidence / human merge
```

Для первого полезного setup сосредоточьтесь на:

- **Knowledge** — что AI должен знать.
- **Policy** — какие пути и правила соблюдать.
- **Validation** — какие команды доказывают корректность результата.

Routing, custom deployments, provider execution, pricing и enforcement могут оставаться на defaults, пока реально не понадобятся.

## Что является guidance, а что реально исполняется?

!!! note "Для инженеров"
    Generated agents и skills — это host-native instructions. Они направляют AI-клиент, но не равны исполняемым framework checks.

```bash
embraion validation run affected
embraion enforcement check --base-ref origin/main
```

Эти команды запускают реальные детерминированные проверки.

Полная ownership-модель описана в [Инженерной модели](../reference/engineering-model.md).

## Расширенный путь: provider execution

Некоторым проектам нужен контролируемый внешний/API lane.

```text
bounded execution request
      ↓
project deployment + execution binding
      ↓
EmbrAIon provider-neutral runtime
      ↓
approved provider/model
      ↓
normalized result / attempts / usage / cost
```

Это опционально. Обычные разговоры с Codex/Copilot/Claude через этот путь не проходят.

См. [Execution и провайдеры](../configuration/execution.md).

## Разговорная настройка

Можно сказать:

> Пометь `vendor/**` как protected, зарегистрируй архитектурный документ и добавь integration test command в affected validation.

AI host должен обновить канонические project files для этих concerns.

!!! tip "Не нужно запоминать YAML"
    Смысл `.embraion/` не в том, чтобы заставить людей помнить больше имён файлов. Он даёт репозиторию и AI **один источник истины для каждого типа настройки**.

## Дальше

- [Первая задача для AI](first-ai-task.md)
- [Ежедневный процесс](../guides/daily-workflow.md)
- [Инженерная модель](../reference/engineering-model.md)
