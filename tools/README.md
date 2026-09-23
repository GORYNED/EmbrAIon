# Tools

Deterministic executable operations belong in `tools/`.

Current ownership boundaries:

- `runtime/` — provider-neutral orchestration and bounded worker execution.
- `worktree/` — safe isolated-task worktree mechanics.
- `validation/` — deterministic validation.
- `sync/` — projections and catalog synchronization.
- `doctor/` — diagnostics.
- `install/` — installation and update.
- `cli/` — user-facing command surface.

Tools execute policy; they do not silently redefine Core policy.

<sub>Last updated: 2026-09-23 18:11 UTC</sub>
