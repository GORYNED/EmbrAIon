---
name: implementation
description: Perform a bounded writable change while preserving ownership, compatibility, scope, and validation discipline.
---

# Implementation

## Procedure

1. Confirm owned paths, dependencies, and acceptance criteria.
2. Read the minimum required rules and project constraints. Prefer configured Project Contract Slots for the project engineering workflow, source authority, and any relevant compatibility or persistence contract instead of assuming framework-generic facts. Before adding, moving, or renaming a source file or type, apply the code-organization skill and relevant project coding standard, including custom knowledge bindings.
3. Make the smallest coherent change.
4. Preserve unrelated behavior and compatibility.
5. Run focused checks while editing. When ready for review, complete all tests and CI required by impact for the current candidate; explicitly mark checks legitimately not required under validation policy. Pending, missing, failing, or stale required evidence blocks readiness.
6. Self-review the full cumulative diff and related code after implementation and required checks. Fix findings, rerun affected required checks, and repeat self-review before independent Reviewer dispatch. After Reviewer findings, the author or another implementation owner fixes them and repeats this cycle.
7. Report changed files, integration dependencies, evidence, and residual risk.

## Guardrails

- Do not edit outside assigned ownership.
- Do not silently change shared contracts.
- Do not refactor unrelated code for convenience.
- Stop on unresolved compatibility, security, or ownership risk.
- Do not waive required checks or claim that author self-review is independent review.
