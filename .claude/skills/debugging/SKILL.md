---
name: debugging
description: Diagnose failures systematically by reproducing the symptom, narrowing the cause, testing hypotheses, and verifying the fix.
---

# Debugging

Use for a material or uncertain failure whose cause needs diagnosis. A self-evident typo can be corrected and verified without a hypothesis record.

## Procedure

1. Reproduce the failure or establish the strongest deterministic evidence available.
2. Separate symptom, trigger, and suspected cause.
3. Reduce the search space using logs, diffs, tests, boundaries, and recent changes.
4. State the leading causal hypothesis, a plausible competing cause when one exists, and the observation that would distinguish them.
5. Run the smallest permitted experiment that could falsify the leading hypothesis; preserve its result before editing.
6. Change implementation only after the cause is sufficiently supported. If fixes repeatedly fail or evidence contradicts the cause, revisit the hypothesis and narrow the reproduction.
7. Add or update a regression check when practical.
8. Stop when the original failure no longer reproduces and the affected adjacent contract remains intact. Report the cause, discriminating evidence, fix, checks, and any unresolved limit.

## Guardrails

- Do not make random edits until the symptom disappears.
- Do not confuse correlation with root cause.
- Do not hide intermittent or environment-specific behavior.
- Preserve diagnostic evidence needed for review.
