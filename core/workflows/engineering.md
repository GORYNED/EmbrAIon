# Engineering

Apply the canonical [Lead contract](../agents/lead.yaml) proportionally to each engineering request. Trivial or tightly bounded work stays with Lead when delegation adds no material value.

For substantial work:

1. Lead performs planning, ownership, privacy, compatibility, and impact routing, resolving the relevant configured Project Contract Slots before assigning project-specific work.
2. Use Spec Kit as an optional recommended companion when specification-driven structure is useful.
3. Lead selects the smallest useful role set, classifies each concrete assignment, and resolves project routing, deployments, and policy-approved execution hosts. Sequence dependent work and parallelize only independent assignments under the [safe parallelism rule](../rules/parallelism.md).
4. Worker or project specialist implements bounded owned work.
5. Validator collects fresh focused and impact-appropriate evidence using configured project validation profiles where applicable, distinguishing passes, failures, skips, and infrastructure limitations.
6. An independent read-only Reviewer evaluates completed implementation and its evidence before Lead final acceptance under the [review rule](../rules/review.md) and [review workflow](review.md).
7. Material findings are remediated or explicitly accepted according to policy; fixes receive fresh proportional validation and re-review when they invalidate prior evidence.
8. Lead integrates results, owns final acceptance, and hands off for delivery.
