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

### `embraion bootstrap`

Optional deterministic discovery and conservative application for an initialized project. The normal user entry point is the ordinary-language [Project Bootstrap](../configuration/bootstrap.md) skill.

```bash
embraion bootstrap plan --output .embraion/state/bootstrap-plan.json
embraion bootstrap apply --plan .embraion/state/bootstrap-plan.json
```

`plan` reports evidence, proposed knowledge/policy/validation changes, and limitations. Read the original sources before applying: filename candidates are not proof of authority and CI commands need local context/safety review. `--path` selects the initialized project. Output must be in local `.embraion/state/` or outside the repository.

`apply` accepts only an unchanged, reviewed plan matching current discovery, source hashes, configuration, and project root. It fills unbound slots/empty profiles and conservatively populates empty canonical sources; populated settings and stricter restrictions survive. It does not configure routing/agents, create docs, install dependencies, run commands, or claim validation passed. Semantic correction belongs to bounded project edits followed by a fresh plan. Lead owns subsequent verification.

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

Supported components are host-specific: Codex supports `config`, `agents`, and `skills`; GitHub Copilot supports `agents` and `skills`; Claude Code supports `agents`, `skills`, and optional `scoped-agents` and `hooks`; Portable uses `bundle`. Unselected components remain user-owned and are excluded from obsolete-file handling.


For a mature Codex repository that already owns `.codex/config.toml`, use merge ownership for only the EmbrAIon-required `[agents]` keys:

```bash
embraion install \
  --host codex \
  --component config \
  --config-mode merge
```

`--config-mode replace` remains the default. Merge mode preserves project-owned `[agents]` keys and other TOML tables and fails closed when the file cannot be merged safely.

Projection install and pruning reject nested symlinks or junctions in managed paths, including projection evidence under `.embraion/state`. The destination itself may still be a directory alias. File writes use exclusively created, unique temporary files and replace the destination entry, preserving external hardlink contents and ignoring pre-existing `.tmp` aliases. Pruning rechecks ownership hashes immediately before deletion and preserves intervening edits.

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

`projection verify` exits zero only when every selected projection file is already canonical and there is no create, update, conflict, or obsolete managed output. Files under a reserved projection prefix (Claude Code `scoped-agents`: `.claude/agents/embraion--*.md`) that the current projection would not produce are reported as `obsolete-modified` even without an ownership ledger. With partial Codex config ownership, pass `--config-mode merge` to both `projection diff` and `projection verify`.

Merge mode preserves user content outside the managed blocks, so verify also reports `root-findings` for that content: root keys that override the user's model or effort or the routed subagent selection (`model`, `model_reasoning_effort`, `agents.default_subagent_*`), keys outside an optional `allowed-root-keys` list, and root `developer_instructions` text outside the managed orchestration block. Findings are warnings by default. `--strict-root`, or `projection.codex.strict-root: true` in [policy](../configuration/policy.md#projection-root-checks), makes them fail verification:

```bash
embraion projection verify --host codex --component config --config-mode merge --strict-root --json
```

The Claude Code `hooks` component always merges: it manages only EmbrAIon's hook entries in `.claude/settings.json` and records them in the projection ledger. `projection verify --host claude-code --component hooks` fails when a managed entry is missing (update) or changed (conflict); other settings and hooks are not drift.

### `embraion policy`

Inspect normalized source, validation, review, privacy, and merge policy:

```bash
embraion policy show
embraion policy show --json
```

Fail when deployments, execution bindings, or routing widen the project's [policy ceilings](../configuration/policy.md#policy-ceilings). `embraion validate` runs the same check inside a project:

```bash
embraion policy check
embraion policy check --json
```

### `embraion report`

Render or check the project's completion report contract, declared in `.embraion/report.yaml` (see [Completion report](../configuration/report.md)):

```bash
embraion report template
embraion report validate report.md --pull-request
embraion report validate report.md --pull-request-not-created
embraion report validate update.md --kind intermediate
```

`report validate` exits non-zero with line-numbered findings when the report breaks the contract. Use `-` to read from stdin. `--pull-request` requires the full pull request URL; `--pull-request-not-created` requires a compare URL instead. The two flags are mutually exclusive.

### `embraion update`

Safely normalize project configuration and atomically synchronize the framework pin with the exact published release artifact lock.

```bash
embraion update
embraion update --framework-version <published-version>
```

Check for a newer published release without changing any file:

