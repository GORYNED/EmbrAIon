# Worktree

EmbrAIon provides conservative worktree operations:

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree gc --json
embraion worktree gc --apply
embraion worktree prepare --task-id my-task --json
embraion worktree create ai/my-task --task-id my-task --independent-task
embraion worktree publish --task-id my-task --branch ai/my-task
# After further task commits, publish again through the same verified workflow.
embraion worktree publish --task-id my-task --branch ai/my-task
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

`gc --json` includes `provenance` for each resource: registered host, task IDs and creation
source when the current resource identity matches its registry record. An unregistered,
reused or unverified resource reports `status: unknown`, with no guessed host. This metadata
helps identify the creating workflow; completion, integration and remote ownership remain
separate deletion gates. Host-native registration does not prove archive capability.

`worktree create` captures creation provenance. Creation invokes automatic cleanup only
with explicit `--independent-task`; `--subtask` or omitted scope preserves other resources.
To register a supported native creation,
call `prepare --task-id <id> --host <host> --branch <branch> --path <absolute-path>` before
creation, then `register --task-id <id> --host <host> --receipt-id <receipt> --path <path>`.
The receipt must match a genuinely new resource; registering an existing user branch is
refused. Opaque resources created before preparation remain unmanaged. Unknown native
archive/activity capability preserves host-managed worktrees.

Lifecycle evidence is recorded through the associated independent Lead session. A session
started with `--role lead --access workspace-write --independent-task` runs configured
preparation; omitted scope, `--subtask`, read-only, planning and Reviewer sessions do not.
Continued calls with the same task ID do not repeat
cleanup. `session set --state completed` records completion for linked resources. Completed
task evidence alone does not prove merge or authorize deletion.

New registered resources require authoritative merged PR evidence, exact source SHA and
integration into the current target. GitHub metadata uses the existing authenticated `gh`
client and remote deletion uses an expected-SHA Git lease; credentials are not stored in
the inventory or report. Unknown API, protection, rules, or authorization state preserves
resources. Existing legacy markers retain conservative direct-ancestry worktree cleanup;
the marker alone grants no authority to delete local or remote branches.

Remote authority requires a verified create-only `worktree publish` operation bound to
the registered local branch and original remote. An existing remote, including one created
by an external push after local creation, cannot be adopted. Remote-only resources without
retained local provenance remain preserved. Subsequent task commits use the same `publish`
command: it requires the previous recorded remote SHA, permits only a fast-forward update,
and appends a verified receipt while retaining the initial creation evidence. An unchanged
tip, an externally advanced remote or a race never creates update evidence. The receipt
chain binds the last published tip; external pushes preserve the resource. Embedded URL
credentials, URL parameters, rewrites, multiple URLs, and different fetch/push endpoints
are refused for remote mutation. Git SHA leases detect changed tips, but cannot
distinguish deletion and recreation of the same name at the identical SHA; ambiguous PR
reuse is preserved, and recovery snapshots retain the exact commits.

After verified remote deletion, cleanup removes only the matching direct
`refs/remotes/origin/<branch>` ref. Changed or symbolic tracking refs are preserved;
other cached refs are never pruned. Local ownership checks reject symbolic refs and
filesystem aliases before deletion, and compare-and-delete never dereferences them.

## Git LFS hydration

A new worktree of a repository that uses Git LFS holds pointer text files until the content is
fetched. Hydration is opt-in and off by default. Enable it in `.embraion/project.yaml`:

```yaml
worktree:
  lfs: hydrate
```

The only values are `none` (default) and `hydrate`. Any other value, or an unknown key under
`worktree`, is an error and stops the command before anything is created.

With `hydrate`, `worktree create` (named branch or `--detach`) and `worktree register` check
the new worktree after it exists. `prepare` does not hydrate because it runs before a
checkout exists. The check works in this order:

1. No `filter=lfs` in a `.gitattributes` file at HEAD, or no committed LFS pointer under such
   an attribute: state `not-applicable`. `git lfs` is not needed.
2. Every LFS file in the working tree already matches its pointer size and SHA-256 (for
   example because Git smudged it): state `hydrated`, reason `already-present`.
3. Otherwise `git lfs` must be available. If it is missing, hydration fails with an
   actionable message. This is the only case where a missing `git lfs` is an error.
4. `git lfs fetch <remote> <HEAD-sha>` fetches the content of the exact worktree HEAD. The
   remote is the branch's tracking remote, else `origin`. Nothing is downloaded from any other
   location, and the command never prompts for credentials.
5. `git lfs checkout` writes the content. It receives the LFS filter settings for that one
   command only, so a machine without `git lfs install` works, and no Git configuration is
   changed.
6. Every LFS file at HEAD is verified by size and SHA-256 against its pointer. Files
   excluded by sparse checkout are not counted.

`create` prints `LFS hydrated: <verified> of <files> files verified`. `register` adds an
`lfs` object to its JSON output only when the setting is on:

```json
{"lfs": {"state": "hydrated", "files": 3, "verified": 3, "missing": 0, "reason": "verified"}}
```

`state` is `hydrated`, `failed`, `not-applicable`, or `skipped` (a branch-only resource with
no checkout). A failure exits with code 1 and keeps the worktree, so you can fix the cause
and run `git lfs pull` there. Failure reasons never contain credentials: URL user info and
query parameters are removed from Git LFS error text. With the setting off or absent, these
commands behave exactly as before and print no LFS output.

Applied operations preserve exact commits and required local state before deletion and
repeat eligibility checks. Unknown ignored files preserve the candidate. `salvage` remains
a manual patch/untracked-file helper and is not a substitute for the cleanup recovery snapshot.

<sub>Last updated: 2026-10-07 11:05 UTC</sub>
