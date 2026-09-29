# Routing

EmbrAIon routing is model-agnostic.

It classifies **work and risk**, not model strength, price, provider, or marketing tier. Model availability changes quickly; project architecture and safety constraints should not.

![Model routing](assets/diagrams/en/12-model-routing.svg){ loading=lazy }

## Assignment flow across hosts

```text
User task → Lead decomposition → delegated assignment
  → independent assignment classification → project route resolution
  → active host surface capability check → native model/effort application
  → execution evidence → validation/review → Lead integration
```

Role != Route != Model. Every new or reused assignment is assessed from its actual scope, role, data class, access, and owned paths. Reuse cannot change settings through a message tool that does not support them. Host-default needs no explicit mapping and still supports delegation. Explicit selections require proof that native execution applied them; unknown fields, silent inheritance, substitution, and capping cannot satisfy a mandatory route.

| Surface | Native settings and limits |
| --- | --- |
| Codex verified spawn schema | Separate role/model/effort fields; explicit overrides need a bounded or no-history fork; loaded role definitions can override spawn |
| Copilot CLI | Definition model/ordered models, policy and effort; per-call fields need installed-schema proof; Auto and precedence can cause inheritance |
| Copilot VS Code | Per-call/definition model; effort needs installed-version/schema proof; parent cost tier may constrain selection |
| Copilot cloud/general | Definition model established; CLI-only policy/effort/list controls are not assumed |
| Claude Code | Per-call model where verified; explicit effort through loaded assignment-specific definition or supported handoff, not an invented Agent effort field |
| Portable | Contract/capability metadata only; no spawn or model runtime |

See [host documentation](hosts/index.md) for precedence and effective-setting checks. Unsupported mandatory settings cause a capability limitation before dispatch or a supported handoff; changing host requires fresh privacy/access checks. A prepared plan has `executed: false` and does not prove execution.

Default [Project Bootstrap](configuration/bootstrap.md) preserves optional routing. Ask for full/tuned bootstrap only when you want project-owned deployment and route choices.

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

## Project task classes and effective routes

Projects can define their own semantic task classes in `.embraion/routing.yaml`. Each class names a Core route class, an optional role and minimum data class, and an ordered list of host candidates. A candidate can use that host's route/role/task-class override, name a deployment directly, or expand a project candidate group. Host route fallbacks are inserted immediately after that host's primary candidate. Task-class overrides take precedence over route-role, role, and route overrides.

```yaml
task-classes:
  routine-review:
    route-class: substantial
    role: reviewer
    data-class: PRIVATE
    candidates: [{host: review-host}, {host: native-host, deployment: native-review}]
    escalations:
      quality: {host: native-host, deployment: deep-review, route-class: complex}
      critical: {host: native-host, deployment: protected-review, route-class: critical}
overrides:
  review-host:
    task-classes:
      routine-review: {deployment: review-primary}
```

These identifiers are project examples, not Core models. Resolve with `embraion route --task-class routine-review --access review`. The JSON result reports the selected deployment, ordered availability candidates, separate escalation choices, and selection provenance. `embraion route --validate` checks all declared task classes and groups. `embraion route --audit-authority` finds duplicate concrete routing facts in manually maintained consumer files.

Availability fallback follows only the declared candidate order and never changes the task's complexity. A cross-host candidate requires a fresh privacy/access decision and an explicit handoff. Quality or critical escalation is selected only with `--escalation` and `--justification`; critical escalation must name the `critical` route class, and any selected critical task route requires justification. Each re-review is a new bounded assignment classified from its actual delta. A narrow fix check can use `substantial` after a complex initial review, while changes to concurrency, lifecycle, compatibility, or architecture semantics remain `complex`.

`.embraion/**` is the only manually maintained authority for concrete provider/model/deployment/effort/routing/fallback facts, deployment capabilities, billing, pricing/SKU, and execution bindings. Store credential references in `.embraion/execution.yaml`, not secret values. Consumer tests and docs should refer to semantic classes and query EmbrAIon for resolved choices. Generated host projections are derived outputs, never a second authority.

## Routing is not provider execution

Routing answers **what should be selected**. It does not by itself create a provider call.

For host-native work, the AI host uses the resolved project contract and remains responsible for actual execution.

For Codex delegation, Lead classifies each concrete assignment independently and queries `embraion route` with that assignment's role, route class, data class, and access mode, or a configured task class, before native spawn. The previous assignment's complexity and the role name do not select a model. Explicit resolved model/effort choices are passed through supported native spawn parameters; `host-default` uses the host's subagent defaults or inheritance.

The Codex adapter omits model/effort fields from generated specialist files because Codex role-file overrides take precedence over explicit spawn choices. Config merge preserves user `default_subagent_model` and `default_subagent_reasoning_effort` settings as host defaults. EmbrAIon-managed concrete assignment choices remain in `.embraion/**`; generated files are not a second routing authority. See the official [config reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Static TOML cannot evaluate the resolver at each spawn. The projected Lead instructions guide the host to perform that step; trust, permissions, higher-priority instructions, and native capabilities still apply. If a required explicit choice cannot be applied, Lead must report and resolve the limitation before dispatch, rather than claim execution used it. Cross-host routes require an explicit handoff and fresh privacy/access checks. Role, access, route class, host, and model selection stay independent.

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