```bash
embraion update --check
embraion update --check --json
```

`--check` reads the latest stable GitHub Release, validates its tag and expected wheel digest, and reports the launcher and project-pin status (`current`, `outdated`, `ahead`, or `not-comparable`), whether the project has an artifact lock, and the next steps. It exits `0` whether or not an update is available; `update-available` in the JSON report carries that answer. Unreachable or malformed release metadata exits non-zero. `--check` cannot be combined with `--framework-version`.

Safe configuration normalization targets the installed EmbrAIon launcher version only. To move a project to another published version, install or upgrade/downgrade the launcher to that version first, then run `embraion update`.

Before changing the pin, EmbrAIon resolves the canonical GitHub Release and requires exactly one expected wheel named `embraion-<version>-py3-none-any.whl` with a valid server-side GitHub `sha256:` digest. It validates the release tag, asset identity, URL, digest shape, and all candidate canonical `.embraion/` configuration.

The project manifest is written atomically with both:

- `framework.version`
- `framework.artifact.{schema,source,release,asset,digest}`

A missing release asset, malformed digest, version/lock mismatch, or incompatible configuration fails closed. Existing version-only projects are upgraded automatically; missing modular config files are materialized from compatible defaults without manual migration. Generated host projections and projection state remain untouched.

### `embraion framework`

Use the framework-owned artifact lock instead of consumer-specific download/checksum logic.

Verify the exact locked release asset without installing it:

```bash
embraion framework verify
embraion framework verify --json
```

Install the exact locked wheel into the isolated EmbrAIon runtime cache:

```bash
embraion framework install
embraion framework install --json
```

Both commands read `.embraion/project.yaml`, require a valid artifact lock, download the exact canonical GitHub Release asset, and verify its SHA-256 before success. `framework install` verifies before invoking pip and records the lock identity in the runtime cache marker. Cached runtimes with a different artifact identity or digest are rejected.

Print the exact pin for scripts and CI without network access:

```bash
embraion framework pin
embraion framework pin --json
```

