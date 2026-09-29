# Conversational Project Configuration

You do not have to hand-edit every `.embraion/` file. The AI client already working in the repository can help configure project-owned EmbrAIon settings.

This page is about **changing the project contract through natural-language intent**. Host installation, generated file locations, and host-specific ownership rules live under [Host Integrations](../hosts/index.md).

> EmbrAIon does not intercept your prompt. The installed host projection teaches the AI client where the repository's canonical EmbrAIon configuration lives and which reusable roles/skills are available.

## Ordinary engineering vs configuration

An ordinary engineering request:

> Fix the retry behavior when the service connection fails.

should use the existing project contract.

A configuration request:

> Configure routing so bounded work uses inexpensive models, complex architecture uses stronger reasoning, and the critical route is reserved for exceptional risk.

should intentionally change the canonical project contract.

The host should not rewrite `.embraion/` merely because an ordinary product task was requested.

## Canonical ownership

| User intent | Canonical file |
| --- | --- |
| Change project identity or capabilities metadata | `.embraion/project.yaml` |
| Register architecture/domain knowledge | `.embraion/knowledge.yaml` |
| Mark protected/canonical/generated/external paths | `.embraion/policy.yaml` |
| Register reusable concrete model/provider choices | `.embraion/deployments.yaml` |
| Change model routing | `.embraion/routing.yaml` |
| Add project validation commands | `.embraion/validation.yaml` |
| Declare project-specific agents | `.embraion/agents.yaml` |
| Configure optional provider execution bindings | `.embraion/execution.yaml` |
| Configure optional pricing sources | `.embraion/pricing.yaml` |

Generated host files are projections, not a second configuration authority.

![Canonical configuration to AI host projections](../assets/diagrams/en/10-ai-host-projections.svg){ loading=lazy }

## Project Bootstrap

> Configure EmbrAIon for this project.

This short request loads the canonical Core `project-bootstrap` procedure. Lead discovers existing repository truth, preserves settings, configures useful knowledge/policy/validation, keeps agents minimal and routing optional, then verifies the result. See [Project Bootstrap](bootstrap.md) for discovery, documentation safeguards, repeated setup, and limitations.

For explicit tuning:

> Configure EmbrAIon completely for this project, including routing using the models and reasoning settings actually available to my AI host.

## Routing request

> Configure EmbrAIon routing for this repository using the models and reasoning settings actually available to this host. Keep host-default where explicit routing adds no value, preserve project safety policy, and verify the resulting routes.

## Knowledge request

> Register the current architecture and compatibility documents as EmbrAIon project knowledge. Prefer Project Contract Slots when they match an existing source of truth. Do not duplicate the documents into YAML.

## Policy request

> Review this repository's source ownership. Mark first-party source as canonical, generated artifacts as generated, vendor-managed code as external or protected as appropriate, and preserve any stricter existing restrictions.

## Validation request

> Add deterministic project validation commands to the appropriate EmbrAIon profiles. Keep fast inexpensive, affected scoped to normal changes, and full reserved for the broad project gate. Do not treat an empty profile as a pass.

## Project-agent request

> Add a project-specific read-only specialist for this domain only if the existing Core roles are not sufficient. Reuse a compatible Core role where possible and do not widen its access boundary.

## Host-specific setup

Use the dedicated host pages for installation and projection ownership:

- [Codex](../hosts/codex.md)
- [GitHub Copilot](../hosts/copilot.md)
- [Claude Code](../hosts/claude-code.md)
- [Portable bundle](../hosts/portable.md)
