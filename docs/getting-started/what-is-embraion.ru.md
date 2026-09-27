# Зачем нужен EmbrAIon?

EmbrAIon — **AI-First Engineering System** для программных репозиториев.

!!! tip "Простыми словами"
    Если правила работы AI начинают жить сразу в нескольких prompt'ах, файлах, настройках, CI-скриптах и памяти людей, EmbrAIon даёт им одно место, принадлежащее репозиторию.

## Если вам знакомо такое...

- каждый новый чат требует длинного prompt «помни нашу архитектуру»;
- Codex и Copilot знают немного разные правила проекта;
- AI иногда меняет путь, который не должен трогать;
- «запусти правильные тесты» зависит от того, помнит ли кто-то нужные команды;
- модель приходится выбирать вручную от задачи к задаче;
- новая сессия забывает решения, которые должны быть общими для всего проекта.

### До

```text
prompt
AGENTS.md
copilot instructions
host settings
CI scripts
память разработчика
        ↓
несколько частичных версий одних и тех же правил
```

### После

```text
                 .embraion/
                    ↓
      один инженерный контракт проекта
                    ↓
       Codex / Copilot / Claude Code
                    +
       validation / review / evidence
```

## Почему не просто `AGENTS.md` или native-инструкции host?

Можно использовать и их — EmbrAIon с ними совместим.

Native instruction file в основном доставляет инструкции одному host surface. EmbrAIon добавляет вокруг этих инструкций настройки, принадлежащие репозиторию, и детерминированные инструменты.

| Что нужно | Native instructions | EmbrAIon |
| --- | --- | --- |
| Объяснить AI, как работать | Да | Да, через host projections |
| Использовать один контракт в нескольких hosts | Обычно вручную | Контракт проекта канонический |
| Выбирать project knowledge | Зависит от host | Реестр project knowledge |
| Классифицировать protected/generated/external sources | Обычно текстом | Явная project policy |
| Иметь повторно используемый task/risk routing | Обычно host-specific | Стабильные route classes |
| Запускать project validation | Отдельно | Исполняемые validation profiles |
| Сохранять review/validation evidence | Отдельно / ad hoc | Структурированное evidence |
| Проверять protected paths / validation / review | Текст сам по себе не может | Опциональный deterministic enforcement |

## Практические примеры

### «Не изменяй vendor или хрупкие metadata»

**До:** повторять правило в prompt'ах.

**С EmbrAIon:** классифицировать пути в project policy; host projections доставят инструкцию AI, а validation/enforcement могут отклонить delivery, если protected path был изменён.

!!! note "Важно"
    Текстовая инструкция не может физически переопределить filesystem permissions каждого AI host. Жёсткая блокировка обеспечивается контролями самого host или исполняемыми validation/enforcement.

### «Используй UI Toolkit, а не legacy UI API»

**До:** повторять архитектурное правило в prompt'ах.

**С EmbrAIon:**

```text
knowledge → фиксирует UI Toolkit как архитектурный стандарт
host projection → доставляет правило AI
validation → обнаруживает запрещённые legacy API
enforcement → может требовать успешную validation перед merge
```

Knowledge объясняет правило. Validation доказывает, что результат ему соответствует.

### «Используй сильные модели только для сложной работы»

Классифицируйте работу стабильными классами задач/риска, затем оставьте host-default selection или задайте явные project overrides.

### «Переключайся между Codex, Copilot и Claude Code»

Храните project contract канонически и проецируйте нужные roles/skills в native-формат каждого host.

## Ментальная модель

> **EmbrAIon — операционная система AI-разработки; `.embraion/` — Settings конкретного репозитория.**

- **Core** владеет переиспользуемыми механизмами.
- **Проект** владеет фактами и настройками.
- **AI host** владеет разговором, reasoning и возможностями конкретного host.

## Чем EmbrAIon не является

- не заменяет Codex, Copilot или Claude Code;
- не является proxy, через который обязан проходить каждый prompt;
- не является runtime dependency готового приложения;
- не является глобальным каталогом моделей;
- не утверждает, что одни текстовые инструкции являются hard security controls.

## Дальше

- [EmbrAIon за 60 секунд](in-60-seconds.md)
- [Песочница за пять минут](playground.md)
- [Установка](installation.md)
