# Модель capabilities

EmbrAIon использует явные типы capabilities, чтобы не смешивать policy, responsibility, procedure, orchestration и facts.

| Тип | Назначение |
| --- | --- |
| Rule | Обязательное / запрещённое / защищённое поведение |
| Agent | Ответственность и ownership |
| Skill | Повторяемая процедура |
| Workflow | Упорядоченная orchestration |
| Routing | Выбор model/provider/effort/execution |
| Tool | Детерминированная операция |
| Adapter | Интеграция с host/provider |
| Knowledge | Факты и архитектура |

У canonical capability должен быть один основной тип. Cross-references предпочтительнее, чем дублирование одного и того же содержания в нескольких типах.
