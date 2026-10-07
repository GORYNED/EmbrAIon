# Validation Configuration

`.embraion/validation.yaml` declares the **configuration** for commands that provide real project evidence. This page explains how to define profiles; [Validation & Evidence](../validation.md) explains what happens when they run and how evidence is used.

Simple profiles remain valid and backwards compatible:

```yaml
profiles:
  fast:
    - python -m unittest discover -s tests/unit -p "test_*.py"
  affected:
    - python -m unittest discover -s tests -p "test_*.py"
  full:
    - python -m unittest discover -s tests -p "test_*.py"
    - python -m compileall src
```

An empty profile is valid configuration, but running it produces `skipped` — not a false pass. Commands execute sequentially from the repository root.

## Runtime parameters

A profile can use the structured form when the project needs values that are only known at execution time:

```yaml
profiles:
  affected:
    commands:
      - pwsh -NoLogo -NoProfile -File tools/validation/validate.ps1 affected
    parameters:
      base-ref:
        argument: --BaseRef
        default: main
      head-ref:
        argument: --HeadRef
        default: HEAD

  full:
    commands:
      - pwsh -NoLogo -NoProfile -File tools/validation/validate.ps1 full
    parameters:
      justification:
        environment: PROJECT_FULL_JUSTIFICATION
        required: true
```

Supply declared values with repeatable `--param NAME=VALUE` options:

```bash
embraion validation run affected \
  --param base-ref=origin/main \
  --param head-ref=HEAD

embraion validation run full \
  --param justification=persistence-migration
```

A parameter targets either one command-line argument or one child-process environment variable. Optional `commands` uses one-based command indexes to restrict a parameter to selected commands:

```yaml
parameters:
  test-filter:
    argument: --filter
    commands: [1]
```

Values passed as command-line arguments are shell-quoted for the current platform. On Windows, argument values containing `cmd.exe` metacharacters are rejected instead of being interpolated into a shell command; use an environment parameter when such a value is required. Environment parameters are added only to the child validation process. Unknown parameters, missing required values, invalid command indexes, unsafe Windows argument values, and malformed configuration fail closed.

Structured validation evidence records which parameter names were used, but never persists their raw values or the expanded command containing them. Known runtime parameter values are also scrubbed from captured child stdout/stderr in addition to normal EmbrAIon redaction. Do not use validation parameters as a substitute for a secret manager.

## Timeouts

A structured profile can bound each command with the optional `timeout-seconds` key. A number applies to every command of the profile; a list gives one value per command, in order, and `null` leaves that command unbounded:

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
      - python tools/package.py
    timeout-seconds: [1800, null]
```

Without the key, commands run without a timeout, as before. `--timeout SECONDS` on the command line overrides the configured value for every command of that run. A list whose length differs from the command count, or a value that is not a positive number, fails closed.

## Optional commands and prerequisites

A command can stay a plain string. It can also be a mapping, in the same `commands` list or in a simple profile list:

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
      - command: ./tools/lint.sh
        required: false
      - command: ./tools/device-check.sh
        requires:
          executables: [adb]
          env: [DEVICE_ID]
          platforms: [linux, macos]
```

- `required` is optional and defaults to `true`.
- `requires` is optional. `executables` are looked up on `PATH` (a name with a path separator is resolved from the project root), `env` names must be set and not empty in the command environment, and `platforms` is a list of `linux`, `macos`, or `windows`.

A command whose prerequisite is missing is not started. It is reported as `blocked` with a reason, not as `failed`. A blocked required command makes the profile fail. A blocked optional command does not.

A command with `required: false` still runs, and its failure or timeout is recorded in the evidence. It does not fail the profile. The profile stays `passed` and the record gets a `warnings` count. A command that was never given `required` or `requires` behaves exactly as before. Unknown keys, a non-boolean `required`, an unknown platform, or an empty name fail closed.

## Clean-tree guard

A structured profile can require that validation does not change the working tree:

```yaml
profiles:
  gate:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
    clean-tree: true
```

Without the key, nothing is checked, as before. With `clean-tree: true`, EmbrAIon reads `git status --porcelain=v1 -z --untracked-files=all` before the first command and again after the last one, and compares the two.

- A tree that was already dirty is allowed. Its state is the baseline, and only new differences fail. A file that was already modified and is edited again counts as a difference, because the content is compared too.
- The `.embraion/state/` directory is ignored, because validation writes its own evidence there.
- A failure names up to 20 changed paths and the profile fails with a `failure-reasons` entry that starts with `clean-tree guard failed`.
- Outside a Git work tree, or when `git` is missing, the guard is `blocked` and the profile fails. The commands still run, and their results stay in the evidence.

The record gets a `clean-tree` object with `status` (`passed`, `failed`, or `blocked`), `baseline-dirty`, `changed-count`, and `changed-paths`. A profile without commands is `skipped` and is not checked.

## Output limit

By default each command's full redacted output is kept in its log, and the record keeps a tail of at most 8000 characters per stream. A very large output can make the log huge. A structured profile can bound it with `output-limit-bytes` (an integer of at least 1024):

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
    output-limit-bytes: 1048576
```

When a stream is larger than the limit, EmbrAIon keeps only the first and the last half of the limit, cut on line boundaries, and puts a marker between them in the log:

```text
[... output truncated: 9400000 bytes (210000 lines) omitted; total 9500000 bytes, 211000 lines ...]
```

Only the kept parts are read into memory. Each part is redacted on its own. Without the key, the log is not cut.

In both cases, when a stream is longer than the record tail, the command row gets `stdout-head` or `stderr-head` (the first 8000 characters) and an `output` object with the `bytes` and `lines` totals per stream and `log-truncated`. Short output adds no fields. The record shows `output-limit-bytes` when the profile sets it.

## Choosing profiles

A useful convention:

- `fast` — inexpensive checks for rapid feedback;
- `affected` — checks appropriate for the current change;
- `full` — the broad project gate before high-risk delivery or release.

The schema also permits additional named profiles.

## Run validation

```bash
embraion validation list
embraion validation run fast
embraion validation run affected
embraion validation run full
```

Useful options:

```bash
embraion validation run affected --json
embraion validation run affected --fail-fast
embraion validation run affected --timeout 120
embraion validation run full --run-id task-001
```

Each execution persists redacted structured evidence under `.embraion/state/validation/`, plus one full redacted log per command under `.embraion/state/validation/<evidence-id>/`. See [Validation & Evidence](../validation.md#evidence-behavior).

## Safety

Validation commands are executable project configuration. Keep them deterministic and repository-local where practical, review changes to them like code, and do not put secrets directly in command strings.

Malformed `validation.yaml` fails closed against the project schema.

For evidence and execution semantics, continue with [Validation & Evidence](../validation.md).
