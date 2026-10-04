# Worktree

EmbrAIon provides conservative worktree operations:

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree gc --json
embraion worktree gc --apply
embraion worktree prepare --task-id my-task --json
embraion worktree create ai/my-task --task-id my-task
embraion worktree create ai/my-task --branch-only --task-id my-task
embraion worktree create --detach --path /absolute/new-worktree --task-id my-task
embraion worktree restore --cleanup-id <cleanup-id>
embraion worktree salvage /path/to/worktree
```

The [Core workflow](../../core/workflows/worktree.md) owns the safety rules. GC is dry-run
by default and does not fetch, prune, write registry records, or create snapshots. Applied
cleanup reports each removed, preserved, or failed resource and retains recovery evidence
under the repository's Git common directory. `restore` restores local resources only and
refuses conflicting paths or branches. Recovery snapshots are never pruned automatically.

Enable automatic task housekeeping explicitly in `.embraion/project.yaml`:

```yaml
housekeeping:
  on-task-start: true
  local-branches: true
  remote-branches: true
  worktrees: true
  preserve-branches: [main, develop, 'release/*']
```

Automatic and remote deletion default to off. Agent ownership is mandatory and cannot be
disabled. Unknown branches, including old `claude/*` and `codex/*` resources, remain in the
preservation report. No prefix, author, or missing remote branch authorizes adoption.

`worktree create` captures creation provenance. To register a supported native creation,
call `prepare --task-id <id> --host <host> --branch <branch> --path <absolute-path>` before
creation, then `register --task-id <id> --host <host> --receipt-id <receipt> --path <path>`.
The receipt must match a genuinely new resource; registering an existing user branch is
refused. Opaque resources created before preparation remain unmanaged. Unknown native
archive/activity capability preserves host-managed worktrees.

Lifecycle evidence is recorded through the associated independent Lead session. A session
started with `--role lead --access workspace-write` runs configured preparation; read-only,
planning and Reviewer sessions do not. Continued calls with the same task ID do not repeat
cleanup. `session set --state completed` records completion for linked resources. Completed
task evidence alone does not prove merge or authorize deletion.

New registered resources require authoritative merged PR evidence, exact source SHA and
integration into the current target. GitHub metadata uses the existing authenticated `gh`
client and remote deletion uses an expected-SHA Git lease; credentials are not stored in
the inventory or report. Unknown API, protection, rules, or authorization state preserves
resources. Existing legacy markers retain only conservative direct-ancestry local cleanup.

Remote authority is bound to the original remote identity and its absence before local
creation. A pre-existing remote branch cannot be adopted by creating a matching local
branch. Remote-only resources without retained local provenance remain preserved.

Applied operations preserve exact commits and required local state before deletion and
repeat eligibility checks. Unknown ignored files preserve the candidate. `salvage` remains
a manual patch/untracked-file helper and is not a substitute for the cleanup recovery snapshot.

<sub>Last updated: 2026-10-04 02:07 UTC</sub>
