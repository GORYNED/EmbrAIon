# Codex

The Codex adapter maps EmbrAIon roles and route classes into Codex-specific configuration.

Install it into a project:

```bash
embraion install --host codex --destination .
```

Typical generated shape:

```text
.codex/
├── config.toml
└── agents/
    ├── analyst.toml
    ├── architect.toml
    ├── reviewer.toml
    ├── validator.toml
    └── ...
```

Core owns the reusable role and access semantics. The Codex adapter owns Codex-specific model identities, reasoning-effort mappings, and projection details.

Use:

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

to inspect a route without executing a model.
