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

Create `.embraion/project.yaml` in a project.

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

### `embraion update`

Change the current project's framework pin.

```bash
embraion update
embraion update --framework-version 0.4.3
```

### `embraion sync`

Generate disposable host projections without installing them into a project.

```bash
embraion sync --host all --output build/generated --force
```

## Health & runtime

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

### `embraion route`

Resolve a configured route.

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

### `embraion dispatch`

Create a bounded privacy-aware execution plan.

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

### `embraion session`

Manage normalized task/session state.

```bash
embraion session start --session-id task-001 --task "Implement feature"
embraion session show
embraion session set --state review --validation passed
```

## Engineering controls

### `embraion security`

Scan for likely secrets and policy drift.

```bash
embraion security scan --path . --fail-on high
```

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
