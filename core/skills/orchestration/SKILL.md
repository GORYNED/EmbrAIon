---
name: orchestration
description: Handle ordinary-language engineering requests as Lead, choosing proportional specialist delegation, validation, review, and integration.
---

# Orchestration

Apply the canonical Lead role (`core/agents/lead.yaml`) to the user's engineering request. Load only relevant catalog capabilities and configured project contracts. Use the planning, implementation, validation, review, and verification skills when the assignment warrants their procedures.

The host projection appends the canonical Lead responsibilities and restrictions to this skill. Host instructions guide behavior; executable validation, review, access, and privacy gates remain separate. Concrete routing choices remain project-owned under `.embraion/**`.

For ordinary-language requests to configure EmbrAIon for a project, load the canonical `project-bootstrap` skill. It owns repository discovery, conservative project-contract configuration and post-configuration verification; the user need not enumerate YAML files or specialists. Explicit model tuning additionally loads `routing-configuration`.

## Assignment routing contract

1. Classify every new delegated assignment, including a new assignment sent to an existing specialist. Resolve its project route before dispatch using the assignment's role, route/task class, data class, and access. Use the existing project resolver; role names and Lead's model never supply routing choices.
2. Inspect the successful resolution, or the selected candidate of a task-class plan. Preserve its host, resolution, provenance, model, effort, options, and declared fallbacks. Missing or unknown resolution, resolver failure, and unavailable capability evidence are not host-default.
3. Apply each explicit project field independently through the selected host's verified native mechanism. A model-only or effort-only override remains explicit. Host-default inheritance is permitted only when resolution is actually `host-default`; omit project selection fields in that case. An absent model alone never establishes host-default.
4. Check the active host surface, installed tool schema, selector/effort support, options, and effective configuration precedence before invoking it. Native arguments, assignment-specific definitions, and fresh native session handoffs are different mechanisms. Adapter metadata describes representations, not live model availability. Keep concrete selections derived from `.embraion/**`; generated definitions are projections, never another routing authority.
5. If a mandatory selector, effort, or option cannot be applied, record a capability limitation and block that dispatch. Do not simulate success, silently inherit Lead's settings, accept a substituted selection, or invent a fallback. A supported declared fallback or explicit handoff follows the canonical fallback policy and requires fresh privacy/access checks across execution boundaries. Unknown or unresolved state fails closed.
6. Reuse a specialist only after fresh resolution and verification that its effective role, model, effort, and required options satisfy the new assignment. Unknown settings, conflicting native precedence, or settings that cannot be changed require a fresh routed assignment. Host-default reuse must follow current host defaults/inheritance rather than retain a previous explicit project choice.
7. Preserve bounded intent, ownership, permissions, dependencies, and acceptance criteria through native translation. Record the resolution and actual dispatch arguments/definition plus effective settings or capability limitations. A prepared plan or successful resolver command is not execution evidence. Verify the applied selection before claiming routing succeeded.

Load the current host adapter's native delegation guidance to translate this contract. Portable packages carry this contract as interchange content; they provide no runtime host or delegation mechanism.
