# Validation & Evidence

EmbrAIon has two related but different validation concepts.

![Validation, evidence, runs, and review](assets/diagrams/en/09-validation-evidence-run-review.svg){ loading=lazy }

## Framework validation

```bash
embraion validate
```

This validates the installed EmbrAIon framework itself: schemas, catalogs, references, localization contracts, and other deterministic framework invariants.

Use it when verifying the EmbrAIon installation or developing the framework.

Inside a project it also checks the project's policy ceilings and warns about structural problems in `.embraion/*.yaml`: unknown keys, missing knowledge paths and organization roots, unknown knowledge roles, and empty or unread files. `embraion validate --strict` turns those warnings into errors; see the [CLI reference](reference/cli.md#embraion-validate).

## Project validation profiles

Consuming repositories define executable commands in `.embraion/validation.yaml` and run them with:

```bash
embraion validation run <profile>
```

Configure profiles first: [Validation Profiles](configuration/validation.md).

Inspect available project profiles:

```bash
embraion validation list
```

Run fresh evidence:

```bash
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

## Evidence behavior

Commands execute sequentially from the project root. Each result records:

- profile and overall status;
- command identity;
- exit code;
- duration;
- redacted stdout/stderr tails of at most 8000 characters each;
- the effective timeout and the path of the command's full log;
- optional attached execution run;
- evidence ID/path.

Evidence is stored under:

```text
.embraion/state/validation/
```

That is local runtime state and is ignored by the project-local `.gitignore`. Each command also writes its complete redacted stdout and stderr to `.embraion/state/validation/<evidence-id>/command-<index>.log`, so a long failure stays inspectable beyond the tail in the record.

Each command starts in its own process group (a new session on POSIX, a new process group on Windows). When a command times out, or the run is interrupted, EmbrAIon terminates the whole tree, including processes the command started: on POSIX it signals the group with `SIGTERM` and then `SIGKILL`; on Windows it ends the tree with `taskkill /T /F`. An interrupted run stops and records no evidence. Timeouts come from `--timeout` or the profile's [`timeout-seconds`](configuration/validation.md#timeouts).

With `--run-id`, every command receives the run ID in the `EMBRAION_RUN_ID` environment variable, so tools it starts can label their own artifacts. Without `--run-id`, the variable is removed from the command environment.

An empty profile reports `skipped`. A failed or timed-out command makes the profile fail. Use `--fail-fast` only when later commands are not useful after the first failure.

## Validation is evidence, not a policy override

A green test result cannot override a failed privacy, permission, protected-path, compatibility, or security gate.

Likewise, behavioral eval improvement does not turn a deterministic safety failure into a pass.

## Attach evidence to a structured run

```bash
embraion validation run affected --run-id task-001
```

The run must be active. The validation record is attached by evidence ID rather than re-entered as an unverified claim.

See [Runs & Review](guides/runs-review.md) and [Enforcement](guides/enforcement.md).

## Organization and live skill evaluation

Declare exact project namespace, assembly and asset rules in [organization configuration](configuration/organization.md), then bind `embraion organization check` to the affected validation profiles and CI. Incremental checks show existing debt separately; a full audit reports every finding. Missing configuration reports `skipped`, not evidence that the repository is organized.

The existing `eval run` grades supplied execution records. [Live skill evals](guides/skill-evals.md) launch isolated authenticated host sessions (Codex, Claude Code, or any agent CLI through the portable host) and compare baseline/candidate behavior across repeated English and Russian cases. Fake-host runner tests verify mechanics and never establish semantic skill quality.
