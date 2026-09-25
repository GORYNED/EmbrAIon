---
name: review
description: Independently review a completed candidate for correctness, regressions, compatibility, lifecycle, tests, security, and privacy.
---

# Review

## Procedure

1. Read intent, canonical contracts, candidate diff, fresh validation evidence, and known risks. Resolve configured Project Contract Slots that match the review surface, especially architecture, source authority, compatibility, persistence, and specification.
2. Review correctness before style.
3. Check compatibility, persistence, lifecycle, concurrency, dependency boundaries, tests, platform assumptions, security, and privacy as applicable.
4. Rank findings by material impact.
5. For each material finding, provide evidence and a reproduction or verification suggestion.
6. State explicitly when no material findings remain.

## Guardrails

- Remain independent from implementation ownership.
- Do not modify files while acting as Reviewer.
- Do not inflate cosmetic preference into a correctness finding.
- Missing required evidence is not a pass.
