# Delivery

Git is a stated prerequisite of EmbrAIon and GitHub is the supported delivery surface; the Git and GitHub mechanics behind this workflow are in [Git and GitHub mechanics](git.md).

1. Confirm the intended full cumulative diff, then create or update the pull request so its source HEAD, reviewed base/diff, and required CI can be identified. Keep it unready while required checks or review are pending.
2. Complete the [review workflow](review.md): fresh passing required tests and CI for that exact candidate, author self-review, and independent Reviewer confirmation of the final PR source HEAD SHA, base/diff, and evidence. Explicitly record checks legitimately not required by impact; pending, missing, failing, or stale required checks block readiness. Any candidate content or commit change requires renewed review.
3. Publish Changed, Architecture, Validation, Risks, and Workers evidence when the consuming project uses that completion contract. Recheck the PR source HEAD and diff after any update; a changed candidate returns to the review workflow before readiness.
4. Immediately before an authorized squash merge, confirm the PR source HEAD and reviewed diff are unchanged. How the squash merge changes commit identity is in [reviewed change identity](git.md#reviewed-change-identity); source HEAD confirmation applies before the merge operation.
5. Preserve separate user merge and release approval, including authorization already given. Stop before merge when the project's merge mode is `human-only`; under `owner-permission`, merge only as the [human merge rule](../rules/human-merge.md) allows, and never enable auto-merge.
