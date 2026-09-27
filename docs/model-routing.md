# Routing

EmbrAIon routing is model-agnostic.

It classifies **work and risk**, not model strength, price, provider, or marketing tier. Model availability changes quickly; project architecture and safety constraints should not.

![Model routing](assets/diagrams/en/12-model-routing.svg){ loading=lazy }

## Route classes

The canonical route classes are:

| Route class | Meaning |
| --- | --- |
| `bounded-read` | Narrow read-only discovery or research |
| `bounded-write` | Mechanical or tightly bounded writable work |
| `ordinary` | Limited ordinary engineering |
| `substantial` | Substantial engineering and standard review |
| `complex` | Cross-domain, lifecycle, concurrency, or difficult review |
| `critical` | Exceptional protected-decision risk |

These classes are stable framework vocabulary. They do not imply that a particular model is permanently “the complex model” or “the critical model”.

Routing is evaluated together with independent dimensions such as:

- role;
- data class;
- access mode;
- owned paths;
- project deployment capabilities;
- validation and review requirements.

## Default behavior

Without a project override, routing resolves to `host-default`. The selected host remains responsible for its own available models and automatic/default model policy.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

A default result therefore has no framework-selected model:

```json
{
  "host": "codex",
  "route": "substantial",
  "role": null,
  "resolution": "host-default",
  "model": null,
  "effort": null,
  "options": {},
  "data": "PRIVATE"
}
```

New models can appear in a host without requiring an EmbrAIon release.

## Optional project overrides

A project may define reusable concrete choices in `.embraion/deployments.yaml` and reference them from `.embraion/routing.yaml`:

```yaml
# .embraion/deployments.yaml
providers:
  example:
    display-name: Example Provider

deployments:
  complex-main:
    host: codex
    provider: example
    model: any-host-model-selector
    efforts: [medium, high]
    default-effort: high
```

```yaml
# .embraion/routing.yaml
overrides:
  codex:
    routes:
      complex:
        deployment: complex-main
        effort: high
    roles:
      reviewer:
        deployment: complex-main
        options:
          thinking: maximum
```

The registry is project-owned, not an EmbrAIon Core model catalog. Model/provider strings remain intentionally open-ended.

For simple project choices, direct `model`, `effort`, and `options` overrides are also supported:

```yaml
overrides:
  codex:
    routes:
      ordinary:
        model: any-host-model-selector
        effort: medium
```

Resolution precedence is:

1. role override, when a role is supplied;
2. route override;
3. host default/automatic selection.

A role override is merged over the route override, so a role can replace only the fields it needs.

## Routing is not provider execution

Routing answers **what should be selected**. It does not by itself create a provider call.

For host-native work, the AI host uses the resolved project contract and remains responsible for actual execution.

For projects that opt into `embraion execute`, the selected deployment must also have an approved `.embraion/execution.yaml` binding. The runtime can then execute the bounded candidate list and apply eligible fallback under the original request ceilings.

See [How EmbrAIon works](getting-started/how-it-works.md) and [Execution & providers](configuration/execution.md).

## AI-First configuration

Every installed host projection includes the reusable `routing-configuration` skill. It teaches the AI that routing overrides belong in `.embraion/routing.yaml`, not in generated host files or arbitrary documentation.

The intended user experience is conversational:

> Configure EmbrAIon routing for this repository using the models currently available to you. Keep host-default where no explicit choice is needed. Put model, effort, or host-specific overrides only in the project routing/deployment configuration. Do not weaken privacy, access, ownership, validation, or review policy.

The AI should inspect host-native model choices when available, change only project-owned configuration, and verify the affected routes.

## What EmbrAIon validates

EmbrAIon can deterministically validate:

- route-class and data-class names;
- project-override structure;
- role/route precedence;
- deployment existence/enabled state;
- host matching;
- supported effort;
- declared data/role/access/task capabilities;
- access and privacy policy that is independent from model identity.

The execution host remains authoritative for whether an opaque selector or option is actually available to the current user/account.

## Host-specific setup examples

See [AI host configuration examples](configuration/ai-hosts.md) for Codex, GitHub Copilot, and Claude Code workflows.
