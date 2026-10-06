# GitHub Copilot

## Project Bootstrap

The projected canonical Core `project-bootstrap` skill supports “Configure EmbrAIon for this project.” Install the `skills` component and use it in the active host session; trust, permissions and host-controlled skill loading apply. Lead inspects repository truth, preserves settings, discovers real validation, and keeps routing optional. See [Project Bootstrap](../configuration/bootstrap.md).

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
├── instructions/
│   └── embraion-core.instructions.md
└── skills/
    ├── implementation/
    ├── orchestration/
    ├── project-bootstrap/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files are projections. Project policy, knowledge, validation, agents, and optional routing overrides remain canonical under `.embraion/`.

## Delivery semantics

Generated Copilot agent profiles opt into repository instructions with `include-custom-instructions: true`. This matters when Copilot invokes a profile as a custom subagent: repository instruction files are not inherited by custom subagents by default. The host can still disable repository instructions globally, and host-level settings take precedence over the projection.

The generated `tools` field is an allowlist over tools available on the active Copilot surface. EmbrAIon can request aliases such as `read`, `search`, `edit`, and `execute`, but does not treat every requested alias as a guarantee that the host exposes a corresponding effective tool in every custom-subagent context.

The `skills` component also writes `.github/instructions/embraion-core.instructions.md` with `applyTo: "**"`, so every Core rule is offered as a path-specific repository instruction file for all paths. Whether a surface (IDE chat, CLI, the coding agent, or code review) applies such files depends on that surface and its settings; check it on the active surface.

Skills under `.github/skills/` are projected as root/session procedural capabilities. The Copilot adapter does not promise automatic skill inheritance by every custom subagent unless GitHub exposes and EmbrAIon explicitly configures such a delivery contract.

## Routing

Apply the [canonical assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) before every new or reused assignment. Core owns classification, resolution, reuse, evidence, and cross-host handoff with fresh privacy/access checks; the [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/copilot/orchestration.md) owns host mechanisms. Concrete deployment choices belong in `.embraion/`; generated specialist profiles remain model-neutral.

CLI supports definition `model`, ordered `models`, `modelPolicy`, and `reasoningEffort`, plus per-call settings where the installed `task`/`session.startSubagent` schema exposes them. Precedence is call, `settings.subagents`, definition, then parent; `models` wins over `model`. A mandatory model needs supported `required` policy; `preferred` and Auto can inherit. VS Code supports per-call model and definition model string/array, but may refuse a higher-cost tier than the parent. `reasoning-effort` needs installed-version/schema proof; CLI field names are not interchangeable. Cloud/general agents establish `model`, not the CLI-only controls.

Mandatory settings cannot silently inherit, substitute, or be capped. Unknown surfaces, schemas, or options are capability limitations to resolve under Core. Documentation checked 2026-09-29; official sources are linked in the native adapter. Verify installed schema, precedence, and effective settings at invocation. Preparing a route does not execute it.

```bash
embraion route --host copilot --route-class substantial --data PRIVATE
```

The opt-in `embraion dispatch --native-surface` planner supports `copilot-cli`, `copilot-vscode`, or `copilot-cloud`; `--task-class` selects configured assignment routing. Its `native-plan` includes `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. `prepared` means static translation; `handoff-required` needs a native loading/session step, and `capability-limitation` blocks invocation until resolved. Active schema, effective configuration, and eligibility still need verification.

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
