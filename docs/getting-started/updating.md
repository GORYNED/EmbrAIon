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
embraion update --framework-version 0.6.0
```

Then verify:

```bash
embraion status
embraion doctor
```

## Why updates are explicit

A project pin is part of reproducibility. Older projects can keep using their exact published runtime while another project moves forward.

Before 1.0, patch releases are intended for compatible fixes and documentation improvements. Minor releases may evolve framework contracts. Review the release notes before moving a production project across a minor version.
