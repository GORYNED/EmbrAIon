# copilot native orchestration

Apply the assignment routing contract in the [canonical orchestration skill](../../core/skills/orchestration/SKILL.md). This adapter supplies native mechanisms and capability limits; Core owns classification, resolution, reuse, evidence, and handoff rules. Keep generated specialist profiles model-neutral and concrete deployment choices in `.embraion/`.

## Native assignment settings

CLI native preparation translates project `options.modelPolicy` only as `required`; `preferred` cannot weaken mandatory project selection. For VS Code, `--verified-native-field reasoning-effort` enables definition translation only with retained installed-version/schema evidence. Unknown native option keys remain limitations rather than being discarded.

Identify the surface and inspect its installed schema; Copilot CLI, VS Code, and cloud agents have different controls.

- **CLI:** custom-agent definitions support `model`, ordered `models`, `modelPolicy`, and `reasoningEffort`; `models` takes precedence over `model`. Verified `task` or `session.startSubagent` schemas may expose per-call model/effort settings. Precedence is call overrides, `settings.subagents`, agent definition, then parent. Use `modelPolicy: required` when supported for a mandatory model; `preferred` permits inheritance when the selection is incompatible. Auto mode can force parent inheritance, so verify its behavior before dispatch.
- **VS Code:** subagent invocation can select a model; custom-agent definitions accept a model string or ordered array. A higher-cost model tier than the parent may be refused. Development-source customization documents `reasoning-effort`, but support must be proven by the installed version/schema; do not assume the CLI's `reasoningEffort` field works here. Without that proof an explicit effort is a capability limitation.
- **Cloud/general custom agents:** the published configuration supports `model`; CLI-only effort, policy, and ordered-model fields are not established for this surface. Unknown controls require capability proof or a supported handoff.

Prepare assignment-specific definition/settings overrides when the verified surface requires them; do not persist a route choice into a reusable static role profile. Confirm precedence and the effective choice: mandatory route settings cannot silently inherit, substitute another candidate, or be capped. An ordered native model list is usable only when it agrees with the resolved project selection/fallback policy. Scope settings to the assignment instead of changing unrelated session or project defaults.

Checked 2026-09-29 against official [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), [VS Code subagents](https://code.visualstudio.com/docs/agents/run/subagents), [VS Code development customization source](https://github.com/microsoft/vscode/blob/main/extensions/copilot/assets/prompts/skills/agent-customization/references/agents.md), and [custom-agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration). Runtime schema and effective-setting evidence qualify these capabilities.
