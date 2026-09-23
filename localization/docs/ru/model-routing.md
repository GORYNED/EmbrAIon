# Маршрутизация моделей

Routing — capability первого класса в EmbrAIon.

Canonical routing policy определяет, как характеристики задачи преобразуются в выбор model/provider, reasoning effort, execution permissions, escalation и требования review.

Provider adapters реализуют mechanics вызова. Они не владеют canonical decision policy.

Подробные routing contracts версионируются отдельно по мере развития framework.
