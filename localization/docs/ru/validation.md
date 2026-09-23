# Валидация

Validation — это evidence того, что изменение framework сохраняет ожидаемые contracts.

Validation system развивается слоями:

- schema validation;
- capability-reference validation;
- adapter/projection parity;
- routing-policy validation;
- install и doctor checks;
- security и integration inventory checks;
- integration tests;
- behavioral eval comparison с подходящими baselines.

PASS должен показывать, что именно было проверено, а не просто возвращать generic success.

Behavioral improvement оценивается отдельно от deterministic correctness. Лучший aggregate eval score никогда не отменяет hard failure по security, privacy, permissions, compatibility или mutation.
