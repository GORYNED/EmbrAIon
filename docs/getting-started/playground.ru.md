# Песочница за пять минут

Вы можете попробовать EmbrAIon, не меняя существующую кодовую базу.

Песочница создаёт новый пустой Git-репозиторий, инициализирует project contract, устанавливает одну host projection и позволяет посмотреть routing и validation.

## 1. Создайте одноразовый репозиторий

```bash
mkdir embraion-playground
cd embraion-playground
git init
```

## 2. Инициализируйте EmbrAIon

```bash
embraion init --name EmbrAIonPlayground
```

Что появилось:

```text
.embraion/
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── deployments.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

Runtime-only каталоги `.embraion/state/` и `.embraion/cache/` остаются gitignored.

## 3. Установите одну host projection

Для Codex:

```bash
embraion install --host codex --destination .
```

Или:

```bash
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
```

## 4. Посмотрите состояние проекта

```bash
embraion doctor
embraion status
embraion policy show
embraion validation list
```

В свежем проекте validation profiles могут быть пустыми. Тогда запуск вернёт `skipped` — это не ложный pass.

## 5. Проверьте routing без вызова модели

```bash
embraion route   --host codex   --route-class substantial   --data PRIVATE
```

Без project override результат должен быть `host-default`: EmbrAIon классифицирует работу, а host остаётся ответственным за фактический выбор модели.

## 6. Попросите AI настроить песочницу

Откройте репозиторий в установленном AI-клиенте и попробуйте естественный запрос:

> Настрой EmbrAIon для этого проекта.

Затем посмотрите канонический diff в `.embraion/`.

Bootstrap должен сообщить, что в пустом репозитории нет application test workflow; optional slots остаются unbound, profiles — `skipped`, вместо выдуманных проверок. См. [Project Bootstrap](../configuration/bootstrap.md).

## Что это показывает

```text
init
 ↓
project-owned .embraion/ contract
 ↓
host projection
 ↓
normal AI conversation
 ↓
routing / validation / policy inspection
```

Песочница намеренно не имитирует платные provider calls или сложную validation приложения.

## Что дальше?

- [Minimal](../examples/minimal.md) — минимальный полноценный project overlay;
- [Python](../examples/python.md) — обычный application code + tests;
- [Unity](../examples/unity.md) — Unity 6 с EmbrAIon вне runtime приложения.

После этого переходите к [добавлению EmbrAIon в проект](first-project.md) или [подключению существующего репозитория](existing-repository.md).

## Очистка

Удалите каталог `embraion-playground`, когда закончите.
