---
name: validation
description: Plan and execute proportional validation while distinguishing fresh evidence, expected skips, and infrastructure limitations.
---

# Validation

## Procedure

1. Classify the change impact.
2. Select the smallest checks that can falsify the intended behavior and state which acceptance criterion each proves. Include the relevant consumer or entry-point path when an isolated helper or stub cannot establish the requested behavior. Use test-design when risk requires a separate test strategy; use an independently installed domain skill when its trigger matches the affected platform, resource, or runtime risk.
3. Prefer a configured project profile from `.embraion/validation.yaml` when it matches the needed evidence.
4. Run it through `embraion validation run <profile>`; use `--run-id` when execution evidence should receive the result automatically.
5. Expand validation only when impact justifies it.
6. Record exact fresh results, expected skips, and infrastructure limits. For UI claims, label live user interaction separately from static inspection, screenshots, and build results. On resumption, check candidate and environment identity before reusing earlier results.
7. Preserve failing evidence until the cause is understood.

## Guardrails

- Never weaken a validator to obtain a pass.
- Never convert unavailable evidence into success.
- Do not generalize environment-specific evidence to untested environments.
- Keep validation proportional to risk and blast radius.

## Activation contract

Use a distinct validation plan for material behavior, integration, compatibility, or regression risk. A trivial reversible edit needs only applicable required checks. Stop when mandatory criteria have fresh evidence or an explicitly unresolved limitation; return observed results and coverage boundaries. Source inspection, successful test execution, and runtime evidence prove different properties and must not be substituted for one another.
