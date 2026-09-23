# План выделения framework

Framework следует отделять от существующих проектов недеструктивно.

## Последовательность

1. Провести аудит reusable и project-specific материалов.
2. Зафиксировать canonical структуру EmbrAIon.
3. Скопировать/выделить reusable capabilities upstream.
4. Где практично, временно поддерживать старые и новые пути во время parity validation.
5. Проверить parity поведения, routing, review и tooling.
6. Перевести подключаемые проекты на versioned framework.
7. Удалять legacy-дубли только после доказанной parity.

Цель — не делать разрушительных переносов до того, как границы ownership доказаны.
