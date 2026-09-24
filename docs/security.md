# Security

EmbrAIon treats execution permissions, data classification, provider eligibility, external integrations, generated configuration, credentials, and mutation rights as enforceable engineering constraints.

Security policy belongs in Core rules and project policy. Host/provider adapters implement their mechanics, while deterministic tools inspect configuration, external integrations, and persisted evidence.

## Fail-closed behavior

The framework should fail closed when:

- a task cannot be safely classified;
- a provider or execution path is not permitted for the relevant data;
- an integration has unknown or unexpectedly broader access;
- a secret appears in persisted configuration;
- generated configuration drifts from its approved source;
- a writable action exceeds its access profile or owned paths;
- protected project sources would be mutated without the required path.

Security findings are evidence, not permission to weaken the controlling policy.

## Runtime redaction and environment handling

Runtime state applies credential redaction before persistence.

For child processes launched by EmbrAIon-owned adapters, the framework constructs a minimal allowlisted environment instead of forwarding the host environment wholesale. Captured child-process output is redacted before it is stored as evidence.

Host-native agents launched by an external AI client remain subject to that host's own environment and credential controls. EmbrAIon does not claim to override security boundaries owned by the host.

## External integrations

MCP and other external server/tool configuration is inventoried separately from Core policy. Inventory records privacy-safe metadata and drift rather than secret values.

Use:

```bash
embraion security scan --path . --fail-on high
embraion mcp inventory
```

to inspect deterministic security and integration surfaces.

## Project policy and enforcement

Project-owned source classes, privacy defaults, review rules, and enforcement settings live in `.embraion/policy.yaml`.

A green test or behavioral eval cannot override privacy, protected-source, permission, or security failures. Likewise, model routing cannot widen these boundaries.

See [Policy & Protected Paths](configuration/policy.md) and [Enforcement](guides/enforcement.md).
