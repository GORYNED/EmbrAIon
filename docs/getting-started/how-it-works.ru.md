# Как работает EmbrAIon

!!! tip "Простыми словами"
    Вы по-прежнему пишете обычный запрос в Codex, Copilot или Claude Code. У AI-хоста уже есть сгенерированные native-файлы, которые связывают его с контрактом EmbrAIon в репозитории. EmbrAIon не перехватывает чат: он даёт AI-хосту общие правила проекта и предоставляет реальные команды для validation, enforcement и опционального provider execution.

## Bootstrap и выполнение задачи

Сначала попросите «Настрой EmbrAIon для этого проекта». [Project Bootstrap](../configuration/bootstrap.md) исследует репозиторий и настраивает канонический контракт. Дальнейшая работа следует потоку:

```text
Запрос пользователя → Lead → выбор специалистов
  → классификация каждого assignment → project routing
  → проверка host capability → native model/effort и выполнение
  → validation/review → Lead integration
```

Role != Route != Model. Host-default совместим с delegation; explicit routing применяется только через подтверждённые capabilities.

## Простой путь: host-native работа

Так работает большинство проектов каждый день.

```text
вы просите инженерный результат
          ↓
Codex / Copilot / Claude Code
          ↓
сгенерированные host-native файлы EmbrAIon
          +
настройки проекта .embraion/
          ↓
AI reasoning / правки / инструменты
          ↓
валидация проекта
          ↓
ревью / evidence / решение человека о merge
```

![Host-native и provider execution](../assets/diagrams/en/14-host-native-vs-provider-execution.svg){ loading=lazy }

Для первой полезной настройки сосредоточьтесь на:

- **Knowledge** — что AI должен знать о проекте.
- **Policy** — какие пути и правила он должен соблюдать.
- **Validation** — какие команды доказывают, что результат работает.

Routing, custom deployments, provider execution, pricing и enforcement можно оставить с безопасными настройками по умолчанию, пока они действительно не понадобятся.

## Что является инструкцией, а что реально исполняется?

!!! note "Для инженеров"
    Сгенерированные agents и skills — это host-native инструкции. Они направляют AI-клиент, но не являются исполняемыми проверками EmbrAIon.

![Инструкции и enforcement](../assets/diagrams/en/16-guidance-vs-enforcement.svg){ loading=lazy }

```bash
embraion validation run affected
embraion enforcement check --base-ref origin/main
```

Эти команды запускают реальные детерминированные проверки.

Полная модель владения описана в [Инженерной модели](../reference/engineering-model.md).

## Расширенный путь: provider execution

Некоторым проектам нужен отдельный контролируемый внешний/API-путь.

```text
ограниченный execution-запрос
      ↓
deployment проекта + execution binding
      ↓
provider-neutral runtime EmbrAIon
      ↓
разрешённый provider/model
      ↓
нормализованный результат / попытки / использование / стоимость
```

Этот путь опционален. Обычные разговоры с Codex, Copilot или Claude Code через него не проходят.

См. [Execution и провайдеры](../configuration/execution.md).

## Разговорная настройка

Можно сказать:

> Пометь `vendor/**` как protected, зарегистрируй архитектурный документ и добавь команду integration-тестов в affected validation.

AI-хост должен обновить канонические файлы проекта, отвечающие за эти настройки.

!!! tip "Не нужно запоминать YAML"
    Смысл `.embraion/` не в том, чтобы заставить людей помнить больше имён файлов. Он даёт репозиторию и AI **один источник истины для каждого типа настройки**.

## Дальше

- [Первая задача для AI](first-ai-task.md)
- [Ежедневный процесс](../guides/daily-workflow.md)
- [Инженерная модель](../reference/engineering-model.md)
