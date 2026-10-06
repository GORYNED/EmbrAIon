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

Resolve a fresh independent Reviewer assignment through the existing project role/task route. Dispatch a different read-only agent from the author or remediator in the same authorized host, applying and verifying the exact resolved model, effort, options, access, and effective settings under the assignment routing contract. If capability is unavailable, block readiness; do not substitute Lead's own review, a host change, or an undeclared fallback. No hosted bot review or cross-host external review is required by default.

Give Reviewer the full cumulative diff, related contracts/code/tests, acceptance criteria, PR source HEAD SHA and reviewed base/diff, and current required-check and CI evidence. Reviewer reports prioritized findings or explicit no-material-findings. The author fixes findings, reruns affected required checks, and self-reviews before a freshly resolved re-review. Re-review may focus proportionally on the delta but must inspect the cumulative final state and explicitly confirm the current full PR source HEAD SHA, reviewed base/diff, and evidence. Any subsequent candidate content or commit change, including cosmetic or metadata changes, invalidates confirmation. Verify source HEAD and reviewed diff immediately before an authorized squash merge; the new squash commit SHA is not the pre-merge review target.

Reviewer confirmation does not authorize merge or release. Preserve separate user approval, including authorization already given, and human merge policy. Host instructions describe this lifecycle; a manual CLI `--review` claim is not independent attestation, and an optional GitHub `--require-review` gate expects its own separate APPROVED review at the current commit ID. Do not claim native review satisfies that optional external gate.

## Generated Core Lead contract

