# Independent Review

Every pull request and every substantial code or configuration implementation requires independent review. Trivial non-PR work remains proportional unless a stricter project rule applies.

The author first completes implementation, obtains passing required checks for the current candidate (including applicable CI), and self-reviews the full cumulative diff and related code. A check legitimately outside the change's impact may be explicitly marked not required under validation policy; a required check cannot be waived. Pending, missing, failing, or stale required evidence blocks review readiness.

The independent Reviewer is a different agent from the author or remediator, has read-only access in the same authorized execution host, and is routed through the existing project role and task mapping. Unavailable required reviewer capability blocks readiness; Lead cannot substitute its own review. The Reviewer examines the cumulative candidate and confirms the exact final PR source HEAD SHA, reviewed base and diff, and current evidence after all remediation. Any later candidate content or commit change invalidates that confirmation, including cosmetic or metadata changes.

Reviewer confirmation does not authorize merge or release. Preserve the project's user approval and human merge rules. Copilot Review and a cross-host external reviewer are not default requirements.
