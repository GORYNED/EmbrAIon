# Host Integrations

EmbrAIon keeps one canonical Core and project contract, then projects the relevant pieces into the integration used by each repository.

Codex, GitHub Copilot, and Claude Code are executable AI hosts. **Portable is different:** it is a host-neutral capability bundle for integrations that need EmbrAIon data without adopting one of those host-native layouts.

| Integration | Typical generated locations | What EmbrAIon projects |
| --- | --- | --- |
| Codex | `.codex/`, `.agents/skills/` | config, specialist agents, skills |
| GitHub Copilot | `.github/agents/`, `.github/skills/` | custom agents, skills |
| Claude Code | `.claude/agents/`, `.claude/skills/` | agent definitions, skills |
| Portable bundle | `embraion/` inside the chosen destination | host-neutral capability bundle |

Generated files are projections. Canonical reusable behavior remains in EmbrAIon Core; project-specific configuration remains under `.embraion/`.

## Install a host projection

```bash
embraion install --host codex --destination .
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
```

A repository can support multiple hosts at the same time.

For the host-neutral bundle:

```bash
embraion install --host portable --destination vendor/embraion
```

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

## Conversational project configuration

Host installation and project configuration are separate concerns.

Use [Conversational Project Configuration](../configuration/ai-hosts.md) when you want the AI already working in the repository to update knowledge, policy, deployments, routing, validation, or project agents from natural-language intent.

## Model selection

The AI host owns its current model availability and default/automatic selection. EmbrAIon does not ship a canonical model catalog.

Optional project-specific selectors belong in `.embraion/routing.yaml` or reusable project deployments.

## Enforcement is separate

Installing a host projection does not silently install executable merge enforcement. See [Enforcement](../guides/enforcement.md) when the project wants an explicit GitHub Actions gate.
