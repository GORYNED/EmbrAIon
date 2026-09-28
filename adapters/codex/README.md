# Codex

The Codex adapter projects EmbrAIon configuration, agents, and skills into Codex-native files.

The `config` component projects root-level Codex `developer_instructions` from the [canonical Lead role](../../core/agents/lead.yaml) plus [Codex orchestration guidance](orchestration.md). Users ask for ordinary engineering outcomes; Lead selects useful specialists proactively, handles trivial work directly, bounds assignments, parallelizes independent work safely, collects fresh proportional validation, and obtains independent read-only review when policy requires it. Lead integrates results and retains final acceptance authority. Empty project `agents: []` preserves Core roles and orchestration.

The `skills` component includes the canonical [orchestration skill](../../core/skills/orchestration/SKILL.md) with the generated Core Lead contract. Copilot, Claude Code, and Portable projections receive equivalent skill-level guidance; each host selects skill loading. Codex root instructions add guidance without requiring skill selection.

Config merge uses `tomlkit` to preserve user TOML and updates only the named orchestration subsection inside the parsed root `developer_instructions` string, between `# >>> EmbrAIon managed: orchestration` and `# <<< EmbrAIon managed: orchestration`. User instruction text outside the subsection is preserved. The existing `[agents]` comment markers manage `enabled = true` and `max_concurrent_threads_per_session = 3`; unrelated options, comments, tables, and user `default_subagent_model` / `default_subagent_reasoning_effort` remain intact. Invalid TOML or malformed, duplicate, or ambiguous markers fail closed even with `--force`. Whole-file replacement remains an explicit alternative.

Core agent access is projected through Codex-native `sandbox_mode`: `read-only` remains read-only and `workspace-write` remains workspace-write. Codex or organization policy may further restrict access but EmbrAIon does not widen it.

EmbrAIon does not maintain a Codex model catalog. When a project does not define a routing override, Codex keeps ownership of its default/automatic model selection. When a project does define an override, EmbrAIon treats the model selector, effort, and optional host settings as opaque Codex-owned values.

Lead queries the project resolver for each classified assignment before native spawn and applies explicit choices through supported spawn parameters. Generated specialist files omit model/effort overrides because Codex role-file overrides take precedence over explicit spawn choices; host-default uses subagent defaults or inheritance. Static TOML cannot run the resolver per spawn. Trusted project configuration, native capabilities, permissions, and higher-priority instructions qualify this guidance; it does not deterministically guarantee orchestration or replace executable validation/review gates. Unsupported required choices must be reported and resolved before dispatch. See the official [config reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Canonical role, complexity, access, privacy, validation, and review policy remains in Core.

<sub>Last updated: 2026-09-28 21:59 UTC</sub>
