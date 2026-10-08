# Security & Data Flow

This page answers the practical question: **what can leave my machine or repository, and when?**

For the normative security rules, see [Security](security.md).

!!! tip "In plain English"
    EmbrAIon is not a prompt proxy. Normal Codex/Copilot/Claude conversations go directly through that AI host. EmbrAIon owns repository configuration and deterministic local/CI checks; provider calls happen only through the host or through an explicitly configured provider-execution path.

## Data flow at a glance

| Action | What EmbrAIon does | Network/data boundary |
| --- | --- | --- |
| `pipx install embraion` / upgrade | Installs the CLI package | Your package installer contacts its configured package infrastructure. No project repository is required for installation. |
| `embraion init` | Creates the project-owned `.embraion/` contract | Does not call a model provider. |
| `doctor`, `status`, `context`, `policy`, `route` | Reads/validates local project configuration and metadata | These commands do not need a model-provider call. `route` resolves policy; it does not ask a model. |
| `embraion install --host ...` | Generates host-native projection files | Generation is a project/host configuration operation, not a provider inference call. |
| Normal Codex/Copilot/Claude work | The AI host reads the repository/context it is allowed to use | The **AI host** owns its network, retention, and account policy. EmbrAIon does not sit between you and that host. |
| `embraion validation run ...` | Runs configured project commands and records redacted evidence | EmbrAIon itself is not calling a model provider. A project command can still have whatever network behavior that command/tool normally has. |
| `embraion security scan` / `enforcement check` | Runs deterministic checks over repository/configuration/evidence | No model-provider call is required by the EmbrAIon check itself. |
| `embraion execute` | Runs the optional bounded provider-neutral execution path | May send the approved request/context to the explicitly configured adapter/provider, subject to project policy and binding ceilings. |
| `embraion execution envelope` / `preflight` / `health` | Builds context envelopes from committed files, checks bindings and credential presence, or summarizes the attempt ledger | Local only; no provider call. The envelope builder refuses protected paths, credential material, and machine-local paths before anything can be sent. |
| Project runtime resolution | Resolves the repository's exact published EmbrAIon version when required | May download a published EmbrAIon package into the local version cache; this is framework distribution, not a model-context upload. |

## Does EmbrAIon upload my repository to GORYNED?

Normal project operation does not require an EmbrAIon-operated prompt proxy or cloud backend, and Core does not intentionally upload repository content to a GORYNED/EmbrAIon service.

Two other systems can still use the network:

1. **Your AI host** — Codex, Copilot, Claude Code, or another supported surface operates under its own product/account data policy.
2. **An execution provider you explicitly configure** — `embraion execute` can invoke a declared adapter/provider according to the project's execution contract.

Package installation/version resolution can also contact package infrastructure.

## Does EmbrAIon have telemetry?

Yes, but runtime telemetry is **local operational state**, not a remote analytics service.

EmbrAIon appends privacy-safe runtime events to:

```text
.embraion/state/telemetry.jsonl
```

The local events can record operational metadata such as timestamps, session/dispatch IDs, role, host, selected model/effort, data class, access mode, and owned-path count. Values are redacted before persistence.

The runtime telemetry intentionally excludes prompt content, source excerpts, diffs, raw reasoning, and credential values. The telemetry writer appends to the local state file; it is not a network sender. `.embraion/state/` is local project state and is gitignored by default.

## What is persisted?

### Project-owned, versioned configuration

The repository can commit:

- `.embraion/project.yaml`
- `.embraion/knowledge.yaml`
- `.embraion/policy.yaml`
- `.embraion/deployments.yaml`
- `.embraion/routing.yaml`
- `.embraion/validation.yaml`
- `.embraion/agents.yaml`
- optional `.embraion/execution.yaml` and `.embraion/pricing.yaml`

Secret values should not be stored there.

### Local runtime state

Runtime evidence/state is stored under `.embraion/state/` and caches under `.embraion/cache/`; project initialization keeps those local through the project `.gitignore`.

Validation evidence can include redacted stdout/stderr tails, command identity, duration, exit state, and evidence IDs.

For provider-neutral execution, attempt records are designed not to persist raw credentials or raw prompt/context bytes. `embraion execute` keeps them in the bounded local ledger `.embraion/state/execution-attempts.jsonl`, which also feeds deployment health.

The envelope builder rejects path-shaped absolute POSIX, Windows drive, and UNC paths, as well as `file:` URLs and the repository root. This is a heuristic for literal text, not a proof that arbitrary content cannot reveal machine details: encoded, fragmented, or otherwise disguised paths may remain. Review the committed files you pass with `--path` before allowing external execution.

## How are credentials handled?

Execution bindings reference credentials by name, for example:

```yaml
credentialRef: env:EXAMPLE_API_KEY
```

The secret value itself does not belong in project configuration.

For child processes launched by EmbrAIon-owned adapters, the framework builds a minimal allowlisted environment and redacts captured output before persistence.

Host-native AI clients remain governed by their own environment and credential controls.

## What do PUBLIC / PRIVATE / CONFIDENTIAL mean?

They are Core data classes used to constrain eligibility and execution. Routing cannot widen privacy or permission boundaries.

A project can map a canonical class to legacy project vocabulary at an execution boundary, but the alias does not weaken the original class.

## What about local models?

EmbrAIon is **provider-neutral**, but that is not a promise that every local model server is automatically supported.

A local model can participate only through:

- an AI host that already supports it; or
- an execution adapter/binding that the project intentionally supports and validates.

Do not assume Ollama, LM Studio, or another local server is supported merely because EmbrAIon is model-agnostic.

## Related

- [Security model](security.md)
- [Execution & Providers](configuration/execution.md)
- [Policy & Protected Paths](configuration/policy.md)
- [Validation & Evidence](validation.md)
- [Enforcement](guides/enforcement.md)
