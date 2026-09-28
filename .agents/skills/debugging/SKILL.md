---
name: debugging
description: Diagnose failures systematically by reproducing the symptom, narrowing the cause, testing hypotheses, and verifying the fix.
---

# Debugging

## Procedure

1. Reproduce the failure or establish the strongest deterministic evidence available.
2. Separate symptom, trigger, and suspected cause.
3. Reduce the search space using logs, diffs, tests, boundaries, and recent changes.
4. Form one falsifiable hypothesis at a time.
5. Test the hypothesis with the smallest useful experiment.
6. Change implementation only after the cause is sufficiently supported.
7. Add or update a regression check when practical.
8. Verify the original failure no longer reproduces and that adjacent behavior remains intact.

## Guardrails

- Do not make random edits until the symptom disappears.
- Do not confuse correlation with root cause.
- Do not hide intermittent or environment-specific behavior.
- Preserve diagnostic evidence needed for review.
