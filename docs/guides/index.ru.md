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

!!! note
    Validation и enforcement выполняют реальные проверки. Generated host instructions направляют AI-клиент, но не заменяют host-native security boundaries.
