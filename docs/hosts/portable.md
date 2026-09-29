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

Portable carries the [canonical assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md), without a native dispatch adapter, spawn tool, or model runtime. The consuming integration must verify execution-host capabilities, apply resolved settings, and provide execution evidence. Cross-host handoff requires fresh Core privacy/access checks. Concrete deployment choices remain in `.embraion/`.

The opt-in `embraion dispatch --native-surface` planner supports `portable`; `--task-class` selects configured assignment routing. Its `native-plan` includes `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. `prepared` means static translation; `handoff-required` needs a native loading/session step, and `capability-limitation` blocks invocation until resolved. Active schema, effective configuration, and eligibility still need verification. Portable always returns a capability limitation without runtime arguments.

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
