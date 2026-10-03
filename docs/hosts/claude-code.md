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
├── rules/
│   └── embraion.md
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

Inspect the installed `Agent`/`Task` schema: its `model` argument may accept only aliases, not full IDs. The planner puts explicit model and/or effort into a complete scoped definition with the role prompt, description, and tools. Load and select that definition before invoking it. Invocation overrides, environment settings, allowlists, fork inheritance, and effort caps can still change the result; verify effective settings.

Mandatory settings cannot silently inherit, substitute, or be capped. Unknown surfaces, schemas, or options are capability limitations to resolve under Core. Documentation checked 2026-09-29; official sources are linked in the native adapter. Verify installed schema, precedence, and effective settings at invocation. Preparing a route does not execute it.

```bash
embraion route --host claude-code --route-class substantial --data PRIVATE
```

The opt-in `embraion dispatch --native-surface` planner supports `claude-agent`; `--task-class` selects configured assignment routing. Its `native-plan` includes `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. `prepared` means static translation; `handoff-required` needs a native loading/session step, and `capability-limitation` blocks invocation until resolved. Active schema, effective configuration, and eligibility still need verification.

## Selective adoption

The `skills` component also owns `.claude/rules/embraion.md`, an unconditional entry point that asks each Thread to load orchestration and applicable `AGENTS.md` files. Installation preserves user-owned `CLAUDE.md` and unrelated skills. Rule loading still depends on the active Claude surface and must be checked there.

From 0.18.0, Claude profile names use machine IDs such as `reviewer` rather than display titles such as `Reviewer` or `Video/CV`. Long IDs receive a bounded hashed name. Regenerate profiles and use their emitted native names; human titles remain in the instruction heading.

The routing role and native agent identity are separate. For a configured `independent-review` routing role backed by the canonical reviewer, use `--role independent-review --native-agent reviewer`. The binding preserves the routing role's eligibility and the reviewer's read-only tools. Explicit settings produce a complete `scoped-definition`; its `name` becomes `arguments.subagent_type`. For a supported `--agents` loader, key the JSON object by `name` and use the remaining definition fields as its value. The task prompt is a separate invocation input. The plan remains `executed: false`.

Every selected `critical` route now requires a nonblank `--justification`, including direct routing and dispatch. A normal API rename does not establish critical risk by itself; project policy must classify the actual impact. Existing critical callers must supply their reason when upgrading.

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
embraion harness audit --host claude-code
```

Use `embraion projection diff --host claude-code --destination .` before writing when `.claude/` already contains project-owned configuration.

`harness audit` reports required files and missing paths. `ready` means installation only: file contents, instruction loading, effective settings, and execution are not verified by this command. A Project overview, a cloud Thread, and a local Thread can have different working directories, loaded instructions, and host capabilities. Messages sent to another Thread are not evidence that its routing changed.

For each supported desktop surface, check a new and resumed Thread: confirm the rule and scoped instructions were read; resolve a bounded review; load the returned definition; inspect the actual invocation and effective model/effort. Exercise a mismatch and confirm dispatch stops. Repeat for a local and a cloud Thread. Static tests do not replace these live checks.

The optional [Mods probe](https://github.com/GORYNED/EmbrAIon/tree/main/adapters/claude-code/mods-probe) tests registration and routing evidence in builds supporting Claude function hooks. It is not installed by `embraion install`, and requires an explicit native Agent invocation after registration. Its mock tests do not prove live loading or effective effort.

## Further configuration

See [Configure with Your AI Client](../configuration/ai-hosts.md) for conversational routing/configuration examples, and [Adopt an Existing Repository](../getting-started/existing-repository.md) for selective adoption.
