# Pricing: цены и стоимость

Конкретные цены принадлежат проекту; generic-механизм refresh/snapshot/cost принадлежит EmbrAIon.

## Почему так

Provider rates, SKU, applicability dates и официальные pricing pages меняются быстрее framework.

Поэтому проект хранит их источники в `.embraion/pricing.yaml`.

## Явный refresh

```bash
embraion pricing refresh
```

Refresh выполняется только по заранее объявленным approved URLs. Во время обычного execution EmbrAIon не ходит за ценами в сеть.

## Local validated snapshot

```text
pricing.yaml
  ↓
explicit official-source refresh
  ↓
validation
  ↓
atomic snapshot replacement
  ↓
offline cost calculation
```

Неудачный refresh не уничтожает последний валидированный snapshot.

## Unknown не равно zero

EmbrAIon различает:

- known calculated cost;
- provider exact cost;
- adapter-normalized cost;
- subscription/quota;
- unknown pricing;
- stale pricing;
- unknown usage semantics.

Если данных недостаточно, результат остаётся unknown, а не превращается в `0`.

## Usage semantics

Если cached/reasoning counters могут пересекаться с input/output totals, EmbrAIon требует явного evidence и не угадывает биллинг.

Для LiteLLM это evidence может быть version-tied и проверяться по SHA-256.
