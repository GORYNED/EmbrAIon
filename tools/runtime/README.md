# Runtime

This directory owns provider-neutral runtime orchestration and normalized session state.

Reusable runtime responsibilities include:

- context construction;
- diagnostic redaction;
- routing-registry access;
- bounded worker invocation;
- telemetry reconciliation;
- writer-safety coordination;
- normalized task/session state.

A session record can describe the active task, agent role, host, model, effort, access profile, workspace identity, lifecycle state, validation state, and review state without persisting prompt content or raw reasoning.

Provider-specific transport belongs in `adapters/providers/`. Project-specific credentials, data classes, report roots, and source identities stay in project overlays.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