The output is `version=<x.y.z>` and, when the pin is locked, `digest=sha256:<hex>`, one per line, so it can be appended to `$GITHUB_OUTPUT`. The command fails on a missing `framework.version`, on anything other than an exact `MAJOR.MINOR.PATCH` release (for example `latest`, `>=1`, `1.2` or extra text), on another `framework.repository`, and on a malformed or mismatched artifact lock. Error messages never repeat the rejected value. The [setup action](runtime-version-resolution.md#consumer-ci) uses the same reader.

### `embraion sync`

Generate disposable host projections without installing them into a project.

```bash
embraion sync --host all --output build/generated --force
```

## Health & runtime

### `embraion pricing`

For the conceptual model, see [Pricing & cost](../configuration/pricing.md).

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

`embraion pricing calculate` reads a JSON request from stdin with `deployment`, nullable `usage`, `usageSemantics`, and optional `billing`, `providerExact`, `adapterCost`, `reportedCurrency`, `atUtc`, `batch`, and `discount` fields. Snapshot calculation requires explicit usage semantics: `inclusive` means cached and reasoning counts are included in input and output totals; `disjoint` means they are additional counts. Providers with different input and output conventions can supply `{"input":"inclusive","output":"disjoint"}`. It reads only the local validated snapshot; reported exact costs take precedence. A reported cost has unknown currency unless `reportedCurrency` is supplied. The response keeps unknown and stale prices distinct from zero. A scheduled rate cannot be combined with batch or discount rates in one snapshot entry.

`embraion pricing verify --fixtures <yaml> [--json]` checks that the configured rows produce reviewed costs. The file has `schemaVersion: 1` and a `fixtures` list; each fixture has a unique `id`, `deployment`, nullable `usage`, optional `usageSemantics`, `atUtc` (quoted), `billing`, `batch`, and `discount`, and `expect` with `state`, `amount` (a quoted decimal string or null), and optional `currency`. Each fixture runs offline through the same calculation as `pricing calculate`; amounts compare as exact decimals (`"3.750"` equals `"3.75"`). The command exits 1 on any mismatch.

### `embraion execute`

For execution ownership, bindings, aliases, fallback, and handoff behavior, see [Execution & providers](../configuration/execution.md).

Read a versioned execution request from stdin and emit a JSON result. Executable deployments require explicit `.embraion/execution.yaml` bindings. Install the optional `embraion[litellm]` extra for the `litellm-loopback` adapter. It runs one bounded request in a short-lived local child, using only the selected credential reference. Bindings declare the exact upstream selector and provider, approved context boundary, source/trust/task ceilings, and exact or anchored observed-model evidence. The request supplies approved input in `payload.inputsByDeployment` for every candidate bound to this adapter on the current execution host, including fallback candidates. Cross-host and unbound handoff candidates need no adapter input. Missing required inputs and non-candidate input keys fail closed; each selected input must match its work-item provenance; worker text appears only in the result, never in attempt evidence. Unbound host deployments return `handoff-required`. Project acceptance remains separate from transport completion.

Snapshot cost from LiteLLM usage requires separately reviewed overlap evidence. An optional binding `usageSemanticsEvidence` contains a project-relative `.embraion/usage-evidence/*.json` path and its SHA-256 digest. That checked-in, sanitized JSON records schema version 1, `transport: litellm-responses`, exact LiteLLM `adapterVersion`, provider, selector, official `sourceUrl`, verification and validity timestamps, explicit input/output `usageSemantics`, and a representative `sampleUsage`. The adapter accepts it only when the file digest, running LiteLLM version (currently 1.88.6), provider, selector, dates, and sample shape agree. Missing, expired, or mismatched evidence leaves usage semantics unknown, so snapshot-derived cost remains unknown; it does not block execution. A provider-reported exact cost or LiteLLM normalized cost retains its separate priority. Record evidence only after reviewing real normalized Responses usage against the provider's official billing semantics; a synthetic test fixture does not establish that contract.

Without `healthObservations` in the request, health comes from the local attempt ledger. Each validated attempt is appended to `.embraion/state/execution-attempts.jsonl` (redacted attempt fields only; one rotation at 1 MiB). A failed ledger write prints a warning and keeps the result.

```bash
embraion execute < request.json
```

### `embraion execution`

Build context envelopes, check readiness, and inspect attempt health. See [Execution & providers](../configuration/execution.md#context-envelopes) for the refusal rules.

```bash
embraion execution envelope --path src/module.py --task-file task.md < request.json > ready.json
embraion execution preflight --path src/module.py --task-file task.md --json < request.json
embraion execution preflight --deployment analysis-api
embraion execution health --json
```

`envelope` reads a request from stdin and prints it with `payload.inputsByDeployment` for every adapter-bound candidate. It reads committed content only (`--commit`, default `HEAD`); `--path` is repeatable, `--task-file` is required, and `--max-file-bytes`, `--max-total-bytes`, `--max-output-tokens`, and `--payload-only` are optional. A refusal exits 2 and names the path and reason. `preflight` runs the request consistency checks of `execute`, then checks binding completeness, request ceilings, credential presence, and adapter preflight without a provider call or credential output, and exits 1 when not ready. `health` summarizes the attempt ledger per deployment.

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
embraion validate --strict
```

Inside a project, `validate` also warns (`projection-ignored`) when Git ignores a file recorded in a projection ledger under `.embraion/state/projections`, because a new projected file at such a path would stay untracked. The warning does not fail validation.

Inside a project, `validate` also checks the project's `.embraion/*.yaml` structure and reports warnings for:

- keys a schema in `schemas/` does not declare, at the top level and one section down (`config-unknown-key`);
- knowledge slots or entries whose path is missing or leaves the project, and organization `roots` that do not exist (`config-path`);
- knowledge `roles` that match no Core role or agent declared in `.embraion/agents.yaml` (`config-role`);
- empty files, empty sections that expect a value, and `.embraion` YAML files EmbrAIon does not read (`config-inert`), plus unreadable YAML (`config-parse`).

Warnings keep the exit code at 0; `--strict` reports them as errors. Without findings the output stays `PASS: no validation issues.`. Full schema conformance remains with the commands that load each file, and the policy-ceiling check stays an error.

### `embraion check`

Run every check the project configuration selects, from the project root wherever it is started, so consumer CI needs one step:

```bash
embraion check
embraion check --base-ref origin/main --fail-on medium --all-files
embraion check --json
```

It always runs `validate --strict`, `route --validate`, `route --audit-authority` and `security scan` (with `--fail-on`, default `high`, and `--all-files` passed through). It adds `projection verify` for each host whose components `.embraion/policy.yaml` declares under `projection`, `claude-native status --require` when Claude Code `scoped-agents` or `hooks` are declared, `organization check --require-config` when `.embraion/organization.yaml` exists, and `decisions check --require-config` when `.embraion/decisions.yaml` exists and `--base-ref` is given; without `--base-ref` that check is reported as `NOT RUN` and does not fail the command. Without `--base-ref` the organization check audits the whole structure; with it, the check compares against that ref, so only findings the ref does not have fail, together with moves and GUID changes. The `check` section of `.embraion/policy.yaml` can instead declare which organization modes run (`full`, `compare` or both, reported as `organization-full` and `organization-compare`; `compare` is `NOT RUN` without a base ref), and the default of `--fail-on` and `--all-files`; those flags override it. See [Check options](../configuration/policy.md#check-options). The ref must be fetched, so a CI checkout needs its history. Each check prints `PASS` or `FAIL`, a failed check also prints its output, and an error in one check fails only that check. The command exits 1 when any check fails, and 2 when `.embraion/policy.yaml` cannot be read. See [Policy](../configuration/policy.md#projection-root-checks).

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

`--run-id` attaches the profile result to an active structured execution record, so validation evidence does not have to be re-entered manually, and passes the run ID to each command as `EMBRAION_RUN_ID`. Each command runs in its own process group; a timeout or interrupt terminates the whole tree. `--timeout` overrides a profile's `timeout-seconds`. Each command's full redacted output is kept in `.embraion/state/validation/<evidence-id>/command-<index>.log`.

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
embraion route --task-class routine-review --access review
embraion route --task-class routine-review --escalation quality --justification "review evidence"
embraion route --validate
embraion route --audit-authority
```

The result reports `resolution: host-default` with `model: null` when the host should choose automatically, `resolution: project-override` for a direct project selector, or `resolution: project-deployment` when routing references `.embraion/deployments.yaml`. Deployment routes also report the resolved provider, billing metadata, and ordered fallback plan.

Task-class resolution composes the project's ordered effective candidates, keeps availability fallback separate from explicit escalation, and reports provenance. The authority audit checks manually maintained consumer files for duplicates of concrete facts held in `.embraion/**`; verified generated projections are exempt.

### `embraion dispatch`

Create a bounded privacy-aware execution plan.

Every selected `critical` route requires `--justification "concrete risk"` on both `route` and `dispatch`. Direct execution requests likewise require nonblank `justification` for `routeClass: critical`.

`dispatch --native-surface claude-agent` prepares a complete scoped definition for explicit model/effort and never executes it. `--native-agent reviewer` binds a native specialist independently of `--role` (the project routing role). See [Claude Code](../hosts/claude-code.md) for definition loading and evidence requirements.

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

For `run start --route-class critical`, pass `--justification "concrete risk"`. The redacted reason is retained in the run's route evidence.

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
embraion session start --session-id task-001 --task task-001 --role lead --access workspace-write --independent-task
embraion session start --session-id subtask-001 --task subtask-001 --role lead --access workspace-write --subtask
embraion session show
embraion session set --state review --validation passed
```

## Engineering controls

### `embraion capabilities`

Inspect optional `.embraion/external-capabilities.yaml` declarations and the evidence available for a host:

```bash
embraion capabilities --path . --host codex --json
embraion capabilities --path . --host codex --observation host-observation.json --json
```

An inventory entry does not install or load a host capability. Local checks cannot verify host-managed installation or execution; supplied host observations remain self-reported. Legacy `builtin:unity` entries are reported unavailable. See [External capabilities](../configuration/capabilities.md).

### `embraion organization`

Check changed files against incremental code-organization rules:

```bash
embraion organization check --path . --base-ref main --head-ref HEAD --include-worktree --json
embraion organization check --path . --config .embraion/organization.yaml --json
embraion organization check --path . --require-config --json
```

The base reference identifies existing debt; it is not a waiver for violations added by the change. Without a configuration the check is `skipped`; `--require-config` makes it fail. See [Code organization](../configuration/organization.md).

### `embraion decisions`

Check that a change that makes an architecture-level decision carries a decision record:

```bash
embraion decisions check --base-ref origin/main
embraion decisions check --base-ref origin/main --waiver "vendored copy, no ownership change" --json
embraion decisions check --base-ref origin/main --require-config
```

The check compares the merge base of the base ref and the head (`HEAD` by default) with the head. It fails with `missing-record` when a trigger declared in `.embraion/decisions.yaml` (by default, an added or deleted package manifest) fires and the change adds or modifies no record in the folder bound to the `decisions` slot, unless a `Decision-Waiver: <reason>` commit trailer or `--waiver` states why none is needed. Without a configuration the check is `skipped`; `--require-config` makes it fail. See [Architecture decision records](../configuration/decisions.md).

### `embraion adr`

Create the next numbered architecture decision record:

```bash
embraion adr new "Move parsing into its own package"
embraion adr new "Move parsing into its own package" --locale ru --status Proposed --date 2026-10-07 --json
```

`adr new` writes the record from the project template, adds the index row, and with `--locale <code>` (repeatable) writes a localized copy next to it. It creates the folder, template, and index when the project has none. `--slug` names the file when the title has no ASCII words. See [Architecture decision records](../configuration/decisions.md#scaffold).

### `embraion pr-template`

Install the optional, project-neutral pull request template:

```bash
embraion pr-template
embraion pr-template --path ../service --json
```

The command writes `.github/pull_request_template.md` from `templates/pull-request/pull-request-template.md`. The template has sections for what changed, architecture, compatibility (source and API separate from persisted data), validation, checks that were not run, risks, workers, and the independent review with the exact final head SHA. It never overwrites: if the project already has a pull request template (in the root, `docs/`, or `.github/`, including a `PULL_REQUEST_TEMPLATE/` folder) or a link at that path, the command reports it and leaves everything unchanged. `embraion init` does not run it. `--path` selects the project directory, and `--json` prints `status` (`created` or `exists`) and `path`.

### `embraion checkpoint`

Save a local, reference-only task checkpoint and inspect its freshness later:

```bash
embraion checkpoint create task-42-step-1 --task-id task-42 --phase implementing --acceptance-path docs/task-42.md --path .
embraion checkpoint resume task-42-step-1 --path .
```

`create` also accepts `--decision-id`, `--next-action-id`, `--remaining-path`, `--context-id`, and `--run-id`. Both commands return JSON. Resume checks the project pin and knowledge hashes, referenced evidence, and a Git snapshot covering HEAD, index, and visible working files. It reports `valid`, `stale`, or `missing`; it does not grant review approval or user authorization. See [Task continuity](../guides/task-continuity.md).

### `embraion knowledge`

Create an explicit baseline for declared document/source relationships, then audit drift without writing:

```bash
embraion knowledge snapshot --path .
embraion knowledge audit --path .
```

Both commands return JSON. `snapshot` writes ignored local hash metadata; `audit` reports changed or missing sources for review and does not rewrite documents. See [Knowledge maintenance](../guides/knowledge-maintenance.md).

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

With `--run-id`, active runs receive validation evidence. Completing a run with passed review binds it to HEAD, index entries, and tracked/nonignored untracked file contents, modes and symlink targets. Enforcement requires that snapshot to match both before and after validation; commits, staging changes and working edits require a new reviewed run. Legacy review records without a snapshot cannot satisfy the gate. Unreadable state, submodules and ambiguous directory aliases fail closed. Completed runs are not modified or recompleted. All gates, including external-review gates, reject validation-time changes to the inspected Git snapshot. Ignored runtime/build output is outside that snapshot.

The check rejects mutations of protected sources, requires the configured validation profile to produce a real pass, and enforces review from execution evidence when `require-review` is enabled.

Install the GitHub Actions CI surface explicitly:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected \
  --require-review
```

No enforcement workflow or native hook is installed by `init`, `install`, or `harness audit`. The generated workflow installs EmbrAIon through the reusable `GORYNED/EmbrAIon/actions/setup` action at the generating release, which reads the project pin at run time, so later pin updates need no workflow edit; see [Consumer CI](runtime-version-resolution.md#consumer-ci). `install` refuses an inexact pin before writing. The generated workflow exits non-zero for policy/validation/review failures. To make that check a mandatory merge gate, configure **EmbrAIon enforcement** as a required status check in the repository branch rules/ruleset.

### `embraion security`

Scan for likely secrets and policy drift.

```bash
embraion security scan --path . --fail-on high
```

`--all-files` also checks source and other text files for private keys, access tokens, and machine paths. For paths the project's `.embraion/policy.yaml` marks as `external` or `generated` (never `canonical` or `protected` ones) it waives only the machine-path check and reports how many files that affected (`machine-path-waived-files` with `--json`); secrets are still reported there; see [Security](../security.md#scan-findings). When `.embraion/integrations.yaml` exists, the scan also compares the declared MCP servers with the observed host configuration and reports drift as high-severity `integration-drift` findings; see [Declared integrations](../security.md#declared-integrations).

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
embraion worktree gc --json
embraion worktree prepare --task-id task-001 --host codex --json
embraion worktree create ai/my-task --task-id task-001 --independent-task
embraion worktree publish --task-id task-001 --branch ai/my-task
embraion worktree restore --cleanup-id <cleanup-id>
embraion worktree salvage /path/to/worktree
```

See the [worktree tool guide](https://github.com/GORYNED/EmbrAIon/blob/main/tools/worktree/README.md) and [canonical workflow](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/worktree.md) for opt-in housekeeping, shared creation receipts, lifecycle gates, recovery, and preservation reasons. `gc` defaults to dry-run. `publish` explicitly creates a new remote branch and records creation evidence; subsequent task commits use the same command with an exact prior-SHA lease and verified update receipt. External pushes do not register ownership or updates. Legacy markers retain worktree-only cleanup rights. Existing user branches cannot be adopted.

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

Learning evidence is identified by run ID. Eval IDs record their associated runs, so observing the same eval without its run does not add a confirmation; later association replaces an earlier eval-only confirmation. Separate runs remain independent even with a shared eval label. Unattributed observations count once only when no identified evidence exists. Repeating evidence is idempotent. Legacy associations are reconstructed conservatively and persisted. If newly discovered correlation invalidates a proposal or approval, it returns to observed/accumulating; approval and promotion recheck thresholds. Promoted candidates cannot be reproposed. An omitted target ID stays omitted; promotion notes are included in the schema.

### `embraion eval`

Run behavioral evals and compare baselines.

```bash
embraion eval run --case reviewer-readonly --record execution-record.json
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
embraion eval skills run --suite evals/skills/code-organization.json --host codex --attempts 2 --output build/skill-evals.json --path . --route-class ordinary --data PRIVATE
```

`eval run --record` evaluates a supplied execution record; it does not launch an AI host. `eval skills run` starts fresh host sessions (`--host codex`, `claude-code`, or `portable` with `--host-command`) for baseline and candidate skill variants, subject to project routing and privacy gates. Optional `--model` and `--effort` must agree with resolved project settings when the route is explicit. Its report distinguishes observed behavior from narrow skill-read evidence; neither proves the skill caused an outcome. See [Live skill evaluations](../guides/skill-evals.md).

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

## `embraion claude-native`

Install native guard/observer hooks and inspect advisory Claude Code callback metadata:

```bash
embraion install --host claude-code --component scoped-agents
embraion claude-native install-hooks --dry-run
embraion claude-native install-hooks
embraion projection verify --host claude-code --component hooks
embraion claude-native status
embraion claude-native status --require installed,hooks
```

The explicit `scoped-agents` component requires `.embraion/claude-native.yaml`; the default Claude installation still includes only `agents` and `skills`. Definitions derive from project routing. Start a new Thread after installation and invoke the exact definition type returned by dispatch. See [Claude Code](../hosts/claude-code.md).

`install-hooks` installs the Claude Code `hooks` projection component (`embraion install --host claude-code --component hooks` is equivalent) after checking the scoped-agents projection. It preserves unrelated settings and hooks in `.claude/settings.json` and records the managed entries in the projection ledger. `guard` reads a PreToolUse JSON event from stdin: it checks configured definitions, refuses invocation overrides and, with read-policy enabled, bounds configured scoped-agent reads. It does not restrict parent sessions, arbitrary agents or Bash. `observe` receives PostToolUse/SubagentStop events and stores only identity and reported effort in ignored local state. These two commands are hook entry points.

`status` separates file installation from recorded callback metadata and advisory `reported-effort` comparisons. Observer input has `evidence-origin: unverified-command-input`; `execution`, effective `effort` and `model` remain `unverified`; `callbacks: recorded` denotes accepted metadata. Synthetic parser tests and local records do not prove host delivery, instruction loading, invocation completion or applied settings.

Without `--require`, `status` exits 0 whatever the installation state. For CI, `--require installed,hooks` (comma-separated or repeated) adds a `gate` object and exits 1 unless each listed fact holds: `installed` requires `installation: verified`, so a missing or stale projection fails; `hooks` requires every guard and observer hook entry in `.claude/settings.json`. Only these file facts can gate, because `status` verifies them itself. Model, effort, execution and callbacks come from host behavior or unverified hook input, so `--require` refuses them with exit 2 rather than turning advisory data into a pass.
