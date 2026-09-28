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

The `skills` component also includes the canonical `orchestration` skill with the generated Core Lead contract. Copilot, Claude Code, and Portable projections receive the same skill-level guidance, whose loading is selected by the host. Codex's root `developer_instructions` additionally supplies guidance without relying on skill selection.

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

Codex remains authoritative for its available models and automatic/default model selection. Without a project override, EmbrAIon resolves routing to `host-default`.

Optional Codex model, effort, or host-specific settings belong only under `overrides.codex` in `.embraion/routing.yaml`.

Before each native spawn, Lead classifies the concrete assignment and queries the project resolver with its role, route class, data class, and access mode, or a configured task class. It applies explicit resolved model/effort choices through supported spawn parameters. Generated specialist files omit model/effort fields because role-file overrides would take precedence over explicit spawn choices. A `host-default` result uses Codex subagent defaults or inheritance, including preserved user defaults. Static TOML cannot query routing per spawn; if the current host cannot apply a required choice, Lead must report and resolve the limitation before dispatch. Roles never imply a fixed model or broader access.

See the official [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents) for host settings and precedence.

Inspect resolution without executing a model:

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

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
