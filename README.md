<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System by GORYNED" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="localization/README.ru.md">Русский</a> ·
  <a href="localization/README.zh-CN.md">简体中文</a> ·
  <a href="localization/README.es.md">Español</a> ·
  <a href="localization/README.hi.md">हिन्दी</a>
</p>

# EmbrAIon

**AI-First Engineering System [by GORYNED](https://goryned.com)**

> Where sparks become AI-built products

EmbrAIon is a portable AI-First Engineering System for organizing AI-assisted software engineering around explicit roles, reusable skills, workflow orchestration, model routing, access control, validation, review, security, learning, and project overlays.

It is designed to sit above individual languages and frameworks. A Unity/C# project, a Python service, a web application, or another software repository can use the same Core and add only project-specific knowledge and rules.

## What EmbrAIon does

EmbrAIon separates the engineering system into independent dimensions:

- **[Agent](core/agents/)** — who is responsible: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, Steward.
- **[Skill](core/skills/)** — how a repeatable class of work is performed.
- **[Rule](core/rules/)** — what is required, forbidden, or protected.
- **[Workflow](core/workflows/)** — in what order capabilities are composed.
- **[Routing](core/routing/)** — which access profile, model tier, host, and provider may execute the work.
- **[Adapter](adapters/)** — how canonical capabilities are represented in Codex, Copilot, Claude Code, providers, or a host-neutral Portable bundle.
- **[Tool](tools/)** — deterministic executable behavior such as validation, security scanning, worktree management, synchronization, and diagnostics.
- **[Eval](evals/)** — whether AI behavior actually follows the intended engineering contract.

`core/catalog.yaml` is the discovery index. Instead of loading the entire framework for every task, EmbrAIon can load only capabilities whose triggers match the current work.

## Data classes

EmbrAIon uses three canonical data classes:

| Class | Meaning |
| --- | --- |
| `PUBLIC` | Public information that may be sent to eligible external systems |
| `PRIVATE` | Proprietary/internal project information; external use requires an explicit eligible route |
| `CONFIDENTIAL` | Highest protection level; denied externally unless a route explicitly allows it |

Unknown or ambiguous classification fails closed. Model choice never expands access or privacy eligibility.

## Supported host adapters

Current adapters:

- **[Codex](https://openai.com/codex/)** — native model catalog, model/effort route mapping, generated project agents and config.
- **[GitHub Copilot](https://github.com/features/copilot)** — advisory model catalog and generated custom-agent projection.
- **[Claude Code](https://code.claude.com/docs/en/overview)** — Claude model catalog and generated subagent projection.
- **[Portable](adapters/portable/)** — host-neutral installable capability bundle.
- **[Providers](adapters/providers/)** — direct API model catalogs for [OpenAI](https://openai.com/), [Anthropic](https://www.anthropic.com/), [Google](https://ai.google.dev/), and [DeepSeek](https://www.deepseek.com/), plus transport metadata.

Core remains model-neutral. Current model identities and host selectors live only in adapters.

## Installation

### Install once per machine

EmbrAIon is distributed through [PyPI](https://pypi.org/project/embraion/). For normal use, install the CLI once on each Windows or macOS computer with `pipx`. A source checkout or `git clone` is not required.

A regular `pip` installation is also supported when you intentionally manage the Python environment yourself, but `pipx` is the recommended CLI installation path.

#### Windows

EmbrAIon requires Python 3.11 or newer.

1. Check whether Python is already available:

```powershell
py --version
```

If `py` is unavailable or reports a version older than 3.11, install a current Python 3 release from the [official Python downloads for Windows](https://www.python.org/downloads/windows/), then reopen PowerShell.

2. Install [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html) and add its command directory to `PATH`:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

3. Close and reopen PowerShell so the updated `PATH` is loaded, then install EmbrAIon:

```powershell
pipx install embraion
```

If you deliberately use a managed Python environment instead of `pipx`, this is also supported:

```powershell
py -m pip install embraion
```

#### macOS

If [Homebrew](https://brew.sh/) is already installed, the simplest path is:

```bash
brew install pipx
pipx ensurepath
```

Open a new Terminal window, then install EmbrAIon:

```bash
pipx install embraion
```

Without Homebrew, first check Python:

```bash
python3 --version
```

If Python is missing or older than 3.11, install a current Python 3 release from the [official Python downloads for macOS](https://www.python.org/downloads/macos/). Then install `pipx`:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Open a new Terminal window and run:

```bash
pipx install embraion
```

A regular `python3 -m pip install embraion` is also supported when you manage the Python environment yourself.

#### Verify

```bash
embraion --version
embraion validate
embraion doctor
```

`embraion validate` validates the framework data bundled with the active EmbrAIon installation. `embraion doctor` also inspects the current project/worktree context, so run it from the repository you want to diagnose or from an empty test directory for an installation smoke check.

#### Upgrade

```bash
pipx upgrade embraion
```

The global `pipx` installation makes the `embraion` command available from any project on that computer. It does **not** automatically enable EmbrAIon in every repository or modify repositories in the background.

## Add EmbrAIon to each project

Each repository opts in explicitly. From the project root:

```bash
cd /path/to/your/project
embraion init
```

By default, `init` uses the directory name as the project name. Use `--name MyProject` only when you want to override it.

This creates:

```text
.embraion/
└── project.yaml
```

The Project Overlay records the EmbrAIon repository/version declaration and project-specific configuration in version control.

### Install a host projection

Install the projection for each AI client used by the repository.

[Codex](https://openai.com/codex/):

```bash
embraion install --host codex --destination .
```

[GitHub Copilot](https://github.com/features/copilot):

```bash
embraion install --host copilot --destination .
```

[Claude Code](https://code.claude.com/docs/en/overview):

```bash
embraion install --host claude-code --destination .
```

Portable bundle:

```bash
embraion install --host portable --destination ./vendor/embraion
```

If a repository uses multiple clients, run the corresponding `install` command once for each one. Existing generated files are protected by default; use `--force` only when intentionally replacing them.

### What `init`, `install`, and `sync` do today

- `embraion init` creates the repository-local `.embraion/project.yaml` overlay.
- `embraion install` generates one host projection from the framework data available to the **currently running CLI** and copies it into the requested destination.
- `embraion sync` generates disposable projections into an output directory; it does not discover, initialize, or attach every project on the machine automatically.

### Project version pinning in v0.1.x

`.embraion/project.yaml` records a framework version, but the current `v0.1.x` CLI does **not** automatically resolve and launch that recorded version. `install` and `sync` use the framework data bundled with the EmbrAIon executable that is currently running.

For exact reproducibility, run the CLI/framework distribution that matches the version recorded by the project. In `v0.1.x`, the project version field is therefore a compatibility declaration and update boundary, not yet an automatic per-project runtime resolver.

## How a task flows through EmbrAIon

A substantial task conceptually follows this path:

```text
User goal
  ↓
Project overlay + Core catalog
  ↓
Relevant rules / agents / skills / workflows
  ↓
Data class + access profile + complexity
  ↓
Host adapter + model route
  ↓
Implementation
  ↓
Validation
  ↓
Independent review
  ↓
Verification
  ↓
Delivery / human merge gate
```

For substantial specification-driven work, [Spec Kit](https://github.com/github/spec-kit) is recommended as an independent companion. It refines planning and specification but does not replace Core rules, project truth, compatibility contracts, or validation evidence.

## CLI

### Framework and project

```text
embraion init
embraion install
embraion update
embraion sync
embraion validate
embraion doctor
```

### Routing and runtime state

Resolve a route:

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

Create a bounded dispatch plan:

```bash
embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class economy-write \
  --data PRIVATE \
  --access write \
  --owned-path "src/**"
```

Writable dispatch planning requires explicit owned paths and refuses the stable `main`/`master` branch. The plan and privacy-safe routing telemetry are written under `.embraion/state/`.

Start normalized session state:

```bash
embraion session start \
  --session-id task-001 \
  --task "Implement feature" \
  --role lead \
  --host codex \
  --access plan
```

Inspect or update it:

```bash
embraion session show
embraion session set --state review --validation passed
```

The host adapter performs actual AI execution; EmbrAIon owns canonical routing, generated agent definitions, access/ownership boundaries, dispatch plans, normalized state, and privacy-safe operational telemetry.

### Security

```bash
embraion security scan --path .
```

The scanner checks for high-risk configuration problems such as possible embedded credentials and policy drift.

### MCP inventory

```bash
embraion mcp inventory
```

This creates a normalized privacy-safe inventory under `.embraion/state/`. Environment-variable names may be recorded; secret values are never intentionally persisted.

### Worktrees

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree salvage /path/to/worktree
```

`gc` is dry-run by default and only considers directly proven, clean, unlocked worktrees. Use `--apply` explicitly to remove safe candidates.

### Learning

Record repeated evidence:

```bash
embraion learning observe \
  --id repeated-review-gap \
  --kind repeated-failure \
  --target-type skill \
  --target-id review \
  --summary "Repeated review gap"
```

Promotion is gated:

```text
observe → accumulate evidence → propose → approve → promote
```

Promotion never edits Core automatically. A promoted candidate still requires an ordinary reviewed engineering change.

### Behavioral evals

Run an eval case:

```bash
embraion eval run \
  --case reviewer-readonly \
  --record path/to/execution-record.json
```

Create and compare baselines:

```bash
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
```

## Generate adapter projections

Generate all supported projections without installing them into a project:

```bash
embraion sync --host all --output build/generated --force
```

Generated outputs are disposable projections. Canonical policy always remains in `core/`.

## Repository layout

```text
brand/         Brand specification and README assets
core/          Canonical rules, agents, skills, workflows, routing, knowledge
adapters/      Codex, Copilot, Claude Code, Portable, provider integrations
tools/         CLI, runtime, learning, security, MCP, worktree, validation, sync
schemas/       Machine-readable contracts
templates/     Project overlay templates
docs/          Canonical English documentation
localization/  Russian, Simplified Chinese, Hindi, and Spanish translations
tests/         Deterministic unit/integration tests
evals/         Behavioral cases, baselines, graders, fixtures, reports
examples/      Reference integrations
```

## Validation and CI

Every push and pull request is intended to run:

- schema and catalog validation;
- localization parity;
- unit and integration tests;
- security scanning;
- generation of all host projections;
- behavioral eval smoke tests.

Tagged releases generate source, Codex, Copilot, Claude Code, and Portable archives.

## Documentation

Canonical documentation: [docs/](docs/README.md)

Translations:

- [Русский](localization/docs/ru/README.md)
- [简体中文](localization/docs/zh-CN/README.md)
- [Español](localization/docs/es/README.md)
- [हिन्दी](localization/docs/hi/README.md)

## License and brand

EmbrAIon source code and documentation are licensed under the [MIT License](LICENSE), except where a file or directory explicitly states otherwise.

The **EmbrAIon** and **GORYNED** names, logos, wordmarks, visual marks, and the files under `brand/assets/` are **not licensed under MIT**. The MIT License does not grant trademark or brand-identity rights. See [TRADEMARKS.md](TRADEMARKS.md) for the canonical policy.

## Current status

EmbrAIon is **pre-stable**. The architecture and first executable CLI are in place, but the public compatibility contract is not frozen yet.

Before the first stable release, model catalogs, generated host projections, validation coverage, security rules, installation behavior, and release packaging may still evolve.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **[by GORYNED](https://goryned.com)**

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
