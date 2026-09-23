<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System by GORYNED" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="localization/README.ru.md">Русский</a> ·
  <a href="localization/README.zh-CN.md">简体中文</a>
</p>

# EmbrAIon

**AI-First Engineering System by GORYNED**

> Where sparks become AI-built products

EmbrAIon is a portable AI-First Engineering System for organizing AI-assisted software engineering around explicit roles, reusable skills, workflow orchestration, model routing, access control, validation, review, security, learning, and project overlays.

It is designed to sit above individual languages and frameworks. A Unity/C# project, a Python service, a web application, or another software repository can use the same Core and add only project-specific knowledge and rules.

## What EmbrAIon does

EmbrAIon separates the engineering system into independent dimensions:

- **Agent** — who is responsible: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, Steward.
- **Skill** — how a repeatable class of work is performed.
- **Rule** — what is required, forbidden, or protected.
- **Workflow** — in what order capabilities are composed.
- **Routing** — which access profile, model tier, host, and provider may execute the work.
- **Adapter** — how canonical capabilities are represented in Codex, Copilot, Claude Code, providers, or a host-neutral Portable bundle.
- **Tool** — deterministic executable behavior such as validation, security scanning, worktree management, synchronization, and diagnostics.
- **Eval** — whether AI behavior actually follows the intended engineering contract.

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

- **Codex** — native model catalog, model/effort route mapping, generated project agents and config.
- **GitHub Copilot** — advisory model catalog and generated custom-agent projection.
- **Claude Code** — Claude model catalog and generated subagent projection.
- **Portable** — host-neutral installable capability bundle.
- **Providers** — direct API model catalogs for OpenAI, Anthropic, Google, DeepSeek, plus transport metadata.

Core remains model-neutral. Current model identities and host selectors live only in adapters.

## Installation

### Requirements

- Python 3.11+
- Git
- A local clone of this repository

The current pre-stable CLI is intentionally installed from source.

### 1. Clone EmbrAIon

```bash
git clone https://github.com/GORYNED/EmbrAIon.git
cd EmbrAIon
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### 3. Verify the framework

```bash
embraion validate
embraion doctor
```

## Add EmbrAIon to a project

Create the project overlay:

```bash
cd /path/to/your/project
embraion init --name MyProject
```

This creates:

```text
.embraion/
└── project.yaml
```

The project overlay pins the framework version and is where project-specific capabilities can be declared without modifying Core.

### Install a host projection

Codex:

```bash
embraion install --host codex --destination .
```

GitHub Copilot:

```bash
embraion install --host copilot --destination .
```

Claude Code:

```bash
embraion install --host claude-code --destination .
```

Portable bundle:

```bash
embraion install --host portable --destination ./vendor/embraion
```

Use `--force` only when intentionally replacing an existing generated projection.

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

For substantial specification-driven work, Spec Kit is recommended as an independent companion. It refines planning and specification but does not replace Core rules, project truth, compatibility contracts, or validation evidence.

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
localization/  Russian and Simplified Chinese translations
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

## License and brand

EmbrAIon source code and documentation are licensed under the [MIT License](LICENSE), except where a file or directory explicitly states otherwise.

The **EmbrAIon** and **GORYNED** names, logos, wordmarks, visual marks, and the files under `brand/assets/` are **not licensed under MIT**. The MIT License does not grant trademark or brand-identity rights. See [TRADEMARKS.md](TRADEMARKS.md) for the canonical policy.

## Current status

EmbrAIon is **pre-stable**. The architecture and first executable CLI are in place, but the public compatibility contract is not frozen yet.

Before the first stable release, model catalogs, generated host projections, validation coverage, security rules, installation behavior, and release packaging may still evolve.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **by GORYNED**

<sub>Last updated: 2026-09-23 20:27 UTC</sub>
