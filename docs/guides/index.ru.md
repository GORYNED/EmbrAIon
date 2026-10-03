# Использование и автоматизация

Этот раздел описывает обычный инженерный lifecycle после настройки EmbrAIon.

## Выберите путь

- **Мне нужен только ежедневный workflow:** сформулировать результат → validate → review → merge.
- **Мне нужны deterministic delivery controls:** изучить validation evidence, structured runs/review и optional merge enforcement.

## Повседневный путь

1. [Ежедневный процесс](daily-workflow.md)
2. [Валидация и evidence](../validation.md)
3. [Решение проблем](troubleshooting.md)

## Инженерные controls

- [Runs и review](runs-review.md)
- [Enforcement](enforcement.md)
- [Инженерные навыки](engineering-skills.md)
- [Живые проверки навыков](skill-evals.md)
- [Продолжение задачи](task-continuity.md)
- [Поддержка знаний](knowledge-maintenance.md)
- [Необязательные возможности Unity](unity-capabilities.md)

Проверки [организации кода](../configuration/organization.md) постепенно выявляют новые нарушения в изменённых файлах; прежний долг не служит освобождением от правил. Декларация [внешней возможности](../configuration/capabilities.md) не доказывает, что хост загрузил её или выполнил инструмент.

!!! note
    Validation и enforcement выполняют реальные проверки. Generated host instructions направляют AI-клиент, но не заменяют host-native security boundaries.
