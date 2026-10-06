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
│   ├── embraion.md
│   └── embraion-core.md
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

The `skills` component also owns `.claude/rules/embraion.md`, an unconditional entry point that asks each Thread to load orchestration and applicable `AGENTS.md` files, and `.claude/rules/embraion-core.md`, every Core rule in one unconditional rule file. Installation preserves user-owned `CLAUDE.md` and unrelated skills. Rule loading still depends on the active Claude surface and must be checked there.

From 0.18.0, Claude profile names use machine IDs such as `reviewer` rather than display titles such as `Reviewer` or `Video/CV`. Long IDs receive a bounded hashed name. Regenerate profiles and use their emitted native names; human titles remain in the instruction heading.

The routing role and native agent identity are separate. For a configured `independent-review` routing role backed by the canonical reviewer, use `--role independent-review --native-agent reviewer`. The binding preserves the routing role's eligibility and the reviewer's read-only tools. Explicit settings produce a complete `scoped-definition`; its `name` becomes `arguments.subagent_type`. For a supported `--agents` loader, key the JSON object by `name` and use the remaining definition fields as its value. The task prompt is a separate invocation input. The plan remains `executed: false`.

Every selected `critical` route now requires a nonblank `--justification`, including direct routing and dispatch. A normal API rename does not establish critical risk by itself; project policy must classify the actual impact. Existing critical callers must supply their reason when upgrading.

Claude Code supports the standard `agents` and `skills` components, plus explicitly selected `scoped-agents`. Default installs preserve the standard components. Mature repositories can adopt them independently:

```bash
embraion install --host claude-code --destination . --component skills
embraion install --host claude-code --destination . --component agents --component skills
```

## Startup scoped agents

To make an explicit route available in the desktop Thread's native Agent registry, configure `.embraion/claude-native.yaml` before starting that Thread. For a project whose existing Claude reviewer route already selects an eligible deployment:

```yaml
bindings:
  reviewer: reviewer
assignments:
  - role: reviewer
    route-class: complex
    data-class: PRIVATE
    access: review
read-policy:
  project-only: true
  deny-protected: true
```

Bindings connect routing roles to native specialist IDs; assignments declare only the eligible combinations to project. Model, effort and deployment choices remain in routing/deployments. The component rejects host-default or ineligible combinations rather than inventing a selection. Generation inspects configuration without selecting an execution route, including for critical profiles; actual critical dispatch still requires justification. For a semantic role such as `independent-review`, bind it to `reviewer` explicitly. A task class selects its declared host candidates: a Claude role override cannot turn an API candidate into a desktop assignment.

```bash
embraion framework install
embraion route --validate
embraion install --host claude-code --component scoped-agents
embraion projection verify --host claude-code --component agents --component skills --component scoped-agents
embraion claude-native install-hooks --dry-run
embraion claude-native install-hooks
embraion projection verify --host claude-code --component hooks
embraion claude-native status
embraion claude-native status --require installed,hooks
```

`--require` makes the status usable as a CI gate: it exits 1 when the projection is missing or stale or required hooks are absent. Model and effort cannot be required, because no file or hook payload proves them; see the [CLI reference](../reference/cli.md#embraion-claude-native).

Installation adds separate hash-named `.claude/agents/embraion--*.md` files and metadata in `.claude/embraion-native.json`. The usual `reviewer.md` stays model-neutral. Projection conflicts and obsolete modified files retain the same protections as other components; use a reviewed `--prune` only for unchanged owned obsolete definitions. The `embraion--` prefix is reserved for this projection: with `scoped-agents` selected, `projection diff` and `projection verify` report any `.claude/agents/embraion--*.md` file the current projection would not produce as `obsolete-modified`, even without a local ownership ledger (for example in a clean clone or CI). Such files lack ownership evidence, so `--prune` keeps them; delete them after review.

Start a **new working Thread** attached to this checkout after setup. Each local/cloud checkout needs its own version and projection verification. An old worktree retains its old framework pin; a global launcher update does not migrate it. Resolve each assignment through the project resolver. Dispatch discovers the configured native binding. Invoke the returned hash-named type in the active registry without a model override. File presence is not registry loading. An absent or stale type remains a handoff limitation; separate CLI authentication is not a prerequisite for a correctly loaded native Agent.

## Native hooks and evidence

Hook installation is explicit and merges only EmbrAIon's exact entries into `.claude/settings.json`, preserving unrelated settings and hooks. It refuses malformed settings or a changed conflicting entry, even with `--force`. `install-hooks` installs the `hooks` projection component (`embraion install --host claude-code --component hooks`), which records the managed entries in the projection ledger, so `projection verify --host claude-code --component hooks` reports a missing or changed entry as drift. A managed entry from an earlier release that is still unchanged is replaced on the next installation. Host trust, hook support and a working `embraion` command still need verification in each surface.

The PreToolUse guard refuses configured base-agent calls, stale scoped types, invocation model overrides, and explicit isolation/resume settings whose definition propagation or reuse is unverified. It verifies definition identity and bytes; it does not prove fresh task classification or critical justification, which still require canonical dispatch before invocation. With `read-policy`, it also confines scoped read/search tools to the project and rejects protected source paths or searches that can traverse them. This uses the project's current policy patterns; it does not change source classification or make unclassified data safe. It does not sandbox parent tools, arbitrary agents or shell access. The parent must still follow source-authority instructions and pass eligible bounded context.

PostToolUse and SubagentStop record bounded session/agent identity and optional reported `effort.level` into ignored local state. Claude Code 2.1.277 early-access declarations permit that field; documented examples omit it, and delivery by an installed desktop/cloud build requires a real host check. The public observer accepts arbitrary JSON, so records are marked `unverified-command-input`. `claude-native status` reports installation, recorded callbacks and advisory `reported-effort` comparisons; `execution`, effective `effort` and `model` remain `unverified`; `callbacks: recorded` only identifies accepted metadata. A recorded callback does not prove assignment completion or host origin. Trusted response or supported native-step evidence is still required; session init null effort and an agent's own statements do not prove settings. No hook checks can undo a model call that already occurred. No private tool inputs, prompts, answers or transcript contents are recorded.

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

The [0.19.1 Windows check report](claude-code-check-0.19.1.md) records maintainer-supplied observations from two local Desktop worktree sessions and their evidence limits.

## Further configuration

See [Configure with Your AI Client](../configuration/ai-hosts.md) for conversational routing/configuration examples, and [Adopt an Existing Repository](../getting-started/existing-repository.md) for selective adoption.

Hook events that include `cwd` select that working tree for policy checks and metadata storage, even when the desktop launches the hook command from the main checkout. Relative read/search paths are interpreted from the event directory, including nested directories; policy stays rooted in the working tree. Run `claude-native status` in that same working tree. Invalid event paths or a working-tree version or artifact lock that differs from the active cached runtime are rejected; legacy events without `cwd` retain process-directory behavior. Metadata remains advisory and does not prove effective model or effort.
