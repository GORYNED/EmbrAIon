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

`v0.2.0` implements automatic runtime resolution:

- ordinary commands discover the nearest `.embraion/project.yaml`;
- an exact pinned release is installed on first use into `~/.embraion/versions/<version>/`;
- later commands reuse that isolated cached runtime;
- different repositories can therefore stay on different EmbrAIon versions;
- `init` and `update` bypass delegation so the global launcher can create or intentionally change a project pin;
- legacy `0.1.0-dev` pins resolve to the published `0.1.0` package.

Existing generated files are protected by default. Use `--force` only for an intentional replacement.

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
