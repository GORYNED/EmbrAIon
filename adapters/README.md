# Adapters

Adapters translate canonical Core behavior into concrete execution surfaces.

Current adapter families:

- `codex/` — Codex configuration, agents, and skills projection;
- `copilot/` — GitHub Copilot custom-agent and skills projection;
- `claude-code/` — Claude Code agent and skills projection;
- `portable/` — host-neutral installable capability bundle;
- `providers/` — optional transport/provider integration surfaces.

Portable is not another AI host. It is an interchange/package representation for Core capabilities.

Adapters do not own a global model catalog. Model selectors are host-owned values: the host chooses its own default when no project override exists, and project overrides may pass arbitrary host-understood selectors/options without teaching EmbrAIon Core about individual models.

<sub>Last updated: 2026-09-24 04:40 UTC</sub>
