---
name: implementation
description: Perform a bounded writable change while preserving ownership, compatibility, scope, and validation discipline.
---

# Implementation

## Procedure

1. Confirm owned paths, dependencies, and acceptance criteria.
2. Read the minimum required rules and project constraints.
3. Make the smallest coherent change.
4. Preserve unrelated behavior and compatibility.
5. Run focused checks while editing.
6. Report changed files, integration dependencies, evidence, and residual risk.

## Guardrails

- Do not edit outside assigned ownership.
- Do not silently change shared contracts.
- Do not refactor unrelated code for convenience.
- Stop on unresolved compatibility, security, or ownership risk.
