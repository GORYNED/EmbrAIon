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

## Нужно ли говорить Lead, каких агентов использовать?

Нет. Lead выбирает минимальный полезный набор специалистов по scope, ownership, risk и policy проекта. Trivial work может выполнять Lead; substantial work получает пропорциональное delegation и независимое review.

## Что означает `agents: []`?

Нет дополнительных специалистов проекта. Core Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher и Steward остаются доступными.

## Обязательно ли настраивать routing?

Нет. Routing необязателен, в том числе при Bootstrap. `overrides: {}` — корректный результат.

## Что происходит при пустом routing?

Resolution использует `host-default`: модель и effort выбираются host defaults или inheritance. Orchestration и delegation продолжают работать; EmbrAIon не придумывает model mapping.

## Как настроить routing?

Напишите:

> Настрой EmbrAIon routing для этого репозитория с моделями и reasoning settings, реально доступными этому хосту. Оставь host-default там, где явный routing не добавляет пользы, сохрани safety policy проекта и проверь полученные routes.

Lead использует skill `routing-configuration`, хранит reusable choices в `.embraion/deployments.yaml`, выбор route/role/task-class в `.embraion/routing.yaml` и проверяет результат. См. [Routing](model-routing.md).

## Может ли Lead использовать разные модели для разных subagents?

Да, если активная native поверхность хоста поддерживает resolved settings и их применение можно проверить. Каждое assignment классифицируется и разрешается независимо. Role != Route != Model. Механизмы Codex, Copilot CLI/VS Code/cloud и Claude Code отличаются; см. [AI-хосты](hosts/index.md).

## Что если хост не может применить явные model или effort?

Lead сообщает capability limitation до dispatch. Он не должен молча принять inheritance, substitution или capping либо заявить об успешном применении. Поддерживаемый handoff требует проверки effective settings, а при смене хоста — новой privacy/access проверки. Подготовка route или definition не является evidence выполнения.

## Что делает «Настрой EmbrAIon для этого проекта»?

Запрос загружает каноническую Core процедуру [Project Bootstrap](configuration/bootstrap.md): изучить репозиторий и текущую конфигурацию, связать полезные knowledge, сохранить policy, найти реальную validation, решить, нужны ли project agents, оставить routing необязательным, проверить результат и сообщить о нём.

## Будет ли Bootstrap выдумывать архитектуру или документацию?

Нет. Он использует авторитетные документы. Отсутствующий канонический документ создаётся только для реального concern, при достаточных проверенных evidence и существенной пользе для дальнейшей работы. Иначе slot остаётся unbound, а ограничение явно сообщается.

## Перезапишет ли Bootstrap существующие настройки проекта?

Он сохраняет корректные knowledge, намеренные custom settings, более строгую policy, project agents и существующий routing, если tuning не запрошен. Изменения требуют repository evidence. Generated host output остаётся производным и регенерируется официальными механизмами с ownership checks.

## Какая validation создаётся?

Реальные команды из workflow репозитория и CI: дешёвый частый `fast`, достаточный для обычных изменений `affected`, широкий локальный `full`. Без выдуманных команд. Пустые profiles остаются `skipped`; недоступный tooling и внешний CI отмечаются как ограничения.

## Можно ли повторить Bootstrap позже?

Да. Повторите его после изменений workflow или архитектуры. Он должен безопасно сходиться без дублирования entries, документов и агентов, меняя только то, что оправдано новыми evidence.

## Устанавливает ли Bootstrap внешние зависимости?

Он не устанавливает зависимости или tooling скрытно ради зелёной validation. Установленный setup workflow проекта может выполняться в пределах authorization; недостающая infrastructure и необходимые provisioning decisions сообщаются явно.

## Что остаётся ручным?

Решения, требующие полномочий пользователя или недоступных evidence: trust/settings хоста, непроверенные model selectors, неоднозначный ownership, credentials/integrations, provisioning вне установленного workflow и repository rules для enforcement. Bootstrap сообщает эти границы. Вы проверяете configuration diff и evidence.

## Что читать дальше?

- Первый раз в системе: [EmbrAIon за 60 секунд](getting-started/in-60-seconds.md)
- Непонятный термин: [Глоссарий](glossary.md)
- Вопрос про security/privacy: [Безопасность и поток данных](security-data-flow.md)
- Проблема конфигурации: [Решение проблем](guides/troubleshooting.md)
- Точная архитектура: [Engineering Model Deep Dive](reference/engineering-model.md)
