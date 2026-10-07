<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System by GORYNED" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.ru.md">Русский</a>
</p>

# EmbrAIon

**AI-First Engineering System [by GORYNED](https://goryned.com)**

**EmbrAIon keeps the rules for AI-assisted engineering with the repository — project knowledge, protected paths, routing, validation, review, and evidence — instead of scattering them across prompts and AI-client settings.**

Use the same project contract with Codex, GitHub Copilot, Claude Code, or a host-neutral Portable bundle.

## Why use it?

Use EmbrAIon when:

- important project rules no longer fit in one prompt;
- several AI clients need to follow the same repository contract;
- protected paths and validation need deterministic checks rather than prose alone;
- architecture knowledge and policy must survive model/session changes;
- model selection, review, and evidence should be reusable project settings instead of ad hoc choices.

> **Mental model:** EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.

EmbrAIon does **not** replace the AI client, intercept every prompt, or run inside the finished product.

## Quick start

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
```

Open the repository in your AI client and ask:

> Configure EmbrAIon for this project.

Lead uses the canonical Core Project Bootstrap skill to inspect existing truth, bind knowledge, preserve safety policy, and discover real validation. Routing stays optional. See [Project Bootstrap](docs/configuration/bootstrap.md).

Then work normally:

> Fix the retry flow and add regression coverage.

Use `copilot` or `claude-code` instead of `codex` when that is your host.

Lead reads the project contract, selects specialists automatically, classifies each assignment independently, resolves project routing, and applies configured model/effort through supported native host capabilities. It collects proportional validation and review, integrates results, and retains final authority.

Want to experiment first? Use the [Five-Minute Sandbox](docs/getting-started/playground.md).

## Before / after

```text
Before
prompts + AGENTS.md + host settings + CI + tribal knowledge
                         ↓
                      drift

After
                 .embraion/
                     ↓
      one repository-owned project contract
                     ↓
      host projections + validation + review
```

## Documentation

Canonical site: **https://embraion.goryned.com/**

Recommended onboarding:

1. [Why EmbrAIon?](docs/getting-started/what-is-embraion.md)
2. [EmbrAIon in 60 Seconds](docs/getting-started/in-60-seconds.md)
3. [Five-Minute Sandbox](docs/getting-started/playground.md)
4. [Installation](docs/getting-started/installation.md)
5. Choose the repository path:
   - [Add EmbrAIon to a Project](docs/getting-started/first-project.md) for a new or simple repository.
   - [Adopt an Existing Repository](docs/getting-started/existing-repository.md) for a mature repository with existing AI-client configuration.
6. [Your First AI Task](docs/getting-started/first-ai-task.md)
7. [How It Works](docs/getting-started/how-it-works.md)

Need a term or a direct answer? See the [Glossary](docs/glossary.md), [FAQ](docs/faq.md), and [Security & Data Flow](docs/security-data-flow.md).

For engineers, see [Engineering Model Deep Dive](docs/reference/engineering-model.md).

## New in 0.29

- [Architecture decision records](docs/configuration/decisions.md) are part of the workflow: the optional `decisions` contract slot and `.embraion/decisions.yaml` declare which changes are architectural, `embraion decisions check` (also run by `embraion check --base-ref`) requires a record or a `Decision-Waiver`, and `embraion adr new` scaffolds the next numbered record.

## New in 0.28

- [`embraion check`](docs/reference/cli.md#embraion-check) runs every check the project configuration selects, so [consumer CI](docs/reference/runtime-version-resolution.md#consumer-ci) needs one step; `projection.<host>.components` in [policy](docs/configuration/policy.md) declare the projections it verifies.
- Optional [`privacy.sources`](docs/configuration/policy.md) gives each source ID its data class, and execution requests that name a source fail closed below that class.

## New in 0.27

- [Consumer CI](docs/reference/runtime-version-resolution.md#consumer-ci) can install the pinned release with the reusable `GORYNED/EmbrAIon/actions/setup` action, and `embraion framework pin` prints the exact pin; [enforcement](docs/guides/enforcement.md) generates workflows that use the action.
- Projections carry project-owned skills from [`.embraion/skills/`](docs/configuration/project-files.md), specialist triggers and outputs, Core links pinned to the release tag, and an opt-in [Claude Code hooks](docs/hosts/claude-code.md#native-hooks-and-evidence) component; files recorded in projection ledgers count as generated sources.
- [Declared integrations](docs/security.md#declared-integrations) in `.embraion/integrations.yaml` report drift between expected and observed MCP servers.
- `embraion validate` checks the project's own `.embraion/*.yaml`, and `claude-native status --require` turns the Claude Code projection state into a CI gate.
- [Merge mode](docs/configuration/policy.md#merge-mode) `owner-permission` lets an agent merge with the owner's explicit permission; [validation profiles](docs/configuration/validation.md#timeouts) gain per-command timeouts, full logs and process-tree containment.

## New in 0.26

- Core rules are projected into each host's startup instructions: Claude Code and Copilot rule files and the managed Codex instructions. Whether a surface applies them is checked on that surface; see [Claude Code](docs/hosts/claude-code.md) and [Copilot](docs/hosts/copilot.md).
- [API execution](docs/configuration/execution.md#context-envelopes) builds fail-closed context envelopes from committed files, records each attempt in a local ledger that feeds candidate health, and checks readiness without a provider call.
- [Code organization](docs/configuration/organization.md#filenames) checks file names and can require a `.meta` for every file under its Unity roots, with orphan detection.
- [Security scan](docs/security.md#scan-findings) finds provider-prefixed tokens and home-directory paths, and `--all-files` extends the precise checks to source code.
- [Policy ceilings](docs/configuration/policy.md#policy-ceilings) also bound host routing overrides, and the [report contract](docs/configuration/report.md) can require a Workers summary and a compare link.

## New in 0.20

- [Engineering skills](docs/guides/engineering-skills.md) and [live skill evaluations](docs/guides/skill-evals.md) cover repeatable procedures and fresh host-run comparisons. A recorded eval remains distinct from a live run.
- [Code organization](docs/configuration/organization.md) checks changed files incrementally; existing debt does not waive new violations.
- [Task checkpoints](docs/guides/task-continuity.md) and [knowledge maintenance](docs/guides/knowledge-maintenance.md) track local freshness with hashes and explicit baselines. They do not approve review or rewrite project documents.
- [External capabilities](docs/configuration/capabilities.md) record independently installed host capabilities. A declaration does not install a plugin or prove host loading or execution.

## Examples

- [Minimal](examples/minimal/) — smallest complete project overlay.
- [Python](examples/python/) — ordinary Python app + EmbrAIon engineering layer.
- [Unity](examples/unity/) — Unity 6 project with EmbrAIon outside the game runtime.

## Status

EmbrAIon is pre-1.0. Projects pin exact published framework versions so upgrades remain intentional.

## License and brand

Source code and documentation are licensed under the [MIT License](LICENSE) except where explicitly stated otherwise. The **EmbrAIon** and **GORYNED** names, logos, wordmarks, visual marks, and files under `brand/assets/` are governed separately by [TRADEMARKS.md](TRADEMARKS.md).

---

<sub>Last updated: 2026-10-07 02:00 UTC</sub>
