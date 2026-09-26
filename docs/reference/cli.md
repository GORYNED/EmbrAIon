# CLI Reference

Run:

```bash
embraion help
```

for the launcher-owned command catalog, or:

```bash
embraion help <command>
```

for command-specific help.

## Project & setup

### `embraion init`

Create the modular `.embraion/` project configuration.

```bash
embraion init
embraion init --name MyProject
```

### `embraion install`

Install one host projection.

```bash
embraion install --host codex --destination .
```

Hosts: `codex`, `copilot`, `claude-code`, `portable`.

Preview without writing:

```bash
embraion install --host codex --destination . --dry-run
```

Installed projections track generated-file hashes. Later installs distinguish safe updates from local conflicts instead of blindly overwriting files.

Existing repositories can select projection components explicitly:

```bash
embraion install --host codex --destination . --component skills
embraion install --host codex --destination . --component agents --component skills
```

Supported components are host-specific: Codex supports `config`, `agents`, and `skills`; GitHub Copilot and Claude Code support `agents` and `skills`; Portable uses `bundle`. Unselected components remain user-owned and are excluded from obsolete-file handling.


For a mature Codex repository that already owns `.codex/config.toml`, use merge ownership for only the EmbrAIon-required `[agents]` keys:

```bash
embraion install \
  --host codex \
  --component config \
  --config-mode merge
```

`--config-mode replace` remains the default. Merge mode preserves project-owned `[agents]` keys and other TOML tables and fails closed when the file cannot be merged safely.

### `embraion projection`

Preview ownership-aware projection changes:

```bash
embraion projection diff --host codex --destination .
embraion projection diff --host codex --destination . --component skills
embraion projection diff --host codex --destination . --json
```

Verify an installed projection as a strict CI gate:

```bash
embraion projection verify --host codex --destination .
embraion projection verify --host copilot --component agents --component skills
```

`projection verify` exits zero only when every selected projection file is already canonical and there is no create, update, conflict, or obsolete managed output. With partial Codex config ownership, pass `--config-mode merge` to both `projection diff` and `projection verify`.

### `embraion policy`

Inspect normalized source, validation, review, and privacy policy:

```bash
embraion policy show
embraion policy show --json
```

### `embraion update`

Safely normalize a compatible modular project configuration and change the current project's framework pin.

```bash
embraion update
embraion update --framework-version <published-version>
```

Safe configuration normalization currently targets the installed EmbrAIon launcher version only. To move a project to another published version, install or upgrade/downgrade the launcher to that version first, then run `embraion update`; this prevents the current launcher from writing configuration for a release contract it does not own.

Before writing, EmbrAIon builds and validates the target configuration for all canonical `.embraion/` files. It adds only missing defaults, preserves existing project values, and leaves generated host projections and projection state untouched. Incompatible values or an incomplete legacy layout fail before any configuration file is rewritten.

### `embraion sync`

Generate disposable host projections without installing them into a project.

```bash
embraion sync --host all --output build/generated --force
```

## Health & runtime

### `embraion pricing`

Inspect the validated local pricing snapshot without network access:

```bash
embraion pricing status --json
embraion pricing status --fail-on-stale
```

Refresh only approved official sources declared by ID in `.embraion/pricing.yaml`:

```bash
embraion pricing refresh --json
embraion pricing refresh --source openai
```

Refresh validates every selected source and replaces the snapshot atomically. A failure leaves the previous snapshot intact; execution can continue offline, while stale or missing rates produce unknown calculated cost. Provider-specific SKU patterns and source URLs stay in the project configuration. The CLI does not accept arbitrary URLs.

`embraion pricing calculate` reads a JSON request from stdin with `deployment`, nullable `usage`, `usageSemantics` (`inclusive` or `disjoint`), and optional `billing`, `providerExact`, `adapterCost`, `reportedCurrency`, `atUtc`, `batch`, and `discount` fields. Snapshot calculation requires explicit usage semantics: `inclusive` means cached and reasoning counts are included in input and output totals; `disjoint` means they are additional counts. It reads only the local validated snapshot; reported exact costs take precedence. A reported cost has unknown currency unless `reportedCurrency` is supplied. The response keeps unknown and stale prices distinct from zero. A scheduled rate cannot be combined with batch or discount rates in one snapshot entry.

### `embraion execute`

Read a versioned execution request from stdin and emit a JSON result. Executable deployments require explicit `.embraion/execution.yaml` bindings and a registered adapter. The CLI has no built-in execution adapter yet, so it returns `handoff-required` for configured host deployments. Library callers can inject an adapter. Project acceptance remains separate from transport completion.

```bash
embraion execute < request.json
```

### `embraion doctor`

Run framework and project diagnostics.

```bash
embraion doctor
embraion doctor --json
```

### `embraion status`

Show launcher version, project pin, resolved runtime, cache, and host projections.

```bash
embraion status
embraion status --json
```

### `embraion validate`

Validate framework schemas, catalogs, references, localization, and other deterministic contracts.

```bash
embraion validate
embraion validate --json
```

### `embraion validation`

List or execute project validation profiles from `.embraion/validation.yaml`:

```bash
embraion validation list
embraion validation list --json
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

`validation run` executes commands from the project root, persists redacted evidence under `.embraion/state/validation/`, and exits non-zero when the profile fails. Empty profiles report `skipped`. Use `--fail-fast` to stop after the first failing command and `--timeout SECONDS` for a per-command timeout.

Structured validation profiles can declare runtime parameters. Supply them with repeatable `--param NAME=VALUE`:

```bash
embraion validation run affected \
  --param base-ref=origin/main \
  --param head-ref=HEAD
