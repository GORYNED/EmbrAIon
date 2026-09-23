# Project Overlay

Подключаемый репозиторий соединяется с EmbrAIon через `.embraion/project.yaml`.

Overlay определяет:

- зафиксированную версию EmbrAIon;
- identity проекта;
- расположение project knowledge;
- project-specific agents;
- external capabilities.

Project overlays могут добавлять более строгие правила, но не должны скрытно ослаблять hard gates Core.

Сам project repository остаётся canonical source для product specification, architecture, compatibility contracts, validation evidence и domain semantics.
