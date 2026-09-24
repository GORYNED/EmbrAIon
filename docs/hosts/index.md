# AI Clients

EmbrAIon keeps one canonical Core and projects it into the AI client(s) used by each repository.

| Client | Typical generated locations | What EmbrAIon projects |
| --- | --- | --- |
| Codex | `.codex/`, `.agents/skills/` | config, specialist agents, skills |
| GitHub Copilot | `.github/agents/`, `.github/skills/` | custom agents, skills |
| Claude Code | `.claude/agents/`, `.claude/skills/` | agent definitions, skills |
| Portable | `embraion/` inside the chosen destination | host-neutral capability bundle |

Generated files are projections. Canonical reusable behavior remains in EmbrAIon Core; project-specific configuration remains under `.embraion/`.

## Install a client projection

```bash
embraion install --host codex --destination .
```

Other hosts:

```bash
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
embraion install --host portable --destination vendor/embraion
```

A repository can support multiple AI clients at the same time.

## Existing host configuration

For mature repositories, preview before writing:

```bash
embraion projection diff --host codex --destination .
```

Or adopt only selected components:

```bash
embraion install --host codex --destination . --component skills
```

See [Adopt an Existing Repository](../getting-started/existing-repository.md).

## Model selection

The AI client owns its current model availability and default/automatic selection. EmbrAIon does not ship a canonical model catalog.

Optional project-specific selectors belong in `.embraion/routing.yaml`.

## Enforcement is separate

Installing an AI-client projection does not silently install executable merge enforcement. See [Enforcement](../guides/enforcement.md) when the project wants an explicit GitHub Actions gate.
