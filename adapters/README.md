# Adapters

Adapters translate Core policy into concrete host and provider behavior.

Current adapter families:

- `agent-plugin/` — portable installable package projection;
- `codex/` — Codex model catalog and native route mapping;
- `copilot/` — GitHub Copilot model catalog and advisory route mapping;
- `claude-code/` — Claude Code model catalog and advisory route mapping;
- `providers/` — direct provider catalogs and transport integration.

`agent-plugin/` is not another model host. It is a packaging adapter that turns canonical EmbrAIon capabilities into a portable installable agent bundle while keeping Core as the source of truth.

Model facts live here, not in Core. Generated adapter/package output is never the canonical policy source.

<sub>Last updated: 2026-09-23 19:58 UTC</sub>
