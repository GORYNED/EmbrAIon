# Policy & Protected Paths

`.embraion/policy.yaml` contains project-owned safety policy.

A typical configuration:

```yaml
sources:
  canonical:
    - src/**
    - knowledge/**
  protected:
    - vendor/**
  generated:
    - build/**
  external:
    - external/**

review:
  substantial-required: true

privacy:
  default-class: PRIVATE

enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

## Source classes

### `canonical`

Project-owned source of truth. These are normal authored files.

### `protected`

Paths that ordinary writable work must not mutate. Use this for material that requires a separate approval or ownership path.

Protected-path checks cover modifications, additions where relevant, deletions, rename sources, and dot-prefixed paths such as `.github/**`.

### `generated`

Build output or other derived files that should not be mistaken for canonical authored source.

### `external`

Material sourced from outside the project and governed separately from project-owned source.

## Review policy

```yaml
review:
  substantial-required: true
```

This expresses the project rule that substantial work requires review evidence where the execution contract calls for it.

## Privacy default

```yaml
privacy:
  default-class: PRIVATE
```

Valid classes are `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`.

Model choice cannot widen these boundaries.

## Enforcement policy

Enforcement is disabled by default:

```yaml
enforcement:
  enabled: false
  validation-profile: affected
  require-review: false
```

Do not manually flip this block and assume CI is installed. Use the explicit command when you are ready to add the GitHub Actions surface:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

See [Enforcement](../guides/enforcement.md) for the complete workflow.

## Inspect the effective policy

```bash
embraion policy show
embraion policy show --json
```

Invalid project configuration fails closed instead of being interpreted heuristically.
