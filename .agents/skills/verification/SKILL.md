---
name: verification
description: Verify a final candidate before completion claims, handoff, release, or merge readiness.
---

# Verification

## Procedure

1. Inspect the final diff and confirm only intended files changed.
2. Re-check acceptance criteria against the final candidate, not an earlier intermediate state.
3. Confirm required validation evidence is fresh and applicable.
4. Confirm required independent review is complete.
5. Check documentation, generated projections, schemas, and references for consistency.
6. Confirm known risks are explicitly reported.
7. Only then declare the candidate ready for handoff.

## Guardrails

- Do not rely on memory of earlier passes.
- Do not claim completion while required evidence is stale or missing.
- Do not hide unresolved risk behind a successful test count.
