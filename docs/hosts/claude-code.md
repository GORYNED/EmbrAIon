# Claude Code

## Project Bootstrap

The projected canonical Core `project-bootstrap` skill supports “Configure EmbrAIon for this project.” Install the `skills` component and use it in the active host session; trust, permissions and host-controlled skill loading apply. Lead inspects repository truth, preserves settings, discovers real validation, and keeps routing optional. See [Project Bootstrap](../configuration/bootstrap.md).

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
    ├── orchestration/
    ├── project-bootstrap/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files are projections. Project policy, knowledge, validation, agents, and optional routing overrides remain canonical under `.embraion/`.

## Routing

Apply the [canonical assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) before every new or reused assignment. Core owns classification, resolution, reuse, evidence, and cross-host handoff with fresh privacy/access checks; the [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/claude-code/orchestration.md) owns host mechanisms. Concrete deployment choices belong in `.embraion/`; generated specialist profiles remain model-neutral.

Inspect current `Agent` or older `Task` schema for per-call `model`. Native `.claude/agents/*.md` or `--agents` JSON definitions support `model` and `effort`; per-call Agent effort is not established. Explicit effort requires a loaded, selected assignment-specific native definition or supported handoff with verified settings. Normal model precedence is invocation, definition, `CLAUDE_CODE_SUBAGENT_MODEL`, then parent; force-mode environment settings can supersede it. Allowlists, fork inheritance, `CLAUDE_CODE_EFFORT_LEVEL`, and model-specific effort caps may alter the result.

Mandatory settings cannot silently inherit, substitute, or be capped. Unknown surfaces, schemas, or options are capability limitations to resolve under Core. Documentation checked 2026-09-29; official sources are linked in the native adapter. Verify installed schema, precedence, and effective settings at invocation. Preparing a route does not execute it.

```bash
embraion route --host claude-code --route-class substantial --data PRIVATE
```

The opt-in `embraion dispatch --native-surface` planner supports `claude-agent`; `--task-class` selects configured assignment routing. Its `native-plan` includes `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. `prepared` means static translation; `handoff-required` needs a native loading/session step, and `capability-limitation` blocks invocation until resolved. Active schema, effective configuration, and eligibility still need verification.

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
