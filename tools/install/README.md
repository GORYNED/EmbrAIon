# Install

EmbrAIon is installed once per computer from [PyPI](https://pypi.org/project/embraion/):

```bash
pipx install embraion
```

The command is then available to every repository on that computer. Each repository is connected once so its project-specific state stays explicit and version-controlled:

```bash
cd /path/to/project
embraion init --name MyProject
```

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

Existing generated files are protected by default. Use `--force` only for an intentional replacement.

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
