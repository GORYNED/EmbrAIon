# Portable

Portable is a host-neutral capability bundle rather than another AI host.

Install it into a dedicated destination:

```bash
embraion install --host portable --destination vendor/embraion
```

The generated bundle includes canonical discoverable capabilities such as:

```text
embraion/
├── plugin.json
├── catalog.yaml
├── skills/
├── knowledge/
└── routing/
```

Portable is useful when an integration needs EmbrAIon capabilities without adopting Codex-, Copilot-, or Claude-specific configuration.
