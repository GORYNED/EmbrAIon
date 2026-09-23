---
name: validation
description: Plan and execute proportional validation while distinguishing fresh evidence, expected skips, and infrastructure limitations.
---

# Validation

## Procedure

1. Classify the change impact.
2. Select the smallest checks that can falsify the intended behavior.
3. Run focused checks during implementation.
4. Expand validation only when impact justifies it.
5. Record exact fresh results, expected skips, and infrastructure limits.
6. Preserve failing evidence until the cause is understood.

## Guardrails

- Never weaken a validator to obtain a pass.
- Never convert unavailable evidence into success.
- Do not generalize environment-specific evidence to untested environments.
- Keep validation proportional to risk and blast radius.
