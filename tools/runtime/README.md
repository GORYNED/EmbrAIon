# Runtime

Runtime owns provider-neutral routing decisions, dispatch planning, normalized session state, and privacy-safe operational telemetry.

Current executable capabilities:

```bash
embraion route --host codex --route-class strong --data PRIVATE

embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class economy-write \
  --data PRIVATE \
  --access write \
  --owned-path src/**

embraion session start ...
embraion session show
embraion session set ...
```

Writable dispatch planning requires explicit owned paths and refuses the stable `main`/`master` branch.

EmbrAIon resolves policy and produces host-specific agent projections. Actual model execution occurs through the selected host/client rather than through a second hidden orchestration service.

Runtime telemetry is append-only under `.embraion/state/telemetry.jsonl` and intentionally excludes prompt content, source excerpts, diffs, raw reasoning, and credential values.

<sub>Last updated: 2026-09-23 20:20 UTC</sub>
