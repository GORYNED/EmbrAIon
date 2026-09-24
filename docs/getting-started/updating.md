# Updating

There are two separate versions to think about:

1. the global EmbrAIon launcher installed on the machine;
2. the framework version pinned by each project.

## Update the launcher

```bash
pipx upgrade embraion
```

Updating the launcher does not silently migrate every project.

## Update one project

From that project:

```bash
embraion update
```

Or choose an explicit published version:

```bash
embraion update --framework-version 0.9.1
```

Safe configuration normalization currently targets the installed EmbrAIon launcher version only. To move a project to another published version, install or upgrade/downgrade the launcher to that version first, then run `embraion update`; this prevents the current launcher from writing configuration for a release contract it does not own.

Then verify:

```bash
embraion status
embraion doctor
```

## Compatible configuration normalization

`embraion update` also normalizes an existing **modular** `.embraion/` configuration to the target release contract before changing the project pin.

The normalization is conservative:

- only missing default fields are added;
- existing project values are not replaced with framework defaults;
- all candidate configuration files are validated before any file is written;
- generated Codex, Copilot, Claude Code, Portable, and projection-state files are not regenerated or modified;
- incompatible user-authored values fail the update instead of being guessed or rewritten.

For example, a project created on `0.8.1` can gain a later default such as the disabled `policy.yaml → enforcement` block without changing its privacy, source, routing, validation, agent, or host-projection choices.

Automatic normalization expects the focused modular layout introduced in the `0.8.x` line. If required dedicated files such as `policy.yaml` or `validation.yaml` are missing, the update stops and reports the legacy/incomplete layout rather than attempting an unsafe migration.

Host projections remain intentionally separate. After a framework update, use `embraion projection diff` and `embraion install` only when you explicitly want to refresh generated host files.

## Why updates are explicit

A project pin is part of reproducibility. Older projects can keep using their exact published runtime while another project moves forward.

Before 1.0, patch releases are intended for compatible fixes and documentation improvements. Minor releases may evolve framework contracts. Review the release notes before moving a production project across a minor version.
