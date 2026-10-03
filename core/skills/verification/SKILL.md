---
name: verification
description: Verify a final candidate before completion claims, handoff, release, or merge readiness.
---

# Verification

## Procedure

1. Inspect the full cumulative final diff against the reviewed base and confirm only intended files changed. For a PR identify the source HEAD SHA.
2. Re-check acceptance criteria against the final candidate, not an earlier intermediate state.
3. Confirm required tests and CI are fresh, passing, and applicable to that exact candidate. Reconcile any checkpoint or resumed session with the current candidate, environment, and evidence; changes invalidate affected results and review confirmation. For UI behavior, identify what was observed in live interaction and what was only inspected statically. Record checks legitimately not required by impact; pending, missing, failing, stale, or unavailable required evidence blocks readiness.
4. Confirm the author's full diff and related-code self-review preceded independent review. For every PR or substantial implementation, confirm a different read-only Reviewer in the same authorized host reviewed the cumulative candidate and explicitly confirmed the final PR source HEAD SHA, reviewed base/diff, and current evidence. Any later candidate content or commit change invalidates confirmation.
5. Check documentation, generated projections, schemas, and references for consistency.
6. Confirm known risks are explicitly reported.
7. Only then declare the candidate ready for handoff. Immediately before an authorized squash merge, recheck the PR source HEAD and reviewed diff; preserve separate user merge and release approval.

## Guardrails

- Do not rely on memory of earlier passes.
- Do not claim completion while required evidence is stale or missing.
- Do not hide unresolved risk behind a successful test count.
- Do not treat Reviewer confirmation as merge or release authorization.
