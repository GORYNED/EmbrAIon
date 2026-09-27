# FAQ

Прямые ответы на концептуальные вопросы, которые чаще всего появляются после quick start.

## Нужно ли упоминать EmbrAIon в каждом prompt?

Нет.

После установки project contract и host projection обычная работа должна выглядеть как обычная инженерная задача:

> Добавь retry behavior и regression coverage.

Возвращайтесь к настройкам EmbrAIon, когда намеренно меняете project knowledge, policy, validation, routing, agents, execution или enforcement.

## Перехватывает ли EmbrAIon мои prompts?

Нет.

В host-native работе вы общаетесь напрямую с Codex, GitHub Copilot, Claude Code или другим поддерживаемым host. EmbrAIon предоставляет сгенерированные host-native instructions и принадлежащие репозиторию project rules.

Опциональный путь `embraion execute` существует отдельно.

## Routing действительно переключает модель в UI AI-клиента?

Не обязательно.

По умолчанию routing разрешается в `host-default`, поэтому host сохраняет контроль над своим текущим выбором модели.

Проект может записать явные model/effort/options overrides, но EmbrAIon не перехватывает UI model picker host. Используйте `embraion route`, чтобы увидеть результат project routing.

## Почему deployment и routing разделены?

Потому что они отвечают на разные вопросы:

- **Deployment:** какой переиспользуемый конкретный выбор существует?
- **Routing:** когда route или role должны его выбирать?

Для provider-neutral execution появляется третий вопрос:

- **Execution binding:** как этот deployment разрешено безопасно вызывать?

См. [Глоссарий](glossary.md) или [Engineering Model Deep Dive](reference/engineering-model.md).

## Нужен ли мне `.embraion/execution.yaml`?

Обычно нет.

Он нужен только проектам, которые сознательно используют provider-neutral путь `embraion execute`. Для обычной работы Codex/Copilot/Claude он не требуется.

## Сгенерированные host files — это source of truth?

Нет.

Канонический project contract находится в принадлежащей проекту EmbrAIon configuration/knowledge. Generated host files — projections этого контракта.

Если generated file разошёлся с ожидаемым состоянием, используйте projection diff/verify и переустанавливайте его намеренно, а не поддерживайте вторую копию policy вручную.

## Protected path означает, что AI физически не может его изменить?

Не за счёт одной текстовой инструкции.

Host projections сообщают AI, какие ограничения он должен соблюдать. Детерминированная защита обеспечивается validation/enforcement и, где применимо, host/repository controls.

Это принципиальное разделение: **guidance — не enforcement**.

## `skipped` validation считается pass?

Нет.

`skipped` означает, что в profile нет executable commands. Настройте реальные проверки, прежде чем использовать profile как evidence или merge gate.

## Нужно ли настраивать каждый файл в `.embraion/`?

Нет.

Начните с трёх вопросов:

1. Что AI должен знать? → `knowledge.yaml`
2. Что AI должен соблюдать? → `policy.yaml`
3. Чем доказать, что изменение работает? → `validation.yaml`

Оставьте deployments, routing, execution, pricing, custom agents и enforcement на defaults, пока проекту они не понадобятся.

## Может ли один репозиторий использовать несколько AI hosts?

Да.

Проект может установить несколько projections, сохраняя один канонический project contract.

## Работает ли EmbrAIon внутри готового приложения?

Нет.

EmbrAIon — engineering layer вокруг репозитория. Готовому Python, Unity, web или другому приложению EmbrAIon не нужен как application runtime dependency.

## Provider-neutral означает автоматическую поддержку любого provider или local model?

Нет.

Provider-neutral означает, что Core не хранит жёстко заданный каталог provider/model. Реальная поддержка конкретного provider/model всё равно зависит от host либо от намеренно настроенного и проверенного execution adapter/binding.

Последствия для local models и границ данных описаны в [Безопасность и поток данных](security-data-flow.md).

## Можно ли использовать EmbrAIon в CI?

Да.

Project validation и projection verification подходят для CLI/CI. EmbrAIon также может явно установить GitHub Actions enforcement surface:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

Установка workflow не делает status check обязательным автоматически; управление branch/ruleset остаётся явным решением владельца репозитория.

## Что читать дальше?

- Первый раз в системе: [EmbrAIon за 60 секунд](getting-started/in-60-seconds.md)
- Непонятный термин: [Глоссарий](glossary.md)
- Вопрос про security/privacy: [Безопасность и поток данных](security-data-flow.md)
- Проблема конфигурации: [Решение проблем](guides/troubleshooting.md)
- Точная архитектура: [Engineering Model Deep Dive](reference/engineering-model.md)
