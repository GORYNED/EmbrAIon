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

For an assignment that may make an architecture-level decision (dependency direction, ownership, a persisted format or stable identifier, a platform or build strategy, a foundational dependency, or a new or removed package), load the architecture-decision skill during planning so the record, or a stated waiver, is part of the implementation scope and the project's configured decisions check is among the required checks.

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

# claude-code native orchestration

Apply the assignment routing contract in the [canonical orchestration skill](#assignment-routing-contract). This adapter supplies native mechanisms and capability limits; Core owns classification, resolution, reuse, evidence, and handoff rules. Keep generated specialist profiles model-neutral and concrete deployment choices in `.embraion/`.

## Native assignment settings

Before independent writable work, apply the [Core worktree workflow](https://github.com/GORYNED/EmbrAIon/blob/v0.33.0/core/workflows/worktree.md)
with `embraion worktree prepare --task-id <stable-task-id> --host claude-code`.
Native startup interception requires verified capability; otherwise Lead invokes the preflight.
Review, subtasks and plan/read-only work do not trigger deletion. Observer hooks remain observers.

Capture `--branch <branch> --path <absolute-path>` before known native creation and use
the returned receipt with `worktree register --task-id <id> --host claude-code
--receipt-id <receipt> --path <path>` afterwards. A `.claude/worktrees` path alone does not
prove ownership or inactivity. Preserve opaque pre-created or native-managed resources when
creation evidence, host activity, or supported archive capability is unavailable.

Inspect the installed `Agent` tool schema (older installations may expose `Task`). Its per-call `model` field may accept only a fixed alias enum; do not pass a full model ID merely because definitions accept it, and do not guess an equivalent alias. Current subagent definitions in `.claude/agents/*.md` or the `--agents` JSON configuration support `model` and `effort`; definition model selectors may be host aliases, full IDs, or `inherit`. A mandatory explicit selection must not become inheritance through an alias or fork behavior.

A per-call `effort` argument on `Agent` is not established by the published contract. Apply explicit model and/or effort through a complete assignment-specific native definition containing the role description, prompt, permitted tools, and selected settings. Load and select that definition, or use a supported session/handoff mechanism with verified effective settings. Do not invent an `Agent` effort field or modify a reusable role definition to carry one assignment's route. A prepared definition still requires native loading and invocation evidence.

`dispatch --native-surface claude-agent` returns a `scoped-definition` and the required `subagent_type`, with `handoff-required` and `executed: false` for explicit settings. To use a supported `--agents` loader, form a JSON object keyed by the definition's `name`, whose value contains `description`, `prompt`, `tools`, and any selected `model`/`effort`; do not pass the whole plan as the loader configuration. Supply the bounded task as the separate invocation prompt. A project routing role such as `independent-review` is not automatically a native profile: use `--native-agent reviewer` while retaining the original `--role independent-review`. This binding never changes route eligibility or widens the specialist's tools.

Prefer the opt-in startup projection when `.embraion/claude-native.yaml` configures this assignment. Its `bindings` map routing roles to native specialist IDs; its explicit `assignments` list declares route class, data class and access without duplicating model or effort choices. Install `scoped-agents` before starting a new Thread. These separate hash-named profiles carry the resolver's settings while reusable role profiles stay model-neutral. Dispatch also discovers the configured binding. Its `projection.state: current` proves exact file content, not loading into the active Thread. Confirm that the returned `arguments.subagent_type` is in this Thread's loaded agent registry, then invoke that exact type without a per-call model override. A missing, stale or unloaded profile requires projection refresh and a new Thread or a supported native loader. Do not launch an unconfigured reviewer, restart a CLI requiring separate authentication, or perform the independent review yourself to make the check appear complete.

`embraion claude-native install-hooks`, or the equivalent `hooks` projection component, explicitly preserves and merges native hook entries into `.claude/settings.json` and records them in the projection ledger. The guard refuses stale scoped Agent types, base profiles for configured explicit assignments, and invocation model overrides. A project's opt-in `read-policy` can further confine scoped read/search calls to the current project and refuse protected source patterns; it does not sandbox the parent, arbitrary profiles, or shell access. Tool-list restrictions and route data eligibility alone are not filesystem privacy enforcement. Preserve project source classification and context boundaries independently.

`embraion claude-native status` separates canonical installation from recorded callback metadata. Claude Code 2.1.277 early-access hook declarations permit optional tool-context `effort.level`, but that does not prove delivery by the installed desktop or cloud build. If input supplies it, `reported-effort` compares it with the definition as advisory data. `evidence-origin` remains `unverified-command-input`: the public observer accepts arbitrary JSON, so its records do not prove host origin, effective effort, or assignment completion. `execution`, effective `effort` and `model` remain `unverified`; `callbacks: recorded` means only accepted metadata; real native invocation and trusted host-specific evidence are required. Session init null effort and an agent's own statements are not evidence. A command-line price estimate is not confirmed subscription spending. Hooks store only bounded identity/effort metadata, never prompt, result, transcript or private tool inputs.

The generated `.claude/rules/embraion.md` activates the orchestration skill and scoped project instructions, and `.claude/rules/embraion-core.md` carries every Core rule. Confirm it was read in each local, cloud, or resumed Thread. Project overview messages, installed files, and another Thread's route are not evidence of loading or applied settings. `harness audit` checks installation only.

Normal model precedence is invocation override, agent definition, `CLAUDE_CODE_SUBAGENT_MODEL`, then parent; force-mode environment configuration can supersede normal overrides. Model allowlists can substitute choices, and fork modes can inherit the parent. Verify all these controls without recording secret environment values. Effort is model-specific, and `CLAUDE_CODE_EFFORT_LEVEL` or host caps can override the requested effort. A mandatory route cannot silently accept inheritance, substitution, or capping; report a capability limitation and follow Core's supported handoff rules when the effective selection cannot be proven.

Checked 2026-09-29 against official [subagent documentation](https://code.claude.com/docs/en/sub-agents) and [model configuration](https://code.claude.com/docs/en/model-config). Installed tool/schema, loaded-definition, and effective-setting evidence are required.
