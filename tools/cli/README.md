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

`doctor` prints a human-readable report by default and only runs project-level security, MCP, and worktree diagnostics when it detects a Git repository or an explicit `.embraion/project.yaml`. From a home directory or other non-project folder, those recursive diagnostics are skipped. Use `embraion doctor --json` for structured automation output.

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
embraion status
embraion cache list
embraion cache prune
embraion route
embraion dispatch
embraion session
embraion security
embraion mcp
embraion worktree
embraion learning
embraion eval
```

`v0.2.0` resolves project pins automatically: ordinary commands find the nearest `.embraion/project.yaml`, install an exact pinned release into `~/.embraion/versions/<version>/` when necessary, and delegate to that cached runtime. `init`, `update`, `status`, and `cache` intentionally stay on the global launcher.

Use `embraion status` to inspect the launcher, project pin, resolved runtime, and detected host projections. Use `embraion cache list` to inspect cached runtimes and `embraion cache prune` for a safe dry-run cleanup; add `--apply` to remove candidates.

For framework development from a source checkout, `EMBRAION_HOME` may point the CLI at an explicit framework root.

Python source modules use standard `snake_case` naming as an ecosystem-specific exception to the repository's general kebab-case convention.

<sub>Last updated: 2026-09-23 22:00 UTC</sub>
