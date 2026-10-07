# Worktree

Independent writable tasks should use isolated task worktrees when the host repository supports them. Git is a stated prerequisite of EmbrAIon; the Git and GitHub mechanics behind this workflow are in [Git and GitHub mechanics](git.md).

Cleanup is fail-closed: preserve dirty, locked, active, divergent, ambiguous, or unproven worktrees. Never use a stable main checkout as an unsafe fallback runtime.

## Task housekeeping

Before the first writable action of a new independent Lead task, invoke the project's
`embraion worktree prepare --task-id <stable-task-id>`. Cleanup is restricted to the
current repository, runs once per task, and is opt-in through the project's housekeeping
configuration. Continuing a chat, starting a subtask, review, planning, and read-only
work do not authorize cleanup. Missing cleanup capability preserves resources and is
reported; it does not waive separate requirements for a current base or safe worktree creation.

New automatic cleanup requires proven agent creation, completed task evidence, and
integration of the exact resource HEAD into the current target branch. Names, prefixes,
authors, missing remote branches, and elapsed time are not ownership or inactivity proof.
Resources created by the host require a receipt captured before creation and verified
registration afterwards; an existing user branch cannot be adopted implicitly. Shared
registry records retain resource identity and lifecycle evidence across worktrees.

Remote ownership requires positive creation evidence from a supported adapter. The
portable `worktree publish` explicitly creates a remote ref and later updates it only under
exact-state leases, as described in [publication](git.md#publication). A local receipt or
an external push never grants remote deletion authority; existing remote refs are preserved.

Keep the stable task identity in normalized session state: start the independent writable
Lead session with `session start --session-id <session-id> --task <task-id> --role lead
--host <host> --access workspace-write --independent-task`. Scope must be explicit: a
session without `--independent-task`, or with `--subtask`, never starts automatic cleanup.
Record `session set --state completed` only when
the task is actually finished. Review, blocked and incomplete work remains nonterminal;
cancelled or failed tasks are not new automatic cleanup candidates. Native host callbacks
are lifecycle authority only when their provenance and delivery have been verified.

For a merged change, verify the evidence listed in
[merged pull request evidence](git.md#merged-pull-request-evidence). Preserve divergent,
reused, protected, default, explicitly preserved, and unknown resources. Integration proof
is evidence tied to the exact resource HEAD, never similarity of content. Legacy markers retain
their conservative local direct-ancestry worktree behavior. A legacy marker alone never
grants local or remote branch deletion rights. Legacy compatibility cleanup releases
worktrees and preserves their branch refs.

Never remove the primary or current worktree. Check all linked tasks and worktrees,
Git operations, locks, staged, unstaged and untracked files. Preserve unknown ignored
files and unsupported filesystem state. Host-managed resources require a supported
archive operation; lack of it is a preservation reason, not a raw filesystem fallback.

Before destructive operations, retain verified commit and local-state recovery evidence
outside the removable checkout. Serialize mutation per repository (the Git common directory; see [repository scope](git.md#repository-scope)) and repeat
eligibility checks before each operation.
Delete a remote ref only when its expected SHA still matches, and a local ref only after associated
worktrees are released; [refs](git.md#refs) gives the Git conditions and the one squash-merge exception. Retain operation journals
and backups on partial failure; never overwrite conflicting paths or refs during restore.

Dry-run must not fetch, prune, write refs, create registry state, locks, or backups.
Report candidates, removals, preservation reasons, failures, and recovery identifiers.
Automatic deletion and remote deletion require explicit project enablement and never
expand execution permissions or integration access. Unknown integration state fails closed.

Repository-specific requirements such as Git LFS hydration remain project or tool configuration, not universal Core policy.
