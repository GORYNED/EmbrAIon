# Install

EmbrAIon is installed once per computer from [PyPI](https://pypi.org/project/embraion/), preferably with `pipx`:

```bash
pipx install embraion
```

The command is then available from every repository on that computer, but each repository opts in separately:

```bash
cd /path/to/project
embraion init
```

`init` creates `.embraion/project.yaml`. It does not install a host projection automatically.

Install the host projection used by that repository:

```bash
embraion install --host codex --destination .
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
```

For a host-neutral bundle:

```bash
embraion install --host portable --destination ./vendor/embraion
```

The installed Python distribution carries the canonical framework data required to generate these projections. A local EmbrAIon source checkout is not required.

Current `v0.1.x` behavior:

- `install` generates from the framework data available to the currently running CLI.
- `sync` generates disposable projections into an output directory and does not discover or initialize all projects automatically.
- `.embraion/project.yaml` records a framework version, but that value is not yet an automatic per-project runtime resolver.
- exact reproduction therefore requires running the CLI/framework distribution that matches the project's recorded version.

Existing generated files are protected by default. Use `--force` only for an intentional replacement.

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
