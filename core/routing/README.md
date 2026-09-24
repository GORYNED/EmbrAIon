# Routing

Core routing is model-agnostic and separates five decisions:

- `access.yaml` — what the execution may read, write, execute, or expose;
- `complexity.yaml` — task-oriented route classes: `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, and `critical`;
- `privacy.yaml` — data-class and exposure constraints;
- `fallback.yaml` — safe rerouting semantics;
- `health.yaml` — operational health defaults.

Agent role, access profile, route class, execution host, and optional project model override are independent dimensions.

The route classes describe the work and risk, not model strength, price, reasoning tier, or vendor. EmbrAIon does not maintain a canonical list of current models. By default a route resolves to the selected host's own default/automatic model policy. A consuming project may optionally override a route or role with any host-understood model selector, effort string, or host-specific options in `.embraion/project.yaml`.

Project overrides never expand Core access or privacy policy. Host/model availability is ultimately validated by the execution host, not by a framework-wide model catalog.

<sub>Last updated: 2026-09-24 13:45 UTC</sub>
