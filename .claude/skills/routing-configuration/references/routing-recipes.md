# Routing recipes

Shapes and checks for the files this skill owns. The skill body holds the authority rules; this file holds what to write and how to verify it. `embraion validate --strict` checks only key names. The loader commands below check the full shape, so always run them. Every value in an example is a placeholder: use selectors, efforts, and options that the host reports or the user confirms, never the placeholder text.

## configure-routing

Fills `deployments.yaml` (`providers`, `deployments`) and `routing.yaml` (`overrides`, `task-classes`, `candidate-groups`).

- Discover: which hosts the project uses (`embraion status` lists installed projections); the selectors and efforts each host reports; existing deployments and routes, which you keep.
- Ask: which hosts to tune, the goal in plain words (cheaper ordinary work, stronger complex work, reserved critical route), and whether the project owns a fallback policy. Do not ask for YAML details.
- A bare "configure routing" request does not require a change when host-default already fits. `overrides: {}` is valid. Say so and stop rather than inventing a choice.

Deployment (a reusable named choice; `host` and `model` are required, everything else optional):

```yaml
providers:
  example:
    display-name: Example Provider
deployments:
  fast-main:
    host: <host>
    provider: example
    model: <selector the host reports>
    enabled: true
    efforts: [<effort the host supports>]
    default-effort: <one of efforts>
    billing: {mode: subscription}
    capabilities:
      data-classes: [PUBLIC, PRIVATE]
      access-modes: [read-only, workspace-write]
      roles: [worker, reviewer]
      task-classes: [ordinary, substantial]
```

Route classes are `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, `critical`. Overrides, from least to most specific: `routes.<class>`, `roles.<role>`, `route-roles.<class>.<role>`, `task-classes.<id>`. Each selection names a `deployment` (or a direct `model`, never both), plus optional `effort`, `options`, and ordered `fallbacks` (each names another declared deployment):

```yaml
overrides:
  <host>:
    routes:
      ordinary: {deployment: fast-main}
      complex:
        deployment: deep-main
        effort: <effort>
        fallbacks: [{deployment: fast-main}]
    roles:
      reviewer: {deployment: deep-main}
```

Task classes give project meaning to a request type, with ordered host candidates and optional explicit escalations. A candidate group is a reusable ordered list of deployments:

```yaml
candidate-groups:
  review-pool:
    deployments:
      - {deployment: deep-main, effort: <effort>}
      - {deployment: fast-main}
task-classes:
  routine-review:
    route-class: substantial
    role: reviewer
    data-class: PRIVATE
    candidates:
      - {host: <host>, group: review-pool}
    escalations:
      quality: {host: <host>, deployment: deep-main, route-class: complex}
```

A candidate `effort` or `options` needs an explicit `deployment`. Escalation to `critical` needs a `critical` route class and a justification at use time.

Verify, in this order:

- `embraion route --validate` (loads and checks every route, task class, and group), `embraion deployment list`;
- one resolution per changed route: `embraion route --host <host> --route-class <class> --data PRIVATE`, or `embraion route --task-class <id> --access review`;
- `embraion route --audit-authority` (finds concrete routing facts copied outside `.embraion/`), `embraion policy check` (ceilings);
- after the edit, refresh stale projections with `embraion install --host <host> --destination .` and check `embraion check`.

Resolver success is not execution evidence: say that the host must still apply the selection natively.

## declare-execution-binding

Creates `execution.yaml`: reviewed bindings that let `embraion execute` call a provider. Skip it when the AI host does all the work.

- Each key under `bindings` is the id of a deployment declared in `deployments.yaml`. Declare the deployment first.
- Discover: the adapter and selector the deployment uses; `sourceIds` and `trustLevels` already used in `policy.yaml` `privacy.sources`.
- Ask for the name of the environment variable that holds the credential. Write only `credentialRef: env:NAME`. Never ask for, read, or write the value.
- Required per binding: `adapter`, `selector`, `sourceIds`, `trustLevels`. Common optional keys: `credentialRef`, `taskClasses`, `maxTimeoutSeconds`, `expectedProvider`, `contextBoundary`, `optionAllowlist`.

```yaml
schemaVersion: 1
bindings:
  analysis-api:
    adapter: <adapter name>
    selector: <upstream selector>
    credentialRef: env:EXAMPLE_API_KEY
    sourceIds: [Project]
    trustLevels: [verified]
    taskClasses: [substantial]
    maxTimeoutSeconds: 300
```

Verify: `embraion execution preflight --deployment <deployment-id>` (without `--deployment` it waits for a request on standard input; always pass it). It prints what is missing, such as an unset credential or adapter evidence, and makes no provider call. Report `NOT READY` reasons as they are; the user sets the environment variable. Then `embraion policy check`.

## declare-pricing

Creates `pricing.yaml`: approved official price pages and SKU patterns for cost calculation. EmbrAIon never fetches prices silently.

- Ask for the official pricing page of the provider. The loader accepts only an HTTPS URL on the official documentation host of the chosen `adapter` and says so when it refuses one. Ask permission before `embraion pricing refresh`, which reads the network.
- Required per source: `url`, `adapter` (`openai`, `anthropic`, `gemini`, `deepseek`), `currency` (three capital letters), `freshnessDays`, `skus`. Each SKU needs `sku` and `patterns`: at least one of `input`, `cachedInput`, `output`, `reasoning`, the ones the pricing page states. Copy SKU names and patterns from the page; never invent a rate.

```yaml
schemaVersion: 1
sources:
  <provider>:
    url: https://<official host>/<pricing page>
    adapter: <adapter>
    currency: USD
    freshnessDays: 30
    skus:
      primary:
        sku: <sku name from the page>
        patterns:
          input: "<text that labels the input price>"
          output: "<text that labels the output price>"
```

Verify: `embraion pricing status` (loads and validates the config), then, with the user's permission, `embraion pricing refresh` followed by `embraion pricing status`. A failed refresh keeps the last good snapshot.
