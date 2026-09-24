# Host Integrations

EmbrAIon has one canonical Core and multiple host projections.

| Host | Generated location | Purpose |
| --- | --- | --- |
| Codex | `.codex/` | Codex configuration and native specialist agents |
| GitHub Copilot | `.github/agents/` | Copilot custom agents |
| Claude Code | `.claude/agents/` | Claude Code agent definitions |
| Portable | `embraion/` inside the chosen destination | Host-neutral capability bundle |

The generated files are projections, not the source of policy.

Install a projection with:

```bash
embraion install --host codex --destination .
```

Or generate disposable output without installing it into a project:

```bash
embraion sync --host all --output build/generated --force
```
