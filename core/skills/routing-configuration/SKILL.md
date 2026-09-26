---
name: routing-configuration
description: Configure model-agnostic EmbrAIon routing and project-owned deployments using selectors and capabilities supported by the consuming project's execution hosts.
---

# Routing Configuration

Use this skill when the user asks to choose, assign, replace, optimize, or override models, reasoning effort, execution deployments, providers, or host-specific model options for EmbrAIon.

## Canonical locations

Reusable project-owned execution choices belong in:

`.embraion/deployments.yaml`

Route and role selection belongs in:

`.embraion/routing.yaml`

under `overrides.<host>.routes`, and, when a role-specific choice is needed, `overrides.<host>.roles`.

EmbrAIon Core intentionally has no canonical model catalog. A consuming project may define a deployment registry because those values belong to that project, its accounts, its hosts, and its runtime environment.

Do not create framework-owned model catalogs under Core or adapters, and do not create parallel project model registries outside the canonical `.embraion/deployments.yaml` file.

## Procedure

1. Identify the execution hosts/surfaces used by the project.
2. Inspect the models and settings currently available through those hosts when the host exposes them.
3. Preserve host-default/automatic model selection unless the user wants an explicit project choice.
4. When a model choice is reused, define one project deployment in `.embraion/deployments.yaml` instead of duplicating the selector across routes.
5. Put provider identity, host, model selector, supported/default effort, billing metadata, eligibility capabilities, and non-secret project metadata on the deployment.
6. Never store credentials, tokens, API keys, or other secret values in the registry.
7. Point route/role overrides at a deployment id and optionally provide a route-specific effort/options override.
8. Use ordered `fallbacks` only when the project owns an explicit fallback policy. Every fallback must reference another declared deployment.
9. Direct `model`, `effort`, and `options` overrides remain valid for simple one-off host selection and backwards compatibility.
10. Verify with `embraion route` and inspect the registry with `embraion deployment list/show`.

## Example shape

```yaml
# .embraion/deployments.yaml
providers:
  example:
    display-name: Example Provider

deployments:
  primary:
    host: codex
    provider: example
    model: any-host-model-selector
    efforts: [medium, high]
    default-effort: medium
    billing:
      mode: subscription
    capabilities:
      data-classes: [PUBLIC, PRIVATE]
      access-modes: [read-only, workspace-write]
```

```yaml
# .embraion/routing.yaml
overrides:
  codex:
    routes:
      substantial:
        deployment: primary
        effort: medium
```

The example values are placeholders, not EmbrAIon-owned model names.

## Guardrails

- Deployment/model choice never expands privacy, access, ownership, protected-source, validation, or review permissions.
- Keep global model availability truth with execution hosts; the registry records only consuming-project choices.
- Keep user/project-specific choices in the consuming project's overlay, not in EmbrAIon Core or shared adapters.
- Do not rewrite unrelated routing or deployment entries.
- Do not persist credentials, tokens, secret environment values, or raw authentication material.
- A referenced deployment must exist, be enabled, match the selected host, and satisfy declared effort/data/role/access/task capabilities.
- If a selector or capability cannot be verified, preserve the current route and surface the uncertainty instead of guessing.
