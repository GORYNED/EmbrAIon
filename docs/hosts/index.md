# Host Integrations

EmbrAIon keeps one canonical Core and project contract, then projects the relevant pieces into each supported integration.

!!! tip "In plain English"
    You keep the project rules once. EmbrAIon writes the native agent/skill files expected by the AI client you use.

## Choose your path

- **I use one AI host:** install its projection and keep the rest of the project contract under `.embraion/`.
- **I support several hosts or a custom integration:** use the same canonical project contract and install the relevant projections, including the host-neutral Portable bundle when appropriate.

| Integration | Typical generated locations | What EmbrAIon projects |
| --- | --- | --- |
| Codex | `.codex/`, `.agents/skills/` | config, specialist agents, skills |
| GitHub Copilot | `.github/agents/`, `.github/skills/` | custom agents, skills |
| Claude Code | `.claude/agents/`, `.claude/skills/` | agent definitions, skills |
| Portable bundle | `embraion/` inside the chosen destination | host-neutral capability bundle |

## Install

```bash
embraion install --host codex --destination .
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
```

For the host-neutral bundle:

```bash
embraion install --host portable --destination vendor/embraion
```

## Existing host configuration

Preview before writing:

```bash
embraion projection diff --host codex --destination .
```

Mature repositories can adopt only selected components.

## Conversational project configuration

Host installation and project configuration are separate concerns.

Use [Conversational Project Configuration](../configuration/ai-hosts.md) when you want the AI already working in the repository to update knowledge, policy, deployments, routing, validation, or project agents.

## Model selection

The AI host owns its current model availability and default/automatic selection. EmbrAIon does not ship a canonical model catalog.

## Enforcement is separate

Installing a host projection does not silently install executable merge enforcement.
