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

EmbrAIon is a portable AI-First Engineering System for organizing AI-assisted software engineering around explicit roles, reusable skills, workflow orchestration, task routing, access control, validation, review, security, learning, and project overlays.

It is designed to sit above individual languages and frameworks. A Unity/C# project, a Python service, a web application, or another software repository can use the same Core and add only project-specific knowledge and rules.

## What EmbrAIon does

EmbrAIon separates the engineering system into independent dimensions:

- **[Agent](core/agents/)** — who is responsible: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, Steward.
- **[Skill](core/skills/)** — how a repeatable class of work is performed.
- **[Rule](core/rules/)** — what is required, forbidden, or protected.
- **[Workflow](core/workflows/)** — in what order capabilities are composed.
- **[Routing](core/routing/)** — which complexity route, access/privacy constraints, and host should execute the work; model selection stays host-owned unless the project overrides it.
- **[Adapter](adapters/)** — how canonical capabilities are represented in Codex, Copilot, Claude Code, provider transports, or a host-neutral Portable bundle.
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

- **[Codex](https://openai.com/codex/)** — generated project config, agents, and skills; Codex owns its available models and default selection.
- **[GitHub Copilot](https://github.com/features/copilot)** — generated custom-agent and skills projection; Copilot owns its available models and default selection.
- **[Claude Code](https://code.claude.com/docs/en/overview)** — generated agent and skills projection; Claude Code owns its available models and default selection.
- **[Portable](adapters/portable/)** — host-neutral installable capability bundle.
- **[Providers](adapters/providers/)** — optional provider/transport integration surfaces without a framework-wide model catalog.

Core remains model-neutral. EmbrAIon does not maintain a canonical model list: hosts choose their own defaults, while projects may optionally store opaque host-specific model/effort/options overrides.


### Model-agnostic by design

EmbrAIon does **not** ship or maintain a canonical list of AI models. Model availability changes independently across hosts, plans, accounts, and time, so the framework keeps that knowledge out of Core.

With no project override, the selected host uses its own default or automatic model policy. If you want explicit model routing, ask the AI already working in your repository to configure it for you. For example:

> Configure EmbrAIon routing for this repository using the models currently available to you. Keep host-default where no explicit choice is needed. Put any model, effort, or host-specific overrides only in `.embraion/routing.yaml` under `overrides`, mapped to the appropriate route classes or roles. Do not weaken privacy, access, ownership, validation, or review policy.

The installed EmbrAIon host projection includes a `routing-configuration` skill that tells the AI exactly where and how to make that change. The project stores only its own overrides; EmbrAIon itself remains independent of individual model names.

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
embraion help
embraion status
embraion cache list
```

`embraion validate` validates the framework data bundled with the active EmbrAIon installation. `embraion doctor` prints a human-readable diagnostic report by default and automatically detects whether the current directory is inside a Git or EmbrAIon project. Outside a project it performs installation/framework diagnostics only; it does not recursively scan your home directory or another arbitrary folder. Use `embraion doctor --json` when structured machine-readable output is required.

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
├── project.yaml
├── knowledge.yaml
├── policy.yaml
└── routing.yaml
```

The Project Overlay records project configuration in focused files: `project.yaml` keeps framework/project identity plus validation/agents/capabilities, `knowledge.yaml` owns project knowledge references, `policy.yaml` owns sources/review/privacy policy, and `routing.yaml` owns optional model/effort/options overrides.

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

### Automatic project runtime resolution

`v0.2.0` adds automatic per-project version resolution.

For ordinary commands, the global `embraion` launcher walks upward from the current directory until it finds the nearest `.embraion/project.yaml`. It then reads `framework.version`:

```text
global embraion launcher
        ↓
nearest .embraion/project.yaml
        ↓
framework.version
        ↓
exact cached runtime for that project
```

If the pinned version differs from the launcher version, EmbrAIon installs the exact PyPI distribution into an isolated cache under:

```text
~/.embraion/versions/<version>/
```

The first command for a version may download it from PyPI. Later commands reuse the cached runtime. Projects can therefore use different EmbrAIon releases on the same Windows PC or Mac without separate global installations.

Legacy project overlays created by `v0.1.0` may contain `0.1.0-dev`; the new resolver treats that legacy pin as the published `0.1.0` distribution.

`embraion init` and `embraion update` intentionally run in the globally installed launcher instead of delegating to the old project runtime:

- `embraion init` opts a repository into the current launcher version.
- after `pipx upgrade embraion`, `embraion update` moves only the current project to the new launcher version.
- `embraion update --framework-version X.Y.Z` explicitly pins a chosen release; the next ordinary command resolves it automatically.

For framework development, setting `EMBRAION_HOME` keeps using the explicitly selected framework checkout. Automatic resolution can also be disabled explicitly with `EMBRAION_DISABLE_VERSION_RESOLUTION=1`.

### Inspect launcher, project pin, and runtime cache

```bash
embraion status
```

The status report shows the globally installed launcher version, nearest project, project pin, resolved runtime, whether the pinned runtime is already cached, the cache location, and detected host projections. Use `embraion status --json` for automation.

Inspect cached project runtimes:

```bash
embraion cache list
```

Clean invalid or stale cache entries with a dry run first:

```bash
embraion cache prune
```

Optionally include valid runtimes not used for a chosen number of days:

```bash
embraion cache prune --older-than 90
embraion cache prune --older-than 90 --apply
```

The current launcher version and the current project's resolved version are protected from age-based pruning.

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
Host adapter + host-default/project routing
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

Use `embraion help` for the categorized command catalog. Use `embraion help <command>` (including nested paths such as `embraion help cache prune`) or `embraion <command> --help` for detailed command-specific help.

### Routing and runtime state

Resolve a route:

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

Create a bounded dispatch plan:

```bash
embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class bounded-write \
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

The host adapter performs actual AI execution and owns model availability. EmbrAIon owns route classes and policy, generated agent definitions, access/ownership boundaries, dispatch plans, normalized state, and privacy-safe operational telemetry; `.embraion/routing.yaml` may optionally override host model selection.

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

## Reference projects

EmbrAIon includes three executable reference shapes:

- [Minimal](examples/minimal/README.md) — the smallest complete project overlay.
- [Python](examples/python/README.md) — a normal Python package with its own unit tests.
- [Unity/C#](examples/unity/README.md) — a generic Unity 6 project with an assembly definition, pure state logic, a Unity-facing controller, and project architecture knowledge.

CI copies each reference project into a temporary directory and exercises the real consuming-project lifecycle. Generated Codex, Copilot, Claude Code, and Portable projections are recreated rather than stored as canonical example source.

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
- Linux, Windows, and macOS compatibility on Python 3.11 and 3.14;
- project-version resolver E2E checks on each operating system;
- consuming-project E2E for Minimal, Python, and Unity/C# reference projects;
- security scanning;
- generation of all host projections;
- behavioral eval smoke tests.

Tagged releases generate source, Codex, Copilot, Claude Code, and Portable archives.

## Documentation

Documentation: **[goryned.github.io/EmbrAIon](https://goryned.github.io/EmbrAIon/)** · [Markdown sources](docs/index.md)

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

Before the first stable release, routing overrides, generated host projections, validation coverage, security rules, installation behavior, and release packaging may still evolve.

---

**EmbrAIon** · **AI-First Engineering System** · **[by GORYNED](https://goryned.com)**

<sub>Last updated: 2026-09-24 16:00 UTC</sub>
