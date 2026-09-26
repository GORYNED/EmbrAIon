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
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files are projections. Project policy, knowledge, validation, agents, and optional routing overrides remain canonical under `.embraion/`.

## Config ownership

Whole-file replacement remains the default for the `config` component:

```bash
embraion install --host codex --destination . --component config
```

Mature repositories can instead let EmbrAIon manage only its required `[agents]` settings while preserving project-owned Codex configuration such as MCP servers or additional agent defaults:

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

Merge mode writes a marked EmbrAIon-managed block inside `[agents]`, preserves other `[agents]` keys and non-managed TOML tables, and fails closed on invalid TOML or ambiguous managed markers. `--force` does not bypass an unsafe merge; use whole-file `replace` mode only when replacement is explicitly intended.

## Routing

Codex remains authoritative for its available models and automatic/default model selection. Without a project override, EmbrAIon resolves routing to `host-default`.

Optional Codex model, effort, or host-specific settings belong only under `overrides.codex` in `.embraion/routing.yaml`.

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
