# Engineering

Apply the canonical [Lead contract](../agents/lead.yaml) proportionally to each engineering request. Trivial or tightly bounded non-PR work stays with Lead when delegation adds no material value. Every pull request follows the [review workflow](review.md), regardless of implementation size.

For substantial work:

Before writable independent task work, apply the [worktree housekeeping workflow](worktree.md).
This preflight also applies to bounded independent writable tasks; it is not triggered by read-only work.

1. Lead performs planning, ownership, privacy, compatibility, and impact routing, resolving the relevant configured Project Contract Slots before assigning project-specific work.
2. Use Spec Kit as an optional recommended companion when specification-driven structure is useful.
3. Lead selects the smallest useful role set, classifies each concrete assignment, and resolves project routing, deployments, and policy-approved execution hosts. Sequence dependent work and parallelize only independent assignments under the [safe parallelism rule](../rules/parallelism.md).
4. Worker or project specialist implements bounded owned work.
5. Author completes the candidate, obtains fresh required focused and impact-appropriate tests and CI evidence using configured project validation profiles where applicable, and self-reviews the full cumulative diff plus related code. Distinguish passes, failures, legitimate not-required checks, and infrastructure limitations. Pending or missing required evidence blocks review readiness.
6. Only after step 5 is clear, an independent read-only Reviewer evaluates the completed implementation and its evidence before Lead final acceptance under the [review rule](../rules/review.md) and [review workflow](review.md).
7. Author remediates material findings under policy, reruns affected required checks, self-reviews again, and obtains fresh independent confirmation of the final candidate. Every candidate change invalidates prior confirmation.
8. Lead integrates results, owns final acceptance, and hands off for delivery. Reviewer confirmation does not grant merge or release authority.
