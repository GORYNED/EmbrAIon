# Routing

Core routing is model-agnostic and separates five decisions:

- `access.yaml` — what the execution may read, write, execute, or expose;
- `complexity.yaml` — task-oriented route classes: `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, and `critical`;
- `privacy.yaml` — data-class and exposure constraints;
- `fallback.yaml` — safe rerouting semantics;
- `health.yaml` — operational health defaults.

Agent role, access profile, route class, execution host, and optional project model override are independent dimensions.

The route classes describe the work and risk, not model strength, price, reasoning tier, or vendor. EmbrAIon does not maintain a canonical list of current models. By default a route resolves to the selected host's own default/automatic model policy. A consuming project may optionally override a route or role with any host-understood model selector, effort string, or host-specific options in `.embraion/routing.yaml` under `overrides`.

Project overrides never expand Core access or privacy policy. Host/model availability is ultimately validated by the execution host, not by a framework-wide model catalog. Project task classes may compose ordered availability candidates across hosts and separate explicit quality or critical escalation routes. An unavailable deployment never raises assignment complexity. Each re-review is a new bounded assignment classified from its actual delta; previous complexity is evidence, not an inherited route.

`.embraion/**` is the only manually maintained source of truth for concrete routing, deployment capabilities, billing, pricing/SKU, and execution bindings. All host projections inherit the `routing-configuration` skill and are derived outputs.

<sub>Last updated: 2026-09-27 20:17 UTC</sub>
