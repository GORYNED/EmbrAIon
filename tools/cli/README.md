# CLI

Install EmbrAIon once per computer from [PyPI](https://pypi.org/project/embraion/). A source checkout is not required for normal use.

### Windows

Check Python 3.11+ first:

```powershell
py --version
```

If needed, install Python from the [official Windows downloads](https://www.python.org/downloads/windows/). Then install [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html):

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Open a new PowerShell window:

```powershell
pipx install embraion
```

### macOS

With [Homebrew](https://brew.sh/):

```bash
brew install pipx
pipx ensurepath
```

Open a new Terminal window:

```bash
pipx install embraion
```

Without Homebrew, use Python 3.11+ and the official [pipx installation guidance](https://pipx.pypa.io/latest/how-to/install-pipx.html).

Verify:

```bash
embraion --version
embraion validate
embraion doctor
```

Upgrade later with:

```bash
pipx upgrade embraion
```

The global `pipx` installation makes the CLI available from every project on that machine, but repositories opt in explicitly with `embraion init`. It does not auto-discover or modify all repositories.

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

In `v0.1.x`, the version recorded in `.embraion/project.yaml` is not an automatic runtime resolver. `install` and `sync` use the framework data bundled with the currently running CLI.

For framework development from a source checkout, `EMBRAION_HOME` may point the CLI at an explicit framework root.

Python source modules use standard `snake_case` naming as an ecosystem-specific exception to the repository's general kebab-case convention.

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
