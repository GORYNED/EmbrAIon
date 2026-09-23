# Routing

Core routing is provider-neutral and separates five decisions:

- `access.yaml` — what the execution may read, write, execute, or expose;
- `complexity.yaml` — logical capability tier;
- `privacy.yaml` — data-class and exposure constraints;
- `fallback.yaml` — safe fallback semantics;
- `health.yaml` — operational health defaults.

Agent role, access profile, model route, and provider are independent dimensions.

Concrete current models belong to adapter catalogs under `adapters/**/models.yaml`. Host-specific route mappings live beside those catalogs.

<sub>Last updated: 2026-09-23 19:21 UTC</sub>
