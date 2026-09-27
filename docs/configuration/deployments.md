# Project Deployments

`.embraion/deployments.yaml` is the consuming project's reusable execution registry.

EmbrAIon Core remains model-agnostic: it does not ship a current model catalog and does not decide which vendor/model a project must use. The registry exists so a project can name the concrete execution choices it already owns and reuse those names from routing.

## Baseline

```yaml
providers: {}
deployments: {}
```

An empty registry means routing can continue to use host-default selection or direct model overrides.

## Define reusable deployments

```yaml
providers:
  example:
    display-name: Example Provider
    homepage: https://example.com

deployments:
  native-main:
    host: codex
    provider: example
    model: example-model-selector
    enabled: true
    efforts: [medium, high]
    default-effort: medium
    billing:
      mode: subscription
      plan: Example Plan
    capabilities:
      data-classes: [PUBLIC, PRIVATE]
      access-modes: [read-only, workspace-write]
      roles: [worker, reviewer]
      task-classes: [substantial, complex]
    options:
      example-option: true
```

The model/provider strings are project-owned values. EmbrAIon validates structure and deterministic eligibility; it does not claim that a selector is globally available.

A deployment requires `host` and `model`. It may also declare provider identity, enabled state, supported/default effort, billing metadata, eligibility capabilities, host options, and non-secret metadata.

Do not put credentials, tokens, API keys, or secret environment values in this file.

## Route by deployment id

```yaml
overrides:
  codex:
    routes:
      substantial:
        deployment: native-main
        effort: medium
```

The resolved route reports the deployment id, provider, model, effort, billing metadata, and merged options.

## Fallback chains

```yaml
overrides:
  codex:
    routes:
      substantial:
        deployment: native-main
        fallbacks:
          - deployment: native-backup
            effort: low
```

Fallbacks in `.embraion/routing.yaml` are a **selection plan**. EmbrAIon verifies that every referenced deployment exists, is enabled, belongs to the selected host, and satisfies declared route/data/role/access/effort capabilities.

Project task-class profiles may compose those host-local selections with explicitly ordered candidates on other hosts. A cross-host candidate is a handoff boundary with a fresh privacy/access decision, not an automatic provider switch. Availability fallback never raises complexity; quality and critical escalation are separate explicit selections.

What happens next depends on the execution lane:

- for **host-native work**, the AI host remains responsible for actually running the selected model/tool workflow;
- for **provider-neutral execution**, a caller can pass a bounded candidate set to `embraion execute`; EmbrAIon then owns the attempt loop, failure normalization, health-aware ordering, and eligible fallback under the original request ceilings.

A deployment is therefore not the transport itself. Provider invocation requires an approved `.embraion/execution.yaml` binding.

## Fail-closed behavior

A deployment route is rejected when the deployment is missing or disabled, belongs to another host, references an undeclared provider, requests unsupported effort, violates declared capabilities, or forms a duplicate/self fallback.

## Inspect the registry

```bash
embraion deployment list
embraion deployment list --json
embraion deployment show native-main
embraion deployment show native-main --json
```

Use [Model routing](../model-routing.md) for route/role precedence and host-default behavior, [Execution & providers](execution.md) for executable bindings, and [Pricing & cost](pricing.md) for cost evidence.
