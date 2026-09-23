# Security

EmbrAIon treats execution permissions, data classification, provider eligibility, external integrations, generated configuration, credentials, and mutation rights as enforceable engineering constraints.

Security policy belongs in Core rules and routing. Host/provider adapters implement their mechanics. `tools/security/` performs deterministic inspection, while `tools/mcp/` normalizes external server inventory and drift.

The framework should fail closed when:

- a task cannot be safely classified;
- a provider is not permitted for the relevant data;
- an integration has unknown or unexpectedly broader access;
- a secret appears in persisted configuration;
- generated configuration drifts from its approved source;
- a writable action exceeds its access profile.

Security findings are evidence, not permission to weaken the controlling policy.
