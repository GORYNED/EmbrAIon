# CLI

Install EmbrAIon once per computer from [PyPI](https://pypi.org/project/embraion/):

### Windows

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Open a new PowerShell window:

```powershell
pipx install embraion
```

### macOS

```bash
brew install pipx
pipx ensurepath
pipx install embraion
```

Upgrade later with:

```bash
pipx upgrade embraion
```

The global `pipx` installation makes the CLI available from every project on that machine. Each repository still uses an explicit project overlay and host projection.

Main commands:

```text
embraion init
embraion install
embraion update
embraion sync
embraion validate
embraion doctor
embraion route
embraion dispatch
embraion session
embraion security
embraion mcp
embraion worktree
embraion learning
embraion eval
```

For framework development from a source checkout, `EMBRAION_HOME` may point the CLI at an explicit framework root.

Python source modules use standard `snake_case` naming as an ecosystem-specific exception to the repository's general kebab-case convention.

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
