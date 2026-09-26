# Validation Profiles

`.embraion/validation.yaml` declares the commands that provide real project evidence.

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

Each execution persists redacted structured evidence under `.embraion/state/validation/`.

## Safety

Validation commands are executable project configuration. Keep them deterministic and repository-local where practical, review changes to them like code, and do not put secrets directly in command strings.

Malformed `validation.yaml` fails closed against the project schema.

For evidence and execution semantics, continue with [Validation & Evidence](../validation.md).
