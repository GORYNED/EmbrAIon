# Codex

## What it is

The Codex adapter projects EmbrAIon host configuration, Core/project agents, and reusable skills into Codex-native files.

## Install

```bash
embraion install --host codex --destination .
```

## Generated structure

```text
.codex/
├── config.toml
└── agents/
    ├── analyst.toml
    ├── architect.toml
    ├── reviewer.toml
    └── ...

.agents/
└── skills/
    ├── implementation/
    ├── orchestration/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files are projections. Project policy, knowledge, validation, agents, and optional routing overrides remain canonical under `.embraion/`.

## Ordinary engineering requests

Ask for the outcome in normal language: “Add a retry action when the connection fails.” You do not need to name Lead, request delegation, or select specialist roles. The `config` projection puts orchestration guidance in root-level Codex `developer_instructions`, derived from the [canonical Lead role](https://github.com/GORYNED/EmbrAIon/blob/main/core/agents/lead.yaml) and the [Codex orchestration adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/codex/orchestration.md).

Lead handles trivial work directly and proactively selects the smallest useful role set for work that benefits from specialists. It bounds assignments, safely parallelizes independent work, collects fresh proportional validation, and obtains independent read-only review of substantial implementation when policy requires it. Lead integrates the results and retains final acceptance authority. Empty project `agents: []` adds no specialists; Core roles and Lead orchestration remain available.

Codex must load and trust the project configuration for this guidance to apply. Host capabilities, permissions, native limits, and higher-priority instructions still govern execution. Generated instructions guide orchestration; static TOML cannot guarantee delegation or enforce validation and review by itself.

The `skills` component also includes the canonical `orchestration` skill with the generated Core Lead contract. Copilot and Claude Code skill projections include the Core contract and their own native guidance; Portable includes only the canonical contract. The host selects skill loading. Codex's root `developer_instructions` additionally supplies guidance without relying on skill selection.

## Config ownership

Whole-file replacement remains the default for the `config` component:

```bash
embraion install --host codex --destination . --component config
```

Mature repositories can instead let EmbrAIon manage its orchestration subsection and required `[agents]` settings while preserving project-owned Codex configuration such as MCP servers or additional agent defaults:

```bash
embraion projection diff \
  --host codex \
  --destination . \
  --component config \
  --config-mode merge

embraion install \
  --host codex \
  --destination . \
  --component config \
  --config-mode merge
```

Merge mode uses `tomlkit` to parse and preserve user TOML. Within the parsed root `developer_instructions` string, it creates or updates only the named subsection between `# >>> EmbrAIon managed: orchestration` and `# <<< EmbrAIon managed: orchestration`. Existing user instruction text outside that subsection is preserved. It also manages `[agents].enabled = true` and `[agents].max_concurrent_threads_per_session = 3` using the existing comment markers, preserving unrelated options, tables, comments, and user `default_subagent_model` / `default_subagent_reasoning_effort` choices. Invalid TOML or malformed, duplicated, or ambiguous managed markers fail closed even with `--force`; use whole-file `replace` only when replacement is explicitly intended.

Managed agent settings require a single explicit `[agents]` table. Inline, dotted-only, or out-of-order representations that do not provide that ownership boundary are rejected without mutation; normalize that table before using merge mode.

## Routing

Apply the [canonical assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) before every new or reused assignment. Core owns classification, resolution, reuse, evidence, and cross-host handoff with fresh privacy/access checks; the [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/codex/orchestration.md) owns host mechanisms. Concrete deployment choices belong in `.embraion/`; generated specialist profiles remain model-neutral.

On a verified `collaboration.spawn_agent` schema, map role/model/effort to `agent_type`/`model`/`reasoning_effort`, independently. Explicit model or effort requires `fork_turns='none'` or a bounded positive integer string; full-history forks cannot accept these overrides. Follow-up/message tools cannot change them. Custom role-file model/effort can override spawn settings, so inspect the loaded definition and effective settings. Tool names and fork fields are surface-specific.

Mandatory settings cannot silently inherit, substitute, or be capped. Unknown surfaces, schemas, or options are capability limitations to resolve under Core. Documentation checked 2026-09-29; official sources are linked in the native adapter. Verify installed schema, precedence, and effective settings at invocation. Preparing a route does not execute it.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

The opt-in `embraion dispatch --native-surface` planner supports `codex-native`; `--task-class` selects configured assignment routing. Its `native-plan` includes `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. `prepared` means static translation; `handoff-required` needs a native loading/session step, and `capability-limitation` blocks invocation until resolved. Active schema, effective configuration, and eligibility still need verification.

## Selective adoption

Codex supports the `config`, `agents`, and `skills` projection components. Mature repositories can adopt only the pieces they want:

```bash
embraion install --host codex --destination . --component skills
embraion install --host codex --destination . --component agents --component skills
```

Preview before writing:

```bash
embraion projection diff --host codex --destination .
```

## Verify

```bash
embraion doctor
embraion status
embraion projection verify --host codex --destination .
```

`projection verify` is the fail-closed CI form of projection comparison: it exits non-zero when any selected generated file must be created or updated, conflicts, or leaves obsolete managed output. For a partially owned Codex config, verify with the same mode used for installation:

```bash
embraion projection verify \
  --host codex \
  --destination . \
  --component config \
  --config-mode merge
```

`status` reports detected host projections. Use `projection diff` for an explanatory preview and `projection verify` for a strict gate.

## Further configuration

See [Configure with Your AI Client](../configuration/ai-hosts.md) for conversational routing/configuration examples, and [Adopt an Existing Repository](../getting-started/existing-repository.md) for conflict-safe adoption.
