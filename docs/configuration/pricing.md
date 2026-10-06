# Pricing & Cost

EmbrAIon can calculate provider cost deterministically without fetching live pricing during every execution.

The project owns concrete pricing facts. EmbrAIon owns the generic refresh, validation, snapshot, staleness, and calculation mechanics.

## Why pricing is project-owned

Provider names, SKUs, rates, applicability dates, discounts, and official source pages change over time. They are not stable Core capabilities.

A project that needs cost evidence declares:

- approved official pricing source URLs;
- provider parser adapter;
- currency;
- freshness window;
- deployment/SKU mappings;
- effective/valid-through dates when needed;
- usage field patterns and special rate schedules.

Those facts live in `.embraion/pricing.yaml`.

## Refresh is explicit

Pricing is never fetched silently during execution.

```bash
embraion pricing refresh
```

You can refresh a selected approved source:

```bash
embraion pricing refresh --source openai
```

The configured source list is the allowlist. The CLI does not accept arbitrary refresh URLs from the command line.

## Validated local snapshot

The flow is:

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

A failed refresh does not destroy the last validated snapshot.

Inspect the current state:

```bash
embraion pricing status
embraion pricing status --json
embraion pricing status --fail-on-stale
```

## Unknown is not zero

EmbrAIon deliberately keeps these states distinct:

- known calculated cost;
- provider-reported exact cost;
- adapter-normalized cost;
- subscription/quota semantics;
- unknown pricing;
- unknown because pricing is stale;
- unknown because usage semantics are not proven.

Missing or ambiguous information is **not** converted to `0`.

That matters because zero is a financial claim, while unknown is an evidence state.

## Cost precedence

When available, stronger evidence takes precedence over snapshot calculation.

Conceptually:

```text
provider exact cost
      ↓
adapter-normalized cost
      ↓
validated snapshot calculation
      ↓
unknown
```

The exact returned state remains explicit so consuming projects can distinguish the source of the amount.

## Usage semantics

Different providers/adapters can report token counters with different overlap semantics.

For example, cached input may already be included inside total input, or it may be an additional count. Reasoning tokens may likewise overlap output totals.

EmbrAIon therefore does not guess.

Snapshot calculation requires explicit usage semantics such as:

```json
{
  "input": "inclusive",
  "output": "disjoint"
}
```

When the semantics cannot be proven, snapshot-derived cost remains unknown.

## Version-tied usage evidence

A project using the LiteLLM execution adapter can bind reviewed usage-semantics evidence:

```yaml
usageSemanticsEvidence:
  path: .embraion/usage-evidence/example.json
  sha256: <reviewed-digest>
```

The evidence is checked against the configured adapter/provider/selector and the running adapter version. Expired, mismatched, or malformed evidence is rejected for cost derivation rather than silently guessed.

Synthetic fixtures are useful for tests but do not prove real provider billing semantics.

## Pricing configuration shape

The following is a **schema illustration**, not a refresh-ready provider fixture. Replace the URL, SKU, and extraction patterns with reviewed values from an approved official source for the selected parser adapter.

A project source can look like:

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

Current parser adapters include OpenAI, Anthropic, Gemini, and DeepSeek pricing pages. The concrete URL, SKU, patterns, dates, and rates remain project-owned.

## Calculate without network access

`embraion pricing calculate` reads a JSON request from stdin and uses only the validated local snapshot plus supplied usage/cost evidence.

See the [CLI reference](../reference/cli.md#embraion-pricing) for the exact input contract.

## Verify configured rates

`embraion pricing verify --fixtures pricing-fixtures.yaml` runs reviewed usage fixtures through the same offline calculation and compares each state, currency, and amount as exact decimals:

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

Amounts are quoted decimal strings, never floats. A mismatch exits 1, so a project can gate snapshot refreshes on its own reviewed fixtures.

## Related

- [How EmbrAIon works](../getting-started/how-it-works.md)
- [Execution & providers](execution.md)
- [Project deployments](deployments.md)
- [Security](../security.md)
