# Project Bootstrap

После `embraion init` и установки host projection напишите:

> Настрой EmbrAIon для этого проекта.

Lead загружает канонический Core skill `project-bootstrap`. Эта переиспользуемая процедура проецируется в Codex, GitHub Copilot, Claude Code и Portable. Это процедура AI-хоста, а не новая CLI-команда и не обещание автоматического исполнения статических файлов. Trust, permissions, загрузка skills и native capabilities хоста продолжают действовать. Portable переносит процедуру для потребляющей интеграции; сам он не запускает AI-сессию.

## Сначала исследование, затем изменения

Bootstrap сначала изучает репозиторий и существующие `.embraion/**`: README и инструкции участникам, архитектуру и решения, source authority, compatibility и persistence contracts, спецификации, CI, package manifests, build/test/lint scripts, generated и vendor paths, public APIs, сериализацию и release workflow. Отсутствие документа не доказывает отсутствия соответствующей задачи.

Существующие решения проекта остаются авторитетными. Bootstrap сохраняет корректные entries, намеренные custom settings, более строгую policy, агентов проекта и существующий routing, если tuning не запрошен. Он вносит минимальные подтверждённые изменения и сообщает о неоднозначности вместо подмены решения догадкой.

## Что настраивается

| Область | Результат Bootstrap |
| --- | --- |
| Knowledge | Связать существующие авторитетные документы с Project Contract Slots; добавить extra knowledge только когда оно полезно для выбора контекста |
| Policy | Определить canonical, protected, generated и external paths; сохранить privacy, review requirements и намерение enforcement |
| Validation | Найти реальные repository/CI commands и настроить полезные профили `fast`, `affected`, `full` |
| Project agents | Предпочесть `agents: []`, если Core roles достаточно; сохранить специалистов и добавлять только стабильные обязанности проекта с ограниченным доступом |
| Routing | Сохранить host-default или существующий выбор; tuning выполнять только по явному запросу |
| Host projections | Проверить согласованность и при необходимости регенерировать через официальные install/update механизмы |

Knowledge slots: `constitution`, `architecture`, `source-authority`, `compatibility`, `persistence`, `engineering-workflow`, `specification`, `deferred-tasks`. YAML ссылается на документы, а не копирует содержимое. Необязательный slot без авторитетного источника остаётся null или unbound.

Bootstrap может создать отсутствующий канонический документ только если concern реально существует, доказательств достаточно и документ существенно улучшает будущую разработку. Факты выводятся из проверенных кода, структуры, CI и contracts. Недостаточно evidence — значит unbound slot и явно указанное ограничение, а не выдуманная архитектура, lifecycle, compatibility или persistence.

Policy следует реальному ownership. Необычная структура не превращает first-party code в external. Важность файла сама по себе не делает его protected. Неизвестная классификация закрывает действие; канонические data classes остаются `PUBLIC`, `PRIVATE`, `CONFIDENTIAL`. Детерминированный enforcement не включается ради завершения настройки.

## Реальная валидация

Bootstrap читает CI workflows и tooling проекта перед выбором команд:

- `fast`: недорогой feedback для частого запуска;
- `affected`: достаточные проверки correctness для обычного изменения;
- `full`: широкий локальный delivery/release gate; ограничения внешнего и multi-platform CI сообщаются отдельно.

Он не придумывает команды и не устанавливает зависимости скрытно ради зелёной проверки. Существующие дешёвые проверки должны заменить пустые defaults. Пустой профиль остаётся `skipped`, никогда `passed`. Перед запуском команды проверяются по repository workflow и permissions; небезопасные или недоступные проверки отмечаются как ограничения. Локальная команда не доказывает успех внешнего CI.

## Необязательный routing

Минимальный запрос не требует настройки моделей. `overrides: {}` — полностью корректный результат: Lead orchestration и delegation работают с выбором host-default.

Для намеренного tuning напишите:

> Настрой EmbrAIon полностью для этого проекта, включая routing с моделями и reasoning settings, реально доступными моему AI-хосту.

