# Core

`core/` contains vendor-neutral canonical EmbrAIon behavior.

```text
core/
├── catalog.yaml
├── rules/
├── agents/
├── skills/
├── workflows/
├── routing/
└── knowledge/
```

`catalog.yaml` is the machine-readable index used to discover only the capabilities relevant to a task rather than loading the entire framework.

Core defines policy and responsibility. It does not contain host-specific configuration, provider transport mechanics, project-specific domains, or current provider model identifiers.

Spec Kit remains a recommended external capability for substantial specification-driven work.

<sub>Last updated: 2026-09-23 19:21 UTC</sub>
