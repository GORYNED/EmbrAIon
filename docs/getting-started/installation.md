# Installation

EmbrAIon uses one global launcher per machine. Consuming projects pin the framework version they expect.

## Requirements

- Windows, macOS, or Linux
- Python 3.11 or newer
- `pipx` for the recommended isolated CLI installation

## Install the launcher

```bash
pipx install embraion
```

Confirm the installation:

```bash
embraion --version
embraion help
```

If EmbrAIon is already installed:

```bash
pipx upgrade embraion
```

## Why one launcher is enough

A project records its framework version in `.embraion/project.yaml`. If that pin differs from the global launcher, EmbrAIon resolves the exact published project runtime into an isolated cache under:

```text
~/.embraion/versions/<version>/
```

This allows different projects to remain on different EmbrAIon versions without installing a separate global CLI for every repository.

## Next

[Initialize your first project](first-project.md).
