---
name: compatibility-migration
description: Plan and verify a scoped change to persisted shapes, stable identity, public APIs, or their consumers.
---

# Compatibility Migration

Load when a change can alter persisted data, stable IDs, public APIs, serialized names, or import/export contracts. Skip for internal refactoring with verified private reach and no compatibility surface; use ordinary implementation and validation there.

1. Identify the exact old and new contract from code, released artifacts, project compatibility and persistence slots, and known consumers. Include readers, writers, migrations, generated artifacts, external users, and version boundaries. Ask the project Steward to resolve unresolved identity or data-loss risk through the established workflow.
2. Choose the smallest compatible path: preserve the old surface, add a versioned reader/writer, or define an explicit breaking migration where authorized. Map each old form to the new form, including missing, malformed, and older records. Do not infer that a rename is safe merely because source references compile.
3. Sequence changes so existing consumers continue working during rollout. State any dual-read/write window, upgrade order, backup or recovery requirement, and rollback boundary. Avoid turning one compatibility fix into a mass refactor.
4. Validate with representative historical fixtures and affected current consumers. Check stable identifiers, read/write round trips where meaningful, public call sites, and rollback or recovery behavior that the project actually supports.

Output: affected contract and consumer inventory, migration mapping and sequence, fresh validation evidence, explicit rollback limit, and residual risk. Follow project-owned contracts and canonical privacy, review, and approval gates.
