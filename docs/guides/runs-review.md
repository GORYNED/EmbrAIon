# Runs & Review

Structured run evidence is useful when a project needs more than conversational history — for example, substantial changes, auditability, validation attachment, or enforced review.

It is optional for ordinary lightweight tasks.

## What a run records

A structured run can record:

- task and role;
- selected host and route class;
- data class and access mode;
- owned paths;
- selected context identity;
- changed paths;
- attached validation evidence;
- review result;
- outcome and residual risk.

Knowledge content is not copied into the run record. Context and validation are attached through their persisted identities/evidence rather than being re-entered as unverified claims.

## Start a run

```bash
embraion run start \
  --run-id task-001 \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class substantial \
  --data PRIVATE \
  --access write \
  --owned-path "src/**" \
  --substantial
```

The run records the task contract: role, host, routing class, data class, access, owned paths, and substantial-work intent.

## Attach real validation

```bash
embraion validation run affected --run-id task-001
```

This attaches validation evidence by ID instead of asking a user or AI to re-enter a claim manually.

## Record review and completion

After independent review:

```bash
embraion run complete task-001 \
  --changed-path src/example.py \
  --validation affected=passed \
  --review passed \
  --outcome completed
```

Writable completion checks changed paths against owned scope and project-protected path policy. Substantial writable work also has to satisfy the applicable review contract.

## What review should mean

A meaningful review should be independent from the implementation step and should inspect evidence relevant to the risk of the change.

For substantial work, review commonly includes:

- behavior and regressions;
- architecture or compatibility boundaries;
- protected/generated/external source handling;
- validation coverage;
- security/privacy implications;
- residual risk.

## Relationship to GitHub enforcement

When `.embraion/policy.yaml` requires review, `embraion enforcement check` can use structured run evidence through `--run-id`, or an explicitly installed GitHub Actions surface can delegate the review requirement to current PR approvals.

See [Enforcement](enforcement.md).
