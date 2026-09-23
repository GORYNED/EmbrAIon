# CLI

Install EmbrAIon without cloning the repository:

```bash
pipx install "git+https://github.com/GORYNED/EmbrAIon.git"
```

After the package is published to PyPI:

```bash
pipx install embraion
```

The installed distribution includes the framework data required by the CLI, so a checked-out EmbrAIon repository is not required at runtime.

For framework development from a source checkout, `EMBRAION_HOME` may still be used to point the CLI at an explicit framework root.

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

Python source modules use standard `snake_case` naming as an ecosystem-specific exception to the repository's general kebab-case convention.

<sub>Last updated: 2026-09-23 21:13 UTC</sub>
