# Agents

Core agents are **job-like roles**. Their names describe who performs responsibility, not what document or task happens to be involved.

Current canonical roles:

- `lead` — owns routing, synthesis, protected decisions, and delivery.
- `worker` — performs bounded writable implementation.
- `reviewer` — independently reviews completed changes.
- `architect` — owns architecture and capability-boundary analysis.
- `analyst` — resolves requirements, intent, and structured analysis.
- `validator` — plans and collects validation evidence.
- `researcher` — performs bounded read-only research.
- `steward` — protects compatibility, persistence, and migration contracts.

Agent definitions remain model-neutral. Concrete models are selected by routing and adapter catalogs.

<sub>Last updated: 2026-09-23 18:11 UTC</sub>
