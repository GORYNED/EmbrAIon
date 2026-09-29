# Codex

The Codex adapter projects EmbrAIon configuration, agents, and skills into Codex-native files.

The `config` component projects root-level Codex `developer_instructions` from the [canonical Lead role](../../core/agents/lead.yaml) plus [Codex orchestration guidance](orchestration.md). Users ask for ordinary engineering outcomes; Lead selects useful specialists proactively, handles trivial work directly, bounds assignments, parallelizes independent work safely, collects fresh proportional validation, and obtains independent read-only review when policy requires it. Lead integrates results and retains final acceptance authority. Empty project `agents: []` preserves Core roles and orchestration.

The `skills` component includes the canonical [orchestration skill](../../core/skills/orchestration/SKILL.md) with the generated Core Lead contract; the Codex skill projection also includes this adapter's native routing and dispatch guidance. Copilot and Claude Code skill projections include their own native guidance alongside the Core contract; Portable carries only the canonical contract. Each host selects skill loading. Codex root instructions also carry the adapter guidance without requiring skill selection.

Config merge uses `tomlkit` to preserve user TOML and updates only the named orchestration subsection inside the parsed root `developer_instructions` string, between `# >>> EmbrAIon managed: orchestration` and `# <<< EmbrAIon managed: orchestration`. User instruction text outside the subsection is preserved. The existing `[agents]` comment markers manage `enabled = true` and `max_concurrent_threads_per_session = 3`; unrelated options, comments, tables, and user `default_subagent_model` / `default_subagent_reasoning_effort` remain intact. Invalid TOML or malformed, duplicate, or ambiguous markers fail closed even with `--force`. Whole-file replacement remains an explicit alternative.

Core agent access is projected through Codex-native `sandbox_mode`: `read-only` remains read-only and `workspace-write` remains workspace-write. Codex or organization policy may further restrict access but EmbrAIon does not widen it.

EmbrAIon does not maintain a Codex model catalog. When a project does not define a routing override, Codex keeps ownership of its default/automatic model selection. When a project does define an override, EmbrAIon treats the model selector, effort, and optional host settings as opaque Codex-owned values.

Assignment routing follows the [canonical orchestration contract](../../core/skills/orchestration/SKILL.md). The [Codex native guidance](orchestration.md) covers tool-schema checks, spawn/fork controls, role-file precedence, and follow-up limitations. Static profiles remain model-neutral; route preparation is not execution evidence.

Canonical role, complexity, access, privacy, validation, and review policy remains in Core.

The opt-in `embraion dispatch --native-surface` planner supports `codex-native` for this adapter and accepts `--task-class` for configured assignment routing. Its `native-plan` contains `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. A `prepared` result is static translation; `handoff-required` needs a supported native loading/session step, and `capability-limitation` prevents invocation until resolved. None proves native execution. Unsupported native options block planning until their application is established.

<sub>Last updated: 2026-09-29 01:14 UTC</sub>