```

Unknown parameters and missing required parameters fail closed. Parameters can be projected into a command-line argument or into the validation child process environment according to `.embraion/validation.yaml`.

`--run-id` attaches the profile result to an active structured execution record, so validation evidence does not have to be re-entered manually.

### `embraion cache`

Inspect or clean isolated project runtimes.

```bash
embraion cache list
embraion cache list --json
embraion cache prune --older-than 90
embraion cache prune --older-than 90 --apply
```

Pruning is dry-run unless `--apply` is supplied.

## AI execution

### `embraion deployment`

Inspect the consuming project's `.embraion/deployments.yaml` registry:

```bash
embraion deployment list
embraion deployment list --json
embraion deployment show DEPLOYMENT_ID
embraion deployment show DEPLOYMENT_ID --json
```

The registry is project-owned. EmbrAIon validates it but does not ship a global model/provider catalog.

### `embraion route`

Resolve host-default or project-overridden routing. EmbrAIon does not select a model unless the project explicitly overrides the route or role.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
embraion route --host codex --route-class substantial --role reviewer --data PRIVATE
```

The result reports `resolution: host-default` with `model: null` when the host should choose automatically, `resolution: project-override` for a direct project selector, or `resolution: project-deployment` when routing references `.embraion/deployments.yaml`. Deployment routes also report the resolved provider, billing metadata, and ordered fallback plan.

### `embraion dispatch`

Create a bounded privacy-aware execution plan.

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

### `embraion context`

Select project knowledge by task, role, privacy class, and character budget:

```bash
embraion context build \
  --task "Review architecture boundaries" \
  --role architect \
  --data PRIVATE \
  --max-chars 20000
```

Canonical Project Contract Slots can also be requested explicitly:

```bash
embraion context slots
embraion context slots --json

embraion context build \
  --task "Review persistence compatibility" \
  --role reviewer \
  --slot persistence \
  --slot compatibility \
  --data PRIVATE
```

`--slot` is repeatable and accepts: `constitution`, `architecture`, `source-authority`, `compatibility`, `persistence`, `engineering-workflow`, and `specification`. An explicit slot request bypasses its default task-term trigger but still respects project-configured role and privacy restrictions.

The saved record stores provenance metadata and hashes, not duplicated knowledge contents.

```bash
embraion context show CONTEXT_ID
```

### `embraion run`

Record execution evidence:

```bash
embraion run start \
  --run-id task-001 \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class substantial \
  --data PRIVATE \
  --access write \
  --owned-path "src/**" \
  --substantial

embraion run complete task-001 \
  --changed-path src/example.py \
  --validation fast=passed \
  --review passed \
  --outcome completed
```

Completed writable runs enforce owned scope, protected project paths, and substantial-review policy.

### `embraion session`

Manage normalized task/session state.

```bash
embraion session start --session-id task-001 --task "Implement feature"
embraion session show
embraion session set --state review --validation passed
```

## Engineering controls

### `embraion enforcement`

Inspect project enforcement:

```bash
embraion enforcement status
embraion enforcement status --json
```

Evaluate the enabled gate against a Git base ref:

```bash
embraion enforcement check --base-ref origin/main
embraion enforcement check --base-ref origin/main --run-id task-001 --json
```

The check rejects mutations of protected sources, requires the configured validation profile to produce a real pass, and enforces review from execution evidence when `require-review` is enabled.

Install the GitHub Actions CI surface explicitly:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected \
  --require-review
```

No enforcement workflow or native hook is installed by `init`, `install`, or `harness audit`. The generated workflow exits non-zero for policy/validation/review failures. To make that check a mandatory merge gate, configure **EmbrAIon enforcement** as a required status check in the repository branch rules/ruleset.

### `embraion security`

Scan for likely secrets and policy drift.

```bash
embraion security scan --path . --fail-on high
```

Redact likely credentials from diagnostic text:

```bash
embraion security redact --text "token=..."
```

### `embraion harness`

Audit host agent/skill projection surfaces and report native hook capability metadata:

```bash
embraion harness audit --host codex
embraion harness audit --host all
```

EmbrAIon reports hook availability but does not silently install executable project hooks.

### `embraion mcp`

Create a privacy-safe MCP inventory.

```bash
embraion mcp inventory
```

### `embraion worktree`

Manage isolated Git worktrees.

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree gc --apply
embraion worktree salvage /path/to/worktree
```

### `embraion learning`

Record evidence and manage gated learning candidates.

```bash
embraion learning observe \
  --id repeated-review-gap \
  --kind repeated-failure \
  --target-type skill \
  --target-id review \
  --summary "Repeated review gap"

embraion learning propose repeated-review-gap
embraion learning approve repeated-review-gap
embraion learning promote repeated-review-gap
```

### `embraion eval`

Run behavioral evals and compare baselines.

```bash
embraion eval run --case reviewer-readonly --record execution-record.json
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
```

## Help

### `embraion help`

Show the launcher-owned catalog or nested command help.

```bash
embraion help
embraion help cache prune
embraion --help
```

## Exit behavior

Commands use non-zero exit codes for failed deterministic checks or invalid operations. Machine-readable output is available where documented through `--json`.