Lead проверяет подтверждённые host-native selectors, efforts, options и возможности конкретной поверхности, где это доступно. Переиспользуемый конкретный выбор хранится в `.embraion/deployments.yaml`; выбор role, route и task-class — в `.embraion/routing.yaml`. Role != Route != Model. Выбор не меняет access, privacy, ownership, review или validation requirements. Если доступность или применение нельзя подтвердить, Lead сохраняет существующий выбор и сообщает capability limitation. См. [Routing](../model-routing.md) и [AI-хосты](../hosts/index.md).

Только для routing:

> Настрой EmbrAIon routing для этого репозитория с моделями и reasoning settings, реально доступными этому хосту. Оставь host-default там, где явный routing не добавляет пользы, сохрани safety policy проекта и проверь полученные routes.

Расширенный запрос может добавлять ограничения, не заменяя короткий обычный prompt:

> Настрой EmbrAIon для этого проекта. Используй существующие авторитетные документы, сохрани намеренные настройки и более строгую policy, найди реальные проверки CI, оставь fast недорогим, сообщи о недоступных проверках, оставь необязательный routing на host-default и покажи diff и verification evidence.

## Необязательный детерминированный план

Core skill владеет семантическим discovery, решениями о документации, tuning routing и verification. Необязательный расширенный helper собирает candidates без запуска команд репозитория:

```bash
embraion bootstrap plan --output .embraion/state/bootstrap-plan.json
```

Изучите план и оригинальные источники: authority, безопасность команд, локальный контекст CI и стоимость. Helper распознаёт ограниченный набор имён документов и форм команд; это не полный анализатор репозитория. Он не создаёт документацию, не настраивает модели, не устанавливает зависимости и не запускает validation. Он заполняет unbound slots и пустые profiles, может консервативно заполнить пустой canonical source list; populated settings, routing, agents, privacy, review и enforcement сохраняются.

Применяйте только неизменённый проверенный план:

```bash
embraion bootstrap apply --plan .embraion/state/bootstrap-plan.json
```

Apply валидирует schemas и отклоняет изменённые планы, устаревшие source/configuration evidence, изменившееся discovery и несовпадающий project root. Храните планы в локальном `.embraion/state/` или вне репозитория. Если candidates требуют семантической коррекции, внесите ограниченные evidence-backed изменения конфигурации и создайте/проверьте новый план; не редактируйте JSON для обхода проверок. Применение helper не является verification: Lead ещё запускает применимые diagnostics и реальную validation.

## Проверка и отчёт

После настройки Bootstrap выполняет пропорциональную проверку применимыми официальными командами:

```bash
embraion doctor
embraion status
embraion context slots
embraion policy show
embraion validation list
embraion route --validate
embraion route --audit-authority
embraion projection diff --host codex --destination .
```

Для projection checks используйте установленный host и destination, а при partial adoption — выбранные components/config mode. Запускайте реальные настроенные validation profiles, когда это безопасно и уместно. Перед регенерацией изучите generated output; не редактируйте его вручную и не разрешайте ownership conflicts автоматическим `--force`.

Отчёт перечисляет knowledge bindings, изменения policy и validation, решения по agents и routing, изменённые файлы/документы, реально выполненные проверки, skips, infrastructure limitations и неоднозначности. Изучите канонический diff и evidence перед тем, как полагаться на конфигурацию.

## Повторный запуск и обычная работа

Повторите тот же prompt после изменений workflow или архитектуры. Bootstrap должен безопасно сходиться к результату без дублирования knowledge, docs, agents и колебаний классификации. Меняется только то, что оправдано новыми evidence.

Затем работайте обычно:

> Исправь retry flow и добавь regression coverage.

Не нужно упоминать EmbrAIon или выбирать роли для каждой задачи. Lead читает контракт, пропорционально делегирует, независимо классифицирует каждое assignment, разрешает routing, проверяет native application при явной настройке, собирает validation/review и сохраняет окончательные полномочия.

Ручные решения остаются там, где нужны evidence или authorization: недоступные host selectors, неоднозначные ownership/authority, credentials и external integrations, зависимости вне установленного workflow, trust/settings хоста и repository rules для enforcement. Bootstrap показывает эти границы вместо выдумывания фактов или скрытого расширения доступа.
