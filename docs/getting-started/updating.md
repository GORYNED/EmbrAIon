# Updating Safely

EmbrAIon has two versions to think about:

1. the global launcher installed on the machine;
2. the exact framework release pinned by each project.

Project updates are intentionally explicit.

## Normal update flow

Upgrade the launcher:

```bash
pipx upgrade embraion
```

Then, inside the project you want to move forward:

```bash
cd MyProject
embraion update
embraion doctor
embraion status
```

Updating the launcher does not silently migrate every repository.

## Why the launcher must match the target

Safe configuration normalization is owned by the installed launcher release.

`embraion update` therefore targets the installed launcher version instead of asking one release to guess another release's schema/defaults.

If you intentionally need a different published release, install that launcher version first, then run `embraion update` from the project.

## What update may change

For a compatible modular `.embraion/` layout, update can:

- move the project pin to the active launcher version;
- add compatible defaults that are missing;
- preserve existing project-owned values.

Before writing anything, EmbrAIon builds and validates candidate configuration for all canonical project files.

## What update does not do

`embraion update` does **not**:

- silently guess a migration for an incomplete/legacy layout;
- rewrite incompatible user-owned values heuristically;
- refresh Codex/Copilot/Claude/Portable projections automatically;
- rewrite projection ownership state.

If configuration is incompatible, update fails before the canonical files are rewritten.

## Review host projection changes separately

After an update:

```bash
embraion projection diff --host codex --destination .
```

Reinstall only when you intentionally want the generated host files to move to the new projection.

## Version resolution

Older projects can remain pinned to older published releases even when the global launcher is newer. Ordinary commands can resolve the exact project runtime from the local version cache.

See [Runtime & Version Resolution](../reference/runtime-version-resolution.md).

## Pre-1.0 compatibility

Patch releases are intended for compatible fixes and improvements. Minor releases may evolve framework contracts. Review release notes before moving a production repository across a minor version.
