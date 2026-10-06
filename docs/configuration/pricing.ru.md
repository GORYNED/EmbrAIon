# Pricing и стоимость

EmbrAIon может детерминированно рассчитывать provider cost, не загружая live pricing при каждом execution.

Конкретные pricing facts принадлежат проекту. EmbrAIon владеет generic refresh, validation, snapshot, staleness и calculation mechanics.

## Почему pricing принадлежит проекту

Provider names, SKU, rates, applicability dates, discounts и official source pages меняются со временем и не являются стабильными Core capabilities.

Проект, которому нужно cost evidence, объявляет:

- approved official pricing source URLs;
- provider parser adapter;
- currency;
- freshness window;
- deployment/SKU mappings;
- effective/valid-through dates;
- usage field patterns и special rate schedules.

Эти факты находятся в `.embraion/pricing.yaml`.

## Refresh выполняется явно

Pricing никогда не обновляется молча во время execution.

```bash
embraion pricing refresh
```

Обновить конкретный approved source:

```bash
embraion pricing refresh --source openai
```

Configured source list — allowlist. CLI не принимает произвольные refresh URLs из командной строки.

## Валидированный локальный snapshot

```text
pricing.yaml
    ↓
explicit official-source refresh
    ↓
validate all selected data
    ↓
atomic snapshot replacement
    ↓
offline status / execution-time cost calculation
```

Failed refresh не уничтожает последний валидированный snapshot.

```bash
embraion pricing status
embraion pricing status --json
embraion pricing status --fail-on-stale
```

## Unknown не равно zero

EmbrAIon различает:

- known calculated cost;
- provider-reported exact cost;
- adapter-normalized cost;
- subscription/quota semantics;
- unknown pricing;
- unknown из-за stale pricing;
- unknown из-за недоказанных usage semantics.

Недостающая или неоднозначная информация **не превращается в `0`**.

Ноль — финансовое утверждение, unknown — состояние evidence.

## Приоритет cost evidence

Более сильное evidence имеет приоритет над snapshot calculation:

```text
provider exact cost
      ↓
adapter-normalized cost
      ↓
validated snapshot calculation
      ↓
unknown
```

Returned state остаётся явным, чтобы проект мог отличить источник суммы.

## Usage semantics

Разные providers/adapters могут сообщать token counters с разной overlap semantics.

Cached input может уже входить в total input или быть дополнительным count. Reasoning tokens могут пересекаться с output totals.

EmbrAIon не угадывает.

Для snapshot calculation требуются явные semantics:

```json
{
  "input": "inclusive",
  "output": "disjoint"
}
```

Если semantics не доказаны, snapshot-derived cost остаётся unknown.

## Version-tied usage evidence

Проект с LiteLLM execution adapter может привязать reviewed usage-semantics evidence:

```yaml
usageSemanticsEvidence:
  path: .embraion/usage-evidence/example.json
  sha256: <reviewed-digest>
```

Evidence сверяется с configured adapter/provider/selector и running adapter version. Expired, mismatched или malformed evidence отклоняется для cost derivation вместо догадки.

Synthetic fixtures полезны для tests, но не доказывают реальные provider billing semantics.

## Форма pricing configuration

Следующий пример — **иллюстрация schema**, а не готовая provider fixture. URL, SKU и extraction patterns должны быть заменены проверенными значениями approved official source.

```yaml
schemaVersion: 1

sources:
  example:
    url: https://example.com/pricing
    adapter: openai
    currency: USD
    freshnessDays: 30
    skus:
      analysis-api:
        sku: example-model
        patterns:
          input: "..."
          output: "..."
```

Текущие parser adapters включают OpenAI, Anthropic, Gemini и DeepSeek pricing pages. Concrete URL, SKU, patterns, dates и rates принадлежат проекту.

## Расчёт без сети

`embraion pricing calculate` читает JSON request из stdin и использует только validated local snapshot плюс переданное usage/cost evidence.

Точный input contract — в [CLI reference](../reference/cli.md#embraion-pricing).

## Проверка configured rates

`embraion pricing verify --fixtures pricing-fixtures.yaml` прогоняет reviewed usage fixtures через тот же offline calculation и сравнивает state, currency и amount как exact decimals:

```yaml
schemaVersion: 1
fixtures:
  - id: analysis-basic
    deployment: analysis-api
    usage: {inputTokens: 1000000, outputTokens: 1000}
    usageSemantics: disjoint
    atUtc: "2026-10-01T12:00:00Z"
    expect: {state: snapshot-computed, amount: "1.004", currency: USD}
```

Amounts задаются decimal strings в кавычках, не float. Mismatch завершает команду с кодом 1, поэтому проект может проверять snapshot refresh своими reviewed fixtures.

## Связанные страницы

- [Как работает EmbrAIon](../getting-started/how-it-works.md)
- [Execution и провайдеры](execution.md)
- [Deployments проекта](deployments.md)
- [Безопасность](../security.md)
