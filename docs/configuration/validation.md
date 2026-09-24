# Validation Profiles

`.embraion/validation.yaml` declares the commands that provide real project evidence.

Default shape:

```yaml
profiles:
  fast: []
  affected: []
  full: []
```

An empty profile is valid configuration, but running it produces `skipped` — not a false pass.

## A practical example

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

Commands execute sequentially from the repository root.

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
