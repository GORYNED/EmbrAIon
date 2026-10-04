# Модель возможностей

EmbrAIon использует явные типы capabilities, чтобы не смешивать policy, responsibility, procedure, orchestration и facts.

| Type | Purpose |
| --- | --- |
| Rule | Required / prohibited / protected behavior |
| Agent | Responsibility и ownership |
| Skill | Повторяемая procedure |
| Workflow | Ordered orchestration |
| Routing | Task/risk classification, execution constraints, host resolution и optional project overrides |
| Tool | Deterministic operation |
| Adapter | Host/transport integration и projection |
| Knowledge | Facts и architecture |

Canonical capability должна иметь один primary type. Cross-references предпочтительнее, чем дублирование одного content в нескольких types.

Routing намеренно model-agnostic. Concrete model names, provider rates, lifecycle state и host availability не являются canonical Core capabilities.

EmbrAIon предоставляет reusable **механизмы** deployment eligibility, provider-neutral execution, pricing refresh/snapshots, health и evidence. Конкретные models, providers, rates, source URLs и availability facts остаются project- или host-owned.

Навыки Core описывают повторяемые [инженерные процедуры](guides/engineering-skills.md): миграцию совместимости, проектирование тестов, обновление зависимостей, исследование производительности и создание навыков. [Живая проверка навыка](guides/skill-evals.md) сравнивает базовое и новое поведение в свежих сессиях хоста; проверка предоставленной записи оценивает только эту запись. Событие чтения навыка не доказывает, что он вызвал результат.

Необязательные [внешние возможности](configuration/capabilities.ru.md) имеют отдельный lifecycle деклараций и наблюдений. Запись в инвентаре не доказывает установку, обнаружение хостом, загрузку инструкции, готовность инструмента или выполнение. Предметные возможности устанавливаются и управляются независимо через хост. Факты проекта и review gates продолжают действовать.

Детерминированная [проверка организации кода](configuration/organization.md) применяется к изменениям постепенно. Старый долг служит базой сравнения, но не исключением для новых нарушений. [Контрольные точки](guides/task-continuity.md) и [аудит знаний](guides/knowledge-maintenance.md) сохраняют локальные ссылки для проверки актуальности; они не продвигают learning и не дают одобрения.
