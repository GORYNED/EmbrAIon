# Installation

EmbrAIon uses one global launcher per machine. Each project pins the exact framework version it expects.

!!! tip "In plain English"
    Install the `embraion` command once. Individual repositories keep their own version pin, so one computer can work with projects on different EmbrAIon releases.

## Requirements

- Windows, macOS, or Linux
- Python 3.11 or newer
- `pipx` for the recommended isolated CLI installation
- Git on your `PATH`

### Git and GitHub

Git is a stated prerequisite of EmbrAIon. Project checks, worktrees, and the decision records read and change Git state. The worktree commands need Git 2.36 or newer, because they read `git worktree list --porcelain -z`. The CLI does not check the Git version for you.

GitHub is the supported hosting and delivery surface. The GitHub CLI `gh`, signed in, is needed only when `embraion worktree gc` verifies merged pull requests. Without it, cleanup keeps the resources it cannot prove.

The universal rules stay in the [worktree](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/worktree.md) and [delivery](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/delivery.md) workflows. Their Git and GitHub mechanics are in [one place](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/git.md). The decision is recorded in [ADR 0001](../architecture/decisions/0001-git-is-a-prerequisite-git-mechanics-live-in-one-place.md).

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

A repository becomes an EmbrAIon project when you ask your agent to configure
it. The agent checks the launcher and repository, runs the supported setup and
host installation steps, then verifies the result in a fresh host session where
available. A shared machine installation may require your permission; you do
not need to type commands or edit YAML. If the host has not yet loaded the
`project-bootstrap` skill, it must first discover the official installation
procedure. File checks alone do not prove that a host loaded the new skill.

The equivalent manual command remains available:

```bash
cd MyProject
embraion init
```

Then install your host projection and open a new session in that host. See
[Project Bootstrap](../configuration/bootstrap.md).

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
