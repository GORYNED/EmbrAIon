# Install

Installation creates host projections from canonical EmbrAIon Core.

Install the EmbrAIon CLI without cloning the repository:

```bash
pipx install "git+https://github.com/GORYNED/EmbrAIon.git"
```

After a PyPI release:

```bash
pipx install embraion
```

Then, from the consuming project:

```bash
embraion init
embraion install --host codex --destination .
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
embraion install --host portable --destination ./vendor/embraion
```

The installed Python distribution carries the canonical framework data required to generate these projections. A local EmbrAIon source checkout is not required.

Existing generated files are protected by default. Use `--force` only for an intentional replacement.

<sub>Last updated: 2026-09-23 21:13 UTC</sub>
