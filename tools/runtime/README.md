# Runtime

This directory owns provider-neutral runtime orchestration.

Reusable runtime responsibilities include context construction, diagnostic redaction, routing-registry access, bounded worker invocation, telemetry reconciliation, and writer-safety coordination.

Provider-specific transport belongs in `adapters/providers/`. Project-specific credentials, data classes, report roots, and source identities stay in project overlays.

<sub>Last updated: 2026-09-23 19:04 UTC</sub>
