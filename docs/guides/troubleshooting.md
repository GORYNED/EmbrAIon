# Troubleshooting

Start with:

```bash
embraion doctor
embraion status
```

These commands resolve most configuration/runtime questions faster than manually inspecting generated files.

## `Invalid .embraion/...`

EmbrAIon validates canonical project configuration against its schema and fails closed on malformed values.

Common causes:

- a list was written as a string;
- a required agent field is missing;
- an unsupported data class/access value was used;
- configuration was placed in the wrong `.embraion/` file.

Use the [Project Configuration Files](../configuration/project-files.md) reference and correct the canonical file rather than editing generated host output.

## `Projection conflicts with user-modified or unowned files`

Preview ownership:

```bash
embraion projection diff --host codex --destination .
```

For a mature repository, adopt only the component you want:

```bash
embraion projection diff --host codex --destination . --component skills
embraion install --host codex --destination . --component skills
```

Use `--force` only after deciding EmbrAIon should intentionally replace the conflicting file.

## Launcher/project version mismatch

A project pins its EmbrAIon release in `.embraion/project.yaml`. Ordinary commands can resolve that exact published runtime from the cache.

To intentionally move the project forward:

```bash
pipx upgrade embraion
cd MyProject
embraion update
```

Safe configuration normalization targets the installed launcher version. Do not ask a different launcher release to guess another version's configuration contract.

See [Runtime & Version Resolution](../reference/runtime-version-resolution.md).

## `Validation ... skipped`

The profile exists but contains no commands.

Inspect:

```bash
embraion validation list
```

Then add real commands to `.embraion/validation.yaml`. `skipped` is intentionally not treated as `passed`.

## Validation failed

Run the profile directly and inspect its redacted command output:

```bash
embraion validation run affected
```

Fix the project failure first. Do not weaken policy merely to make the gate green.

## Enforcement is disabled

That is the default.

Inspect:

```bash
embraion enforcement status
```

When the project is ready, install enforcement explicitly. See [Enforcement](enforcement.md).

## `Unknown validation profile`

The enforcement or CLI request names a profile not declared in `.embraion/validation.yaml`. Either configure the profile or select an existing one.

## `Unknown route` or unexpected `host-default`

`host-default` is normal. It means EmbrAIon is allowing the AI client to use its own default/automatic model selection.

Inspect routing:

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

Only add `.embraion/routing.yaml` overrides when explicit host-specific selection is actually needed.

## Runtime cache problems

Inspect:

```bash
embraion cache list
```

Dry-run cleanup:

```bash
embraion cache prune --older-than 90
```

Apply only after reviewing candidates:

```bash
embraion cache prune --older-than 90 --apply
```

## Generated files look stale after `embraion update`

That is intentional. Updating the project configuration does not silently rewrite host projections.

Preview first:

```bash
embraion projection diff --host codex --destination .
```

Then reinstall deliberately if wanted.

## Still stuck?

See [Support](../oss/support.md) or open a focused GitHub Issue with the EmbrAIon version, operating system, command, error output, and minimal reproduction. Do not include secrets or private project data.
