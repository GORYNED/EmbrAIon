# ADR 0001: Git is a prerequisite; Git mechanics live in one place

- Status: Accepted
- Date: 2026-10-07
- Owners: EmbrAIon maintainers
- Supersedes: None
- Superseded by: None

## Context

Issue #86 asked which Git-specific rules in the Core workflows are universal. The worktree workflow named the Git common directory, local and remote refs, remote branch deletion, squash-integration proof, and `worktree publish` creating a remote branch. The delivery workflow named the pull request source HEAD, base and diff confirmation, and a note about the squash-merge SHA. The question was whether Core should hide these behind a neutral version-control layer.

Observed facts:

- EmbrAIon lives on GitHub and ships with GitHub-based delivery.
- The CLI already calls `git` directly for worktrees, checks, decision records, and organization checks. It calls `gh` only for GitHub evidence in `embraion worktree gc`.
- Nothing in the repository supports a second version-control system.

The owner decided on 2026-10-07 that EmbrAIon may and does know Git, and that Git is effectively required.

## Decision

- Git is a stated prerequisite of EmbrAIon. GitHub is the supported hosting and delivery surface.
- The prerequisite is stated once, in the installation requirements. Other pages link to it.
- The universal primitives stay in the Core workflow wording: an isolated workspace, a reviewed change identity, and integration proof. Every safety rule keeps its meaning: fail-closed cleanup, exact-head integration proof, review invalidation after any candidate change, and source HEAD confirmation before a merge.
- The Git and GitHub mechanics are consolidated in one page, `core/workflows/git.md`. The worktree and delivery workflows link to it.
- No abstract version-control layer is built.

## Consequences

What moves: the Git common directory scope, the ref deletion conditions, the `worktree publish` lease mechanics, the merged pull request evidence list, and the squash-merge SHA note move from `worktree.md` and `delivery.md` into `git.md`. The workflows keep one short sentence for each and link to the matching section.

What does not move: the Git LFS sentence stays in `worktree.md`, because repository-specific requirements remain project or tool configuration. The `embraion worktree` commands, their options, reports, and exit codes do not change.

Costs: a reader of a workflow follows one link to see the Git detail. The Core catalog does not list `git.md`, because it is a reference reached from the two catalog workflows and not a separate capability.

## Alternatives considered

- An abstract version-control layer with Git as one adapter. Rejected. No second system exists or is planned, so the layer would be speculative. It would add vocabulary and indirection to rules whose safety depends on exact Git facts such as a SHA, a lease, and a common directory. It would also hide the Git requirement that users must meet.
- Leave the mechanics inside the two workflows. Rejected. It keeps the universal rules hard to read and spreads one fact over several places.
- Put the mechanics in an adapter folder. Rejected. The portable bundle ships Core workflows but not adapter files, so a Core link into an adapter would break there.

## Validation and evidence

- `python tools/source.py validate` and the unit and integration suites check schemas, docs parity, links, catalog paths, and projections.
- `git diff --stat` for the change shows no file under `tools/` or `schemas/`, so command behavior has no code change.
- Test results are recorded in the pull request for this change, not here.

## Rollout and compatibility

- Source and API compatibility: unchanged. No CLI option, command, report field, or exit code changes. The workflow files keep their paths, and the existing catalog entries keep their ids and paths.
- Persisted data compatibility: unchanged. No registry record, receipt, ledger, report, or schema changes. The only configuration change is binding the `decisions` knowledge slot of this repository to `docs/architecture/decisions`.
- Rollback: revert the change. No migration is needed.
- A later change of `embraion worktree` behavior needs its own compatibility review.
