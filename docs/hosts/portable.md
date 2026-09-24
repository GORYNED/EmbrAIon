# Portable

## What it is

Portable is a host-neutral capability bundle rather than another AI client. Use it when another integration needs discoverable EmbrAIon capabilities without adopting Codex-, Copilot-, or Claude-specific files.

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

## Routing

Portable carries host-neutral routing capability data, but it is not itself an execution host. The integration consuming the bundle remains responsible for model availability and execution.

Project-owned routing overrides still live in `.embraion/routing.yaml`; they do not turn Portable into a model registry.

## Selective adoption

Portable is exposed as a single `bundle` component rather than separate config/agents/skills components.

Preview the bundle before writing:

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

See [Project Configuration Files](../configuration/project-files.md) for the canonical project contract and [AI Clients](index.md) for how Portable differs from executable AI-client projections.
