# Примеры использования

EmbrAIon поставляется с тремя публичными reference projects, показывающими, как engineering system сочетается с реальными формами репозитория.

| Пример | Что показывает |
| --- | --- |
| Minimal | Минимальный полный project overlay и project knowledge |
| Python | Обычный application code и tests с EmbrAIon вокруг него |
| Unity | Runnable Unity 6 project с обычной C# architecture и EmbrAIon integration |

CI копирует примеры во временные каталоги и выполняет реальный consuming-project lifecycle. Generated host projections создаются заново и не считаются canonical source.

Выберите [Minimal](minimal.md), [Python](python.md) или [Unity](unity.md).

Базовые примеры намеренно маленькие и не имитируют платные provider calls. Для advanced runtime используйте [Execution и провайдеры](../configuration/execution.md) и [Pricing и стоимость](../configuration/pricing.md).
