# Claude Code

## What it is

The Claude Code adapter projects EmbrAIon Core/project agents and reusable skills into Claude Code's repository-native files.

## Install

```bash
embraion install --host claude-code --destination .
```

## Generated structure

```text
.claude/
├── agents/
│   ├── analyst.md
│   ├── architect.md
│   ├── reviewer.md
│   └── ...
└── skills/
    ├── implementation/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files are projections. Project policy, knowledge, validation, agents, and optional routing overrides remain canonical under `.embraion/`.

## Routing

Claude Code remains authoritative for its available models and default selection. EmbrAIon does not maintain a Claude Code model catalog.

Optional selectors/options belong only under `overrides.claude-code` in `.embraion/routing.yaml`.

Inspect resolution with:

```bash
embraion route --host claude-code --route-class substantial --data PRIVATE
```

## Selective adoption

Claude Code supports the `agents` and `skills` projection components. Mature repositories can adopt them independently:

```bash
embraion install --host claude-code --destination . --component skills
embraion install --host claude-code --destination . --component agents --component skills
```

Preview before writing:

```bash
embraion projection diff --host claude-code --destination .
```

## Verify

```bash
embraion doctor
embraion status
```

Use `embraion projection diff --host claude-code --destination .` before writing when `.claude/` already contains project-owned configuration.

## Further configuration

See [Configure with Your AI Client](../configuration/ai-hosts.md) for conversational routing/configuration examples, and [Adopt an Existing Repository](../getting-started/existing-repository.md) for selective adoption.
