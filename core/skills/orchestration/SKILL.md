---
name: orchestration
description: Handle ordinary-language engineering requests as Lead, choosing proportional specialist delegation, validation, review, and integration.
---

# Orchestration

Apply the canonical Lead role (`core/agents/lead.yaml`) to the user's engineering request. Load only relevant catalog capabilities and configured project contracts. Use the planning, implementation, validation, review, and verification skills when the assignment warrants their procedures.

Before the first writable action of an independent task, load the worktree workflow and
invoke `embraion worktree prepare --task-id <stable-task-id>`. Respect project opt-in,
current-repository boundaries, and preservation reports. Continued chats, subtasks,
review and plan/read-only work do not trigger destructive housekeeping.

For an assignment that adds, moves, or renames source files or types, load the code-organization skill before placement or dispatch and include applicable project architecture, source-authority, and coding-standard bindings in the implementation scope. For an explicitly requested structural audit or migration, scope the existing code and identity/dependency risks before assigning moves.

The host projection appends the canonical Lead responsibilities and restrictions to this skill. Host instructions guide behavior; executable validation, review, access, and privacy gates remain separate. Concrete routing choices remain project-owned under `.embraion/**`.

For ordinary-language requests to configure EmbrAIon for a project, load the canonical `project-bootstrap` skill. It owns repository discovery, conservative project-contract configuration and post-configuration verification; the user need not enumerate YAML files or specialists. Explicit model tuning additionally loads `routing-configuration`.

## Assignment routing contract

Before dispatch or a dependent action, identify the current requested outcome, target, and authorized action. Reconcile later corrections or cancellations with earlier approvals; unaffected authorization persists. A dependency update, an independently requested product change, and publication are separate actions under canonical delivery controls. Plans and checkpoints describe state and do not grant authority. Clarify only material ambiguity that blocks the next action; do not infer an obligation to rewrite documentation from a dependency update.

1. Classify every new delegated assignment, including a new assignment sent to an existing specialist. Resolve its project route before dispatch using the assignment's role, route/task class, data class, and access. Use the existing project resolver; role names and Lead's model never supply routing choices.
2. Inspect the successful resolution, or the selected candidate of a task-class plan. Preserve its host, resolution, provenance, model, effort, options, and declared fallbacks. Missing or unknown resolution, resolver failure, and unavailable capability evidence are not host-default.
3. Apply each explicit project field independently through the selected host's verified native mechanism. A model-only or effort-only override remains explicit. Host-default inheritance is permitted only when resolution is actually `host-default`; omit project selection fields in that case. An absent model alone never establishes host-default.
4. Check the active host surface, installed tool schema, selector/effort support, options, and effective configuration precedence before invoking it. Native arguments, assignment-specific definitions, and fresh native session handoffs are different mechanisms. Adapter metadata describes representations, not live model availability. Keep concrete selections derived from `.embraion/**`; generated definitions are projections, never another routing authority.
5. If a mandatory selector, effort, or option cannot be applied, record a capability limitation and block that dispatch. Do not simulate success, silently inherit Lead's settings, accept a substituted selection, or invent a fallback. A supported declared fallback or explicit handoff follows the canonical fallback policy and requires fresh privacy/access checks across execution boundaries. Unknown or unresolved state fails closed.
6. Reuse a specialist only after fresh resolution and verification that its effective role, model, effort, and required options satisfy the new assignment. Unknown settings, conflicting native precedence, or settings that cannot be changed require a fresh routed assignment. Host-default reuse must follow current host defaults/inheritance rather than retain a previous explicit project choice.
7. Preserve bounded intent, ownership, permissions, dependencies, and acceptance criteria through native translation. Record the resolution and actual dispatch arguments/definition plus effective settings or capability limitations. A prepared plan or successful resolver command is not execution evidence. Verify the applied selection before claiming routing succeeded.

Load the current host adapter's native delegation guidance to translate this contract. Portable packages carry this contract as interchange content; they provide no runtime host or delegation mechanism.

## Review lifecycle and authority

Apply this canonical review lifecycle to every pull request and every substantial implementation. Trivial non-PR work stays proportional. Before Reviewer dispatch, the author must finish the candidate, obtain fresh passing impact-required tests and CI, and self-review the full cumulative diff and related code. Explicitly identify checks legitimately not required by impact; pending, missing, failing, stale, or unavailable required evidence blocks readiness. Never waive a required check.

Resolve a fresh independent Reviewer assignment through the existing project role/task route. Dispatch a different read-only agent from the author or remediator in the same authorized host, applying and verifying the exact resolved model, effort, options, access, and effective settings under the assignment routing contract. If capability is unavailable, block readiness; do not substitute Lead's own review, a host change, or an undeclared fallback. No Copilot Review or cross-host external review is required by default.

Give Reviewer the full cumulative diff, related contracts/code/tests, acceptance criteria, PR source HEAD SHA and reviewed base/diff, and current required-check and CI evidence. Reviewer reports prioritized findings or explicit no-material-findings. The author fixes findings, reruns affected required checks, and self-reviews before a freshly resolved re-review. Re-review may focus proportionally on the delta but must inspect the cumulative final state and explicitly confirm the current full PR source HEAD SHA, reviewed base/diff, and evidence. Any subsequent candidate content or commit change, including cosmetic or metadata changes, invalidates confirmation. Verify source HEAD and reviewed diff immediately before an authorized squash merge; the new squash commit SHA is not the pre-merge review target.

Reviewer confirmation does not authorize merge or release. Preserve separate user approval, including authorization already given, and human merge policy. Host instructions describe this lifecycle; a manual CLI `--review` claim is not independent attestation, and an optional GitHub `--require-review` gate expects its own separate APPROVED review at the current commit ID. Do not claim native review satisfies that optional external gate.
