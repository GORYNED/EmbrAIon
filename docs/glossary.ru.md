# Глоссарий

Используйте эту страницу, когда термин EmbrAIon встретился раньше, чем вам понадобилась полная инженерная модель.

!!! tip "Простыми словами"
    Большинству проектов достаточно начать с **knowledge + policy + validation**. Остальные термины становятся важны только тогда, когда репозиторию нужен дополнительный контроль.

| Термин | Значение |
| --- | --- |
| **Project contract** | Принадлежащая репозиторию конфигурация и знания EmbrAIon, которые определяют правила AI-разработки этого проекта. |
| **Core** | Переиспользуемые механизмы EmbrAIon: схемы, общие roles/skills, routing contracts, validation/review mechanics, security mechanics и поведение host projections. |
| **AI host** | AI-клиент, который владеет разговором, reasoning и native tools, например Codex, GitHub Copilot или Claude Code. |
| **Host projection** | Сгенерированные host-native файлы, которые доставляют project contract в AI host. Projection — производный output, а не второй source of truth. |
| **Knowledge** | Факты проекта и документы source of truth, зарегистрированные в `.embraion/knowledge.yaml`. |
| **Project Contract Slot** | Встроенная роль знания, например architecture, source authority, compatibility, persistence, engineering workflow или specification. |
| **Policy** | Принадлежащие проекту правила source classes, privacy, review, protected paths и опционального enforcement. |
| **Canonical source/path** | Контент, который считается авторитетной правдой проекта для своей области. |
| **Protected source/path** | Контент, который AI не должен изменять без явно разрешённого проектом пути/процесса. |
| **Generated source/path** | Производный output, который обычно следует регенерировать из владельца, а не редактировать как каноническую правду проекта. |
| **External source/path** | Контент, владельцем которого project contract не является, например vendored или upstream material. |
| **Route class** | Стабильное описание типа работы/риска, например `ordinary`, `substantial` или `complex`. Это не постоянный tier модели. |
| **`host-default`** | Результат routing, при котором фактический выбор модели остаётся за текущим default/automatic поведением AI host. |
| **Deployment** | Переиспользуемый конкретный выбор model/provider, принадлежащий проекту. Это ответ на вопрос **что можно выбрать**. |
| **Routing** | Правила, определяющие, **когда** route или role должны выбрать deployment или явную host option. |
| **Execution binding** | Конфигурация проекта, описывающая, **как** разрешённый deployment может быть вызван через опциональный provider-neutral runtime EmbrAIon. |
| **Provider-neutral execution** | Опциональный путь `embraion execute`, где EmbrAIon управляет ограниченным external/API attempt loop. Обычные host-native разговоры через него не проходят. |
| **Validation profile** | Именованный набор реальных команд проекта, доказывающих, что изменение работает. |
| **Evidence** | Структурированные записи validation, review, execution или enforcement, связывающие утверждения с реальными проверками. |
| **Review** | Правила/evidence проекта для независимой или человеческой оценки изменения. |
| **Enforcement** | Детерминированные delivery/merge checks для protected paths, validation и при необходимости review. Текстовая инструкция сама по себе не является enforcement. |
| **Runtime resolution** | Разрешение точной версии EmbrAIon, закреплённой репозиторием, включая изолированный cached runtime при необходимости. |

## Четыре advanced-термина, которые чаще всего путают

| Concept | Вопрос |
| --- | --- |
| Deployment | **Что** за конкретный выбор существует? |
| Routing | **Когда** его нужно выбирать? |
| Execution binding | **Как** его можно безопасно вызвать? |
| Pricing | **Как** интерпретируется/обновляется стоимость provider? |

Точная модель описана в [Engineering Model Deep Dive](reference/engineering-model.md).
