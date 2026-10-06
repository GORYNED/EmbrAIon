# Policy & Protected Paths

`.embraion/policy.yaml` contains project-owned safety policy.

![Source ownership and protection model](../assets/diagrams/en/13-source-ownership-protection.svg){ loading=lazy }

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

## Projection root checks

Codex merge mode keeps user-owned content in `.codex/config.toml`. The optional `projection` section decides how `embraion projection verify --config-mode merge` treats that content:

```yaml
projection:
  codex:
    strict-root: true
    forbidden-root-keys:
      - profiles.*.model
    allowed-root-keys:
      - mcp_servers
```

- `forbidden-root-keys` adds dotted key patterns to the Core defaults `model`, `model_reasoning_effort`, and `agents.default_subagent_*`. A project can extend the defaults but cannot remove them.
- `allowed-root-keys` is an optional allowlist of top-level keys. `developer_instructions` and `agents` are always allowed because EmbrAIon manages blocks inside them.
- Root `developer_instructions` text outside the managed orchestration block is always reported.
- `strict-root: true` turns these findings into verification failures, the same as `--strict-root`. Without it they are warnings and verification still depends only on projection drift.

## Inspect the effective policy

```bash
embraion policy show
embraion policy show --json
```

Invalid project configuration fails closed instead of being interpreted heuristically.
