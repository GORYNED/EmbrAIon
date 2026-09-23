# Runtime

Runtime owns provider-neutral routing decisions and normalized session state.

Current executable capabilities:

```bash
embraion route --host codex --route-class strong --data PRIVATE
embraion session start ...
embraion session show
embraion session set ...
```

EmbrAIon resolves policy and produces host-specific agent projections. Actual model execution occurs through the selected host/client rather than through a second hidden orchestration service.

Session records intentionally exclude prompt content, source excerpts, raw reasoning, and credential values.

<sub>Last updated: 2026-09-23 20:05 UTC</sub>
