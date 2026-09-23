# Adapters

Adapters translate canonical Core behavior into concrete execution surfaces.

Current adapter families:

- `codex/` — Codex model catalog, routes, and generated native-agent projection;
- `copilot/` — GitHub Copilot model catalog, advisory routes, and generated custom-agent projection;
- `claude-code/` — Claude Code model catalog, advisory routes, and generated subagent projection;
- `portable/` — host-neutral installable capability bundle;
- `providers/` — direct provider catalogs and transport integration.

Portable is not another AI host. It is an interchange/package representation for Core capabilities.

Model facts live here, not in Core. Generated output is never the canonical policy source.

<sub>Last updated: 2026-09-23 20:05 UTC</sub>
