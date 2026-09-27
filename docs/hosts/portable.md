# Portable Bundle

## What it is

Portable is a **host-neutral capability bundle**, not another AI client and not a generic model/provider.

Use it when another integration needs discoverable EmbrAIon capabilities without adopting Codex-, Copilot-, or Claude-specific files.

The CLI host identifier remains `portable`.

## Install

Install the bundle into a dedicated destination:

```bash
embraion install --host portable --destination vendor/embraion
```

## Generated structure

```text
vendor/embraion/
└── embraion/
    ├── plugin.json
    ├── catalog.yaml
    ├── skills/
    ├── knowledge/
    └── routing/
```

Generated files are projections. Canonical project configuration remains under `.embraion/`.

## What Portable is for

Portable is appropriate when:

- a custom integration can consume a host-neutral capability catalog;
- a tool wants EmbrAIon skills/knowledge/routing metadata without pretending to be Codex, Copilot, or Claude Code;
- a repository wants a neutral bundle as an integration boundary.

Portable does **not** mean:

- portable installation of the EmbrAIon CLI;
- “bring your own model” by itself;
- a provider-neutral API execution engine.

For provider execution, see [Execution & providers](../configuration/execution.md).

## Routing

Portable carries host-neutral routing capability data, but it is not itself an execution host. The integration consuming the bundle remains responsible for model availability and execution.

Project-owned routing overrides still live in `.embraion/routing.yaml`; they do not turn Portable into a model registry.

## Selective adoption

Portable is exposed as a single `bundle` component rather than separate config/agents/skills components.

Preview:

```bash
embraion projection diff --host portable --destination vendor/embraion --component bundle
```

Install intentionally:

```bash
embraion install --host portable --destination vendor/embraion --component bundle
```

## Verify

```bash
embraion doctor
embraion status
```

Use `embraion projection diff --host portable --destination vendor/embraion` to inspect ownership-aware changes before reinstalling.

## Further configuration

See [Project Configuration Files](../configuration/project-files.md) for the canonical project contract and [Host Integrations](index.md) for the executable host adapters.
