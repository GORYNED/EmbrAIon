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
```

`status` reports detected host projections. Use `embraion projection diff --host codex --destination .` whenever you want to inspect ownership-aware changes before reinstalling.

## Further configuration

See [Configure with Your AI Client](../configuration/ai-hosts.md) for conversational routing/configuration examples, and [Adopt an Existing Repository](../getting-started/existing-repository.md) for conflict-safe adoption.