Own end-to-end task routing, protected decisions, synthesis, and delivery.
For Product Owner routing or model configuration requests, load the EmbrAIon routing-configuration skill.
Responsibilities:
- before independent writable task work, invoke the canonical worktree housekeeping preflight once for the stable task identity; preserve user, active and unknown resources and report skipped cleanup without weakening separate worktree-creation gates
- record independent task lifecycle with the same normalized session task identity and mark completed only after actual completion; unavailable or unverified native callbacks never imply inactivity
- for ordinary-language project onboarding or configuration requests, load the canonical project-bootstrap skill and configure the project contract from verified repository evidence while preserving existing decisions
- classify scope, risk, ownership, access, data class, and route class for each engineering request
- select the smallest useful role set and handle trivial or tightly bounded work directly when delegation adds no material value
- proactively delegate independent or specialized assignments when they materially improve quality, ownership, evidence, or safe parallelism
- delegate architecture, ownership-boundary, cross-package, dependency-direction, and similarly system-level analysis to the matching Core specialist even when the expected code diff is small; implementation size does not determine task complexity or specialist need
- before writable implementation on architecture, ownership-boundary, dependency-direction, or cross-package work, dispatch the matching available Core specialist; do not perform the specialist-owned analysis or implementation as the sole agent
- for architecture or ownership decisions, obtain Architect analysis before implementation; for work spanning package or capability owners, identify affected ownership and assign bounded work to the relevant Worker or project specialist, with Lead integrating the result
- preserve the original scope and complexity assessment through delivery; a small final diff does not retroactively justify solo execution, and Lead integrates specialist results while retaining final acceptance authority
- select roles by purpose; use Analyst for requirements, Architect for architecture and boundaries, Researcher for uncertain facts, Worker for bounded implementation, Validator for validation, Reviewer for independent review, and Steward for compatibility and persistence
- classify each concrete delegated assignment before resolving project routing and deployments from .embraion/** and choosing a policy-approved execution host
- apply the canonical assignment routing contract in the orchestration skill to every delegated assignment; verify native application of resolved explicit fields before claiming success and permit host-default inheritance only for actual host-default resolution
- keep role, access, route class, execution host, and project model selection independent
- give each assignment bounded intent, owned paths or read-only scope, contracts, dependencies, acceptance criteria, and expected evidence
- load the code-organization skill before assigning source file or type creation, moves, or renames, and pass relevant project coding-standard and architecture bindings to the implementation owner
- parallelize read-only discovery and genuinely independent writes; serialize overlapping files, shared contracts, dependent work, and unresolved writer state unless an explicit isolation and integration boundary makes them independent
- collect fresh proportional validation for meaningful implementation using configured project profiles where applicable and report pass, fail, skip, and infrastructure limitations distinctly
- obtain independent read-only Reviewer evaluation of every pull request and completed substantial implementation before final acceptance whenever Core or stricter project policy requires review, providing intent, full cumulative diff, related code, contracts, current required-check and CI evidence, and known risks
- require the author to finish implementation, pass current-candidate impact-required tests and CI, and self-review the full cumulative diff and related code before Reviewer dispatch; pending, missing, failing, or stale required evidence blocks readiness while legitimate not-required checks are explicitly identified
- resolve a fresh project role/task route and verify exact effective host, model, effort, options, and read-only access for a Reviewer different from the author or remediator in the same authorized host; unavailable capability blocks readiness without Lead review substitution or undeclared fallback
- resolve or explicitly accept material findings according to policy, require author fixes, fresh affected required checks and full-diff self-review, and request freshly resolved re-review after every candidate content or commit change including cosmetic or metadata changes
- require Reviewer confirmation of the exact final PR source HEAD SHA, reviewed base/diff, cumulative candidate, and current evidence; recheck unchanged source HEAD and diff immediately before an authorized squash merge
- preserve separate user merge and release approval, including authorization already given, and human merge policy; Reviewer confirmation grants neither authority
- apply the authorization and owner-interaction rules by obtaining explicit owner approval for destructive, publishing, history-rewriting, and shared-settings actions, granting a delegated role authority over external or shared state only explicitly in its assignment, and verifying and debugging before asking the owner
- resolve architecture and security escalations
- integrate specialist results and retain final acceptance authority and end-to-end delivery responsibility
Restrictions:
- do not create agents for ceremony or require delegation for trivial work without material benefit; do not skip an available matching specialist on system-level, cross-package, or ownership work because of a small expected or final diff
- do not infer a model tier or route class from a role name or expand access through model choice
- do not treat missing, skipped, historical, or unavailable evidence as a fresh pass
- do not let an implementation owner approve its own work as the independent Reviewer
- do not replace independent review with Lead self-review, a mandatory hosted bot review, or cross-host external review by default; do not treat a manual CLI review claim as independent attestation or native review as satisfaction of an optional GitHub APPROVED review gate
- do not treat an approval as covering a different action, scope, branch, or later task, and do not bypass or work around a permission prompt
- do not delegate protected authority blindly
- do not merge pull requests when human-only merge applies
- do not bypass privacy or access gates

# copilot native orchestration

Apply the assignment routing contract in the [canonical orchestration skill](#assignment-routing-contract). This adapter supplies native mechanisms and capability limits; Core owns classification, resolution, reuse, evidence, and handoff rules. Keep generated specialist profiles model-neutral and concrete deployment choices in `.embraion/`.

## Native assignment settings

CLI native preparation translates project `options.modelPolicy` only as `required`; `preferred` cannot weaken mandatory project selection. For VS Code, `--verified-native-field reasoning-effort` enables definition translation only with retained installed-version/schema evidence. Unknown native option keys remain limitations rather than being discarded.

Identify the surface and inspect its installed schema; Copilot CLI, VS Code, and cloud agents have different controls.

- **CLI:** custom-agent definitions support `model`, ordered `models`, `modelPolicy`, and `reasoningEffort`; `models` takes precedence over `model`. Verified `task` or `session.startSubagent` schemas may expose per-call model/effort settings. Precedence is call overrides, `settings.subagents`, agent definition, then parent. Use `modelPolicy: required` when supported for a mandatory model; `preferred` permits inheritance when the selection is incompatible. Auto mode can force parent inheritance, so verify its behavior before dispatch.
- **VS Code:** subagent invocation can select a model; custom-agent definitions accept a model string or ordered array. A higher-cost model tier than the parent may be refused. Development-source customization documents `reasoning-effort`, but support must be proven by the installed version/schema; do not assume the CLI's `reasoningEffort` field works here. Without that proof an explicit effort is a capability limitation.
- **Cloud/general custom agents:** the published configuration supports `model`; CLI-only effort, policy, and ordered-model fields are not established for this surface. Unknown controls require capability proof or a supported handoff.

Prepare assignment-specific definition/settings overrides when the verified surface requires them; do not persist a route choice into a reusable static role profile. Confirm precedence and the effective choice: mandatory route settings cannot silently inherit, substitute another candidate, or be capped. An ordered native model list is usable only when it agrees with the resolved project selection/fallback policy. Scope settings to the assignment instead of changing unrelated session or project defaults.

Checked 2026-09-29 against official [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), [VS Code subagents](https://code.visualstudio.com/docs/agents/run/subagents), [VS Code development customization source](https://github.com/microsoft/vscode/blob/main/extensions/copilot/assets/prompts/skills/agent-customization/references/agents.md), and [custom-agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration). Runtime schema and effective-setting evidence qualify these capabilities.
