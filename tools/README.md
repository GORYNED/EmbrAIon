# Tools

Deterministic executable operations belong in `tools/`.

Current ownership boundaries:

- `runtime/` — provider-neutral orchestration and normalized session state;
- `learning/` — privacy-safe learning candidates and promotion support;
- `security/` — AI infrastructure security inspection;
- `mcp/` — MCP inventory, normalization, and drift inspection;
- `worktree/` — safe isolated-task lifecycle and cleanup;
- `validation/` — deterministic validation;
- `sync/` — projections and catalog synchronization;
- `doctor/` — diagnostics and integrity inspection;
- `install/` — installation and update;
- `cli/` — user-facing command surface.

Tools execute policy; they do not silently redefine Core policy.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
