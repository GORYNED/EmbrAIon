# Model Routing

Routing is a first-class EmbrAIon capability.

Core routing decides how task characteristics map to a provider-neutral route class, data eligibility, execution permissions, escalation, and review expectations.

Current CLI route classes include:

- `economy-read`
- `economy-write`
- `economy`
- `strong`
- `strong-high`
- `critical`

Host adapters map those classes to concrete host/model selectors. That keeps current model names, supported efforts, pricing metadata, and provider mechanics outside canonical Core policy.

Inspect a configured route with:

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

Supported data classes are `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`. A route must remain eligible for the requested data class; host availability alone is not permission to use a provider.

A bounded execution plan can combine routing with role, access, and owned-path constraints:

```bash
embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class economy-write \
  --data PRIVATE \
  --access write \
  --owned-path "src/**"
```
