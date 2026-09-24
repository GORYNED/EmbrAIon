---
name: routing-configuration
description: Configure model-agnostic EmbrAIon routing for a consuming project by editing only project routing overrides with model selectors and options supported by the active AI host.
---

# Routing Configuration

Use this skill when the user asks to choose, assign, replace, optimize, or override models, reasoning effort, or host-specific model options for EmbrAIon.

## Canonical location

Project model-routing overrides belong only in:

`.embraion/routing.yaml`

under:

`overrides.<host>.routes`

and, when a role-specific choice is needed:

`overrides.<host>.roles`

Do not create an EmbrAIon model registry, `models.yaml`, or another parallel model-configuration file.

## Procedure

1. Identify the AI host used by the project, such as Codex, GitHub Copilot, or Claude Code.
2. Inspect the models and model settings currently available through that host when the host exposes them. EmbrAIon intentionally has no canonical model catalog.
3. Preserve host-default/automatic model selection unless the user wants an explicit override.
4. Translate the user's intent into the existing EmbrAIon route classes and, only where useful, role-specific overrides.
5. Edit only the relevant `overrides` subtree in `.embraion/routing.yaml`; preserve unrelated project policy and configuration.
6. Treat `model`, `effort`, and `options` as opaque host-owned values. Do not invent a selector when the host cannot confirm it.
7. Apply route settings first and role settings as the more specific override.
8. Verify the resolved result with `embraion route` for the affected route/role and inspect `embraion policy show` when policy context matters.

## Example shape

```yaml
overrides:
  codex:
    routes:
      complex:
        model: any-host-model-selector
        effort: high
    roles:
      reviewer:
        model: any-review-model-selector
        options:
          thinking: maximum
```

The example values are placeholders, not EmbrAIon-owned model names.

## Guardrails

- Model choice never expands privacy, access, ownership, protected-source, validation, or review permissions.
- Keep model availability and capability truth with the execution host.
- Keep user-specific model choices in the consuming project's overlay, not in EmbrAIon Core or shared adapters.
- Do not rewrite unrelated routing entries in `.embraion/routing.yaml`.
- Do not persist credentials, tokens, or other secrets in routing overrides.
- If the requested selector or option cannot be verified, preserve the current route and surface the uncertainty instead of guessing.
