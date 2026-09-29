# claude-code native orchestration

Apply the assignment routing contract in the [canonical orchestration skill](../../core/skills/orchestration/SKILL.md). This adapter supplies native mechanisms and capability limits; Core owns classification, resolution, reuse, evidence, and handoff rules. Keep generated specialist profiles model-neutral and concrete deployment choices in `.embraion/`.

## Native assignment settings

Inspect the installed `Agent` tool schema (older installations may expose `Task`). Use its supported per-call `model` field for a resolved explicit model. Current subagent definitions in `.claude/agents/*.md` or the `--agents` JSON configuration support `model` and `effort`; model selectors may be host aliases, full IDs, or `inherit`. A mandatory explicit selection must not become inheritance through an alias or fork behavior.

A per-call `effort` argument on `Agent` is not established by the published contract. Apply explicit effort through an assignment-specific native definition that is loaded and selected, or use a supported session/handoff mechanism with verified effective settings. Do not invent an `Agent` effort field or modify a reusable role definition to carry one assignment's route. A prepared definition override still requires native loading and invocation evidence.

Normal model precedence is invocation override, agent definition, `CLAUDE_CODE_SUBAGENT_MODEL`, then parent; force-mode environment configuration can supersede normal overrides. Model allowlists can substitute choices, and fork modes can inherit the parent. Verify all these controls without recording secret environment values. Effort is model-specific, and `CLAUDE_CODE_EFFORT_LEVEL` or host caps can override the requested effort. A mandatory route cannot silently accept inheritance, substitution, or capping; report a capability limitation and follow Core's supported handoff rules when the effective selection cannot be proven.

Checked 2026-09-29 against official [subagent documentation](https://code.claude.com/docs/en/sub-agents) and [model configuration](https://code.claude.com/docs/en/model-config). Installed tool/schema, loaded-definition, and effective-setting evidence are required.
