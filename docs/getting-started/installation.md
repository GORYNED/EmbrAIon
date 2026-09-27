# Installation

EmbrAIon uses one global launcher per machine. Each project pins the exact framework version it expects.

!!! tip "In plain English"
    Install the `embraion` command once. Individual repositories keep their own version pin, so one computer can work with projects on different EmbrAIon releases.

## Requirements

- Windows, macOS, or Linux
- Python 3.11 or newer
- `pipx` for the recommended isolated CLI installation

## Install the launcher

```bash
pipx install embraion
```

Confirm it:

```bash
embraion --version
embraion help
```

If EmbrAIon is already installed:

```bash
pipx upgrade embraion
```

## What happens after `pipx install`?

At this point, **no repository has been modified**.

You only installed the launcher command.

A repository becomes an EmbrAIon project only when you explicitly run:

```bash
cd MyProject
embraion init
```

Then you explicitly install the host projection(s) you want.

## Why one launcher is enough

A project records its framework version in `.embraion/project.yaml`.

If that pin differs from the global launcher, EmbrAIon can resolve the exact published project runtime into an isolated cache:

```text
~/.embraion/versions/<version>/
```

That lets different projects stay on different EmbrAIon versions without separate global CLI installations.

## Platform notes

### Windows

Use Python 3.11+ and `pipx`. After `pipx ensurepath`, reopen PowerShell so the command path is refreshed.

### macOS

`pipx` via Homebrew is convenient, but any managed Python 3.11+ environment works.

### Linux

Install Python 3.11+ and `pipx` using your distribution/package-management preference, then install `embraion` through `pipx`.

The EmbrAIon project contract is repository-portable; your project's own validation commands may still be platform-specific.

## Next

- Want zero risk? [Try the Five-Minute Sandbox](playground.md).
- Ready for a repository? [Add EmbrAIon to a Project](first-project.md).
