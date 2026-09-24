# Routing (Маршрутизация)

Маршрутизация в EmbrAIon полностью агностична к моделям.

Core классифицирует работу по классам `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex` и `critical`. Эти классы описывают тип работы и риск, а не мощность, стоимость, провайдера или конкретную модель.

Если проект не задаёт override, выбранный AI-клиент использует собственный default/automatic выбор модели. При необходимости проект может сохранить произвольные host-specific значения `model`, `effort` и `options` в `.embraion/project.yaml` → `routing.overrides`.

Пользователь может просто попросить ИИ в проекте настроить EmbrAIon под доступные ему модели. Установленный skill `routing-configuration` объясняет ИИ, куда записывать override и какие правила нельзя ослаблять.

EmbrAIon не содержит канонического каталога моделей. Privacy, access, ownership, validation и review остаются независимыми от выбора модели.
