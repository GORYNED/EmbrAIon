# Codex

The Codex adapter projects EmbrAIon roles, skills, and host configuration into Codex-native files.

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

Core owns reusable role, complexity, access, privacy, validation, and review semantics. EmbrAIon does not pin a Codex model in the generated config.

Without a project routing override, Codex keeps its own default/automatic model selection. Optional project overrides can pass any Codex-understood model selector, effort string, or host-specific options.

Use:

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

to inspect whether the route resolves to `host-default` or a project override without executing a model.
