# GitHub Copilot

## What it is

The GitHub Copilot adapter projects EmbrAIon Core/project agents and reusable skills into Copilot's repository-native locations.

## Install

```bash
embraion install --host copilot --destination .
```

## Generated structure

```text
.github/
├── agents/
│   ├── analyst.agent.md
│   ├── architect.agent.md
│   ├── reviewer.agent.md
│   └── ...
└── skills/
    ├── implementation/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files are projections. Project policy, knowledge, validation, agents, and optional routing overrides remain canonical under `.embraion/`.

## Routing

GitHub Copilot remains authoritative for the models and options available to the current account. EmbrAIon does not maintain a Copilot model catalog.

Optional selectors/options belong only under `overrides.copilot` in `.embraion/routing.yaml`.

Inspect resolution with:

```bash
embraion route --host copilot --route-class substantial --data PRIVATE
```

## Selective adoption

Copilot supports the `agents` and `skills` projection components. Select only what the repository wants EmbrAIon to own:

```bash
embraion install --host copilot --destination . --component skills
embraion install --host copilot --destination . --component agents --component skills
```

Preview before writing:

```bash
embraion projection diff --host copilot --destination .
```

## Verify

```bash
embraion doctor
embraion status
```

Use `embraion projection diff --host copilot --destination .` before reinstalling into a repository that already owns `.github/` AI configuration.

## Further configuration

See [Configure with Your AI Client](../configuration/ai-hosts.md) for conversational routing/configuration examples, and [Adopt an Existing Repository](../getting-started/existing-repository.md) for selective adoption.
