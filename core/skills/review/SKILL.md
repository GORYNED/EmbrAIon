---
name: review
description: Independently review a self-reviewed candidate with current required evidence and confirm the final PR source HEAD.
---

# Review

## Procedure

1. Confirm the author finished implementation, all impact-required tests and CI have fresh passing results for this candidate, and the author self-reviewed the full cumulative diff plus related code. Record legitimate not-required checks separately. Pending, missing, failing, stale, or unavailable required evidence blocks review readiness.
2. Read intent, acceptance criteria, canonical contracts, full cumulative diff, related code and tests, current evidence, and known risks. Resolve configured Project Contract Slots that match the review surface, especially architecture, source authority, compatibility, persistence, and specification. For a PR identify its source HEAD SHA and reviewed base/diff.
3. Review correctness before style. For each added, moved, or renamed source file or type, check folder and namespace ownership, project rules, and dependency direction using the code-organization skill and any configured organization check. For scoped migrations, check preserved identifiers, metadata, references, and contracts with compatibility-migration when its trigger applies. Check dependency, performance, lifecycle, resources, concurrency, tests, platform assumptions, security, and privacy as applicable; use independently installed domain skills for their relevant triggers. For a UI behavior claim, distinguish observed live interaction from static code or screenshot inspection.
4. Rank material findings by impact. Give evidence and a reproduction or verification suggestion for each. State explicitly when no material findings remain.
5. For every clear final candidate, including one with no findings, explicitly confirm the exact current full PR source HEAD SHA, reviewed base/diff, and required evidence, or state what blocks confirmation. After remediation or resumption, inspect the delta and cumulative final state with fresh applicable evidence. Any later candidate content or commit change, including cosmetic or metadata changes, invalidates confirmation.

## Guardrails

- Remain a different agent from the author or remediator, read-only in the same authorized host, with a freshly resolved project role/task route and exact effective settings.
- Do not modify files, implement fixes, or grant merge or release authority while acting as Reviewer.
- Do not inflate cosmetic preference into a correctness finding.
- Missing required evidence is not a pass; required checks cannot be waived.
