---
name: compatibility-migration
description: Plan and verify a scoped change to persisted shapes, stable identity, public APIs, or their consumers.
---

# Compatibility Migration

Load when a change can alter persisted data, stable IDs, public APIs, serialized names, or import/export contracts. Skip for internal refactoring with verified private reach and no compatibility surface; use ordinary implementation and validation there.

1. Before changing code, record the observed baseline for public APIs, persisted shapes, and stable identities from code, representative historical fixtures or released artifacts, project compatibility and persistence slots, and known consumers. Identify the intended new contract and include readers, writers, migrations, generated artifacts, external users, and version boundaries. Ask the project Steward to resolve unresolved identity or data-loss risk through the established workflow.
2. Choose the smallest compatible path: preserve the old surface, add a versioned reader/writer, or define an explicit breaking migration where authorized. Map each old form to the new form, including missing, malformed, and older records. Do not infer that a rename is safe merely because source references compile.
   - Never reuse a retired identifier, number, or name for a different meaning. A rename is a removal plus an addition.
   - Deprecate before removing: mark the old surface, name its replacement, and state how long it keeps working.
   - Readers tolerate unknown fields, so a newer writer does not break an older reader.
3. Sequence changes so existing consumers continue working during rollout. State any dual-read/write window, upgrade order, backup or recovery requirement, and rollback boundary. A failed migration must leave the source data intact and recoverable: keep the original until the new form is verified. Avoid turning one compatibility fix into a mass refactor.
4. Recheck the same representative historical fixtures and affected current consumers after the change against the pre-change baseline, except for explicitly authorized differences. Check stable identifiers, read/write round trips where meaningful, public call sites, and rollback or recovery behavior that the project actually supports.

Stop when affected contracts and consumers have evidence for the authorized migration or an unresolved compatibility risk blocks progress. Output: the baseline and affected contract and consumer inventory, migration mapping and sequence, fresh validation evidence, explicit authorized differences and rollback limits, and residual risk. Follow project-owned contracts and canonical privacy, review, and approval gates.
