# Codex

The Codex adapter projects EmbrAIon configuration, agents, and skills into Codex-native files.

Core agent access is projected through Codex-native `sandbox_mode`: `read-only` remains read-only and `workspace-write` remains workspace-write. Codex or organization policy may further restrict access but EmbrAIon does not widen it.

EmbrAIon does not maintain a Codex model catalog. When a project does not define a routing override, Codex keeps ownership of its default/automatic model selection. When a project does define an override, EmbrAIon treats the model selector, effort, and optional host settings as opaque Codex-owned values.

Canonical role, complexity, access, privacy, validation, and review policy remains in Core.

<sub>Last updated: 2026-09-25 17:51 UTC</sub>
