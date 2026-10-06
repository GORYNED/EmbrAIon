# Changelog

## Unreleased

### Added

- Project-owned skills under `.embraion/skills/<name>/SKILL.md` are projected by the `skills` component next to the Core skills for Codex, Copilot and Claude Code, recorded in the projection ledger, and checked by `projection diff` and `projection verify`, including removed skills as obsolete. A name that matches a Core skill, an unsafe name, a symbolic link, or `SKILL.md` front matter without a matching `name` and a `description` stops projection before anything is written.
- Project specialist profiles for Claude Code, Codex and Copilot list the specialist's `triggers` and `outputs`, and the projected `orchestration` skill gets a `Project specialists` section with each specialist's ID, purpose, and declared triggers and outputs. Nothing is added when `.embraion/agents.yaml` declares no specialists.
- Optional `.embraion/integrations.yaml` declares expected MCP servers per host (`id`, `host`, `command`, `args`, `transport`, `access`, environment-variable names in `env-vars`, and `portable`). When it exists, `embraion security scan` and `doctor` report missing, unexpected, and mismatched servers (command, arguments, transport, environment-variable names), non-portable declarations with machine-absolute paths, invalid declarations, and unreadable host configuration as high-severity `integration-drift` findings. Without the file nothing is compared.
- Validation profiles accept an optional `timeout-seconds`: one value for every command or a list with one value per command. `--timeout` overrides it.
- `embraion validation run` writes each command's full redacted output to `.embraion/state/validation/<evidence-id>/command-<index>.log` and records the log path and effective timeout per command. With `--run-id`, commands receive the run ID as `EMBRAION_RUN_ID`.
- Core rules: preserve observable runtime behavior unless the task authorizes a change and default new options to the previous behavior; unverified compatibility impact is treated as breaking; report reusable upstream candidates, landing the upstream pull request before the consumer pin update; remove a duplicated instruction only after its canonical replacement reaches every host the project uses.
- `deferred-tasks` project contract slot for the project's list of deferred tasks; the owner-interaction rule reads the configured slot.

### Changed

- Projected orchestration guidance and the Codex managed block link to the Core worktree workflow at the release tag of the projected framework version instead of a source-relative `../../core/` path that does not exist in a consuming project. A link to a missing Core file stops projection.
- With Claude Code `scoped-agents` selected, `projection diff` and `projection verify` report every `.claude/agents/embraion--*.md` file the current projection would not produce as `obsolete-modified`, even without a local ownership ledger. `--prune` keeps such files because their ownership is unproven.
- `embraion validation run` starts each command in its own process group (new session on POSIX, `CREATE_NEW_PROCESS_GROUP` on Windows) and terminates the whole process tree on a timeout or interrupt instead of only the direct child.

## 0.26.0 - 2026-10-06

### Added

- Core rules reach every host at startup: `.claude/rules/embraion-core.md` for Claude Code, `.github/instructions/embraion-core.instructions.md` with `applyTo: "**"` for Copilot (both owned by the `skills` component), and the managed Codex `developer_instructions` block. Previously only the portable bundle carried the rule texts. Experiment snapshots for Copilot include the instruction file. Whether a surface applies the files is checked on that surface.
- Core rules for progress checklists and stage updates, reminders of a project's deferred tasks, compatibility that stays unresolved until verified with source and persisted-data compatibility reported separately, and no real user, customer, or device data in pull requests, issues, commits, shared chat channels, or reports that leave the owner's workspace.
- Organization `filenames` checks: files under `roots` (`.` for the whole repository) with a listed extension need lowercase kebab-case stems with an optional numeric version (`filename_style`, `filename_extension_case`), and case-only path collisions are reported (`filename_collision`). Ecosystem and host basenames, host-native suffixes in their folders, reserved scoped Claude profiles, and dot-prefixed names are exempt; `allow` and `suffixes` extend them.
- Organization `unity_meta.require_for_all` requires an adjacent `.meta` for every file under its roots, and `unity_meta.check_orphans` reports `.meta` files without an asset file or folder (`meta_orphan`). `embraion organization check --require-config` fails instead of skipping when the configuration is missing.
- `embraion security scan` reports provider-prefixed access tokens as `access-token` (high) and home-directory machine paths as `machine-path` (medium); `security redact` and evidence redaction replace bare prefixed tokens with `<REDACTED:access-token>`.
- `embraion security scan --all-files` also checks every other tracked or unignored text file up to 2 MiB, such as source code, for private keys, access tokens, and machine paths.
- Report contract `workers.summary: true` requires a compact summary after the Workers table, and `embraion report validate --pull-request-not-created` requires a compare URL when a needed pull request was not created.
- `core/routing/complexity.yaml` lists `critical` examples and what is `not-critical`.
- `embraion execution envelope` builds `payload.inputsByDeployment` for every adapter-bound candidate from committed blobs at an explicit commit, bound to each binding `contextBoundary`, with per-file digests. It fails closed on paths outside the repository, protected or withheld paths, symlinks, LFS pointers, binary files, credential material, machine-local paths, data classes above the request, and byte bounds, including an optional binding `maxContextBytes`.
- `embraion execution health` shows per-deployment health from the local attempt ledger.
- `embraion execution preflight` checks adapter-bound candidates (or `--deployment` bindings) for binding completeness, request ceilings, credential presence, and adapter preflight with the built payload, without a provider call or credential output.
- `embraion pricing verify --fixtures <yaml>` compares offline costs for reviewed usage fixtures with expected amounts as exact decimals.

### Changed

- The release workflow accepts `Co-authored-by` trailers after the exact `release: vX.Y.Z` subject, so a squash merge that includes another author's commit can still release; any other body text still stops it before the tag.
- Policy ceilings also check host overrides (`overrides.<host>` in `.embraion/routing.yaml`): every request an override matches must stay within the ceiling, so a `routes` override is `ceiling-unbounded` under a role ceiling, a `roles` or `route-roles` override is checked against the role ceiling, either is `ceiling-unbounded` under a data-class ceiling unless the selected deployment's `capabilities.data-classes` stay within it (routing refuses other data classes), and `task-classes` overrides are checked like routing task classes.
- Tests and examples no longer use consuming-project paths.
- Core review guidance names a hosted bot review generically instead of a specific vendor's review product.
- `embraion execute` now persists each validated, redacted attempt to the bounded local ledger `.embraion/state/execution-attempts.jsonl` (one rotation, truncated-line recovery). When a request supplies no `healthObservations`, it orders candidates and skips unavailable ones by ledger health.

## 0.25.0 - 2026-10-06

Includes the 0.24.0 changes below: the 0.24.0 release run was cancelled before it was tagged, so 0.24.0 was not published.

### Added

- `eval skills run` supports `--host claude-code` (Claude Code CLI with project skills under `.claude/skills`) and `--host portable` (any agent CLI given with `--host-command`, skills under `--skill-dir`), in addition to `codex`. The report's `evidence-kind` names the host.
- Optional `architecture-decision` skill: records a durable architecture decision in the project's own decision-record location, template and numbering, supersedes instead of rewriting accepted records, and updates the index in the same change. Live suite `evals/skills/architecture-decision.json`.
- Core agent-behavior rules moved from project handbooks: `authorization` and `owner-interaction` rules, honest-check reporting in the `evidence` rule, and a `handling-review-findings` skill. Catalog version 9.
- The `authorization` rule limits roles other than Lead: they change external or shared state or act on the owner's behalf only when the assignment explicitly grants it, and owner-facing communication goes through Lead.
- The `instructions` rule states that each fact has one canonical owner that other documents link to instead of restating.

### Removed

- The repository's CodeRabbit configuration; CodeRabbit is no longer used for review.

## 0.24.0 - 2026-10-06

### Added

- `projection verify --config-mode merge` reports `root-findings` for Codex content outside managed ownership: root model/effort or `agents.default_subagent_*` overrides, keys outside an optional `allowed-root-keys` list, and root instructions outside the managed orchestration block. `--strict-root` or `policy.yaml` `projection.codex.strict-root` makes them fail verification.
- Policy `ceilings` declare the most a project allows per provider, data class, execution source, and pinned task class. `embraion policy check` and `embraion validate` fail when deployments, execution bindings, or routing widen them, and `critical.justifications` makes critical-route reasons a closed set at routing and execution time.
- Completion report contract: `.embraion/report.yaml` declares the final report sections, the Workers table columns, the `Task status` values, and the pull request link rule. `embraion report template` renders it, the orchestration skill projection embeds it, and `embraion report validate` checks final and intermediate report text.
- Read-only `embraion update --check [--json]` compares the launcher and project pin with the latest stable GitHub Release, validates that release's expected wheel and SHA-256 digest metadata, and lists the next upgrade steps without writing project files.

### Changed

- The release workflow proposes the self-host pin, artifact lock and Codex, Copilot, Claude Code and Portable projection upgrade as a `chore/self-host-vX.Y.Z` pull request after the GitHub Release is published, and dispatches `validate` and `docs` for it. Merging remains a human decision.

### Fixed

- Experiment tree inventories skip a local `.venv`, so the virtual environment recommended in CONTRIBUTING no longer fails experiment tests on its internal symlinks.

## 0.23.0 - 2026-10-05

### Added

- Conditional, vendor-neutral `security-assessment`: reachable threat flows, effective controls, evidence-based mitigations, residual risk, and exclusions for unrelated changes.
- Eval v2 manifests and named variants, contamination checks, mandatory oracle coverage, registered trusted checks, independent regression budgets, and promotion blocking for mandatory inconclusive evidence.
- Privacy-safe failure corpus with reviewed active, superseded, and retired lifecycle states, plus protection scenarios and trusted checker calibration.

### Changed

- Strengthen twelve existing Core skills for current intent and authority, completion evidence through wiring and consumers, compact two-axis review, bounded repository-first research, causal debugging, independent test expectations, fresh checkpoints, and accurate documentation.
- Add pre-change behavioral characterization and post-change comparisons to existing code-organization, compatibility-migration, and test-design procedures.

### Compatibility and evidence

- Preserve eight agent roles, eval v1 semantics, historical experiment outcomes, and existing learning promotion gates. No standalone refactoring skill or automatic consumer upgrade is introduced.
- Generate Codex, Claude Code, Copilot, and portable instructions from the same Core. Deterministic checks and independent instruction review do not establish measured live model-quality or cross-host behavior improvements.

## 0.22.0 - 2026-10-04

### Removed

- Remove the shipped optional Unity skill bundle and its navigation. Unity reference projects and project-configured organization checks remain available.

### Compatibility and migration

- Schema v1 retains `builtin:unity` only to read legacy inventories and report the entry unavailable. Install rejects it for a selected host, and update rejects it, before writes; no automatic conversion or version bump occurs.
- Install a desired replacement independently through the host, explicitly remove the legacy inventory entry, and then run an owned-file prune for old projections. Modified or unowned files are preserved.

## 0.21.0 - 2026-10-04

### Added

- Opt-in housekeeping before independent writable tasks, with one cleanup attempt per task ID and preservation of user, unknown, active and protected resources in the current repository.
- A shared Git-common-dir registry records verified creation identity, host provenance and linked task lifecycle without inferring ownership from branch prefixes, commit authors or PR authors.
- Extend `worktree gc` with JSON reports and add `prepare`, `register`, `publish` and local `restore`. Retain verified commit bundles and necessary local state before deletion, repeat eligibility checks, serialize operations and report partial failures with recovery identifiers.
- Verify exact-head merged PR evidence for ordinary and squash merges. Managed remote creation and subsequent fast-forward publications retain a receipt chain and use exact Git SHA leases; cleanup also removes only the matching cached origin ref.

### Safety and compatibility

- Automatic and remote cleanup default to off. Legacy markers retain worktree-only cleanup rights; unsupported native activity/archive operations and unproven remote-only resources remain preserved.
- Reject symbolic or aliased refs and credential-bearing remote URLs. Local compare-and-delete never dereferences refs, and empty subprocess errors omit command arguments.
- Codex and Claude guidance invokes the common preflight without assuming native startup interception or changing observer hooks. Consumer upgrades and first cleanup of existing resources remain explicit follow-up work.

## 0.20.0 - 2026-10-03

### Added

- Five conditional Core procedures: skill authoring, compatibility migration, test design, performance investigation, and dependency upgrades; an original MIT Unity bundle selects serialization, lifecycle, player validation, and asset audit skills without importing external plugin frameworks.
- Optional external capability inventory, bounded diagnostics, and ownership-aware projection of selected built-in skills to all four hosts. Declarations, installation, host discovery, instruction reading, tool readiness, and execution remain separate evidence stages.
- Configurable C# namespace, Unity assembly boundary/platform/cycle, and asset metadata/GUID checks, including incremental comparisons that expose existing debt and reject new findings.
- Local metadata-only task checkpoints and read-only freshness checks, plus explicit documentation/source baselines and advisory knowledge drift audits.
- A live Codex skill evaluation runner with isolated baseline/candidate/previous sessions, repeated cases, declarative grading, source digests, privacy-minimal reports, and separate skill-read evidence. An English/Russian sample suite and unit tests verify the runner; live behavior requires an available authenticated host.

### Documentation

- Add paired English/Russian configuration and task guides, CLI references and navigation. Distinguish live UI evidence from static inspection and semantic evaluation from deterministic harness tests.
- Existing overlays without the optional files keep their current behavior. External host-managed plugins remain independently installed and are never copied or downloaded by these commands.

## 0.19.2 - 2026-10-03

### Added

- Add the portable `code-organization` skill for responsibility-based placement and scoped migration of files and types, guided by project coding standards, ownership, dependency boundaries, and compatibility contracts. Implementation and orchestration load it before structural changes; internal review checks placement, namespaces, and dependencies.
- Project bootstrap discovers authoritative coding standards through existing project knowledge entries. Host projections deliver the same organization procedure without imposing a product-specific folder tree.

### Documentation

- Record anonymized maintainer-reported Claude Code Desktop 0.19.1 checks on Windows, distinguishing worktree callback observations and host transcript model fields from unverified effective effort. Fix the Russian daily-workflow review link.

## 0.19.1 - 2026-10-03

### Fixed

- Claude guard and observer use the hook event working directory to select policy and evidence storage, so desktop commands launched from the main checkout correctly target the active worktree. Relative tool paths use the event working directory while protected policy remains rooted in its worktree. Invalid event context or a different worktree runtime version or artifact identity fails closed instead of falling back to main. Legacy events without a working directory retain their existing behavior.

## 0.19.0 - 2026-10-03

- Make host-native independent review a reusable Core lifecycle for every PR: completed author self-review and required checks before dispatch, author remediation, and exact final PR-head confirmation by a different read-only Reviewer. Copilot Review is not a prerequisite; merge/release authorization stays separate.

### Added

- Opt-in Claude startup scoped-agent projection derives complete native definitions from explicit project assignments, preserving model-neutral reusable roles and existing projection ownership protections.
- Claude native hook setup preserves unrelated host settings, guards configured Agent/Task calls, and records only bounded native identity and optional reported effort metadata. Command-input evidence is advisory; effective model, effort and unsupported host surfaces remain explicitly unverified.
- Policy path matching includes zero-depth `**/` segments while preserving legacy wildcard matches; excessive recursive-pattern complexity fails closed.

### Fixed

- Route validation checks direct host, role, route-role and task-class override references as well as configured task candidates without recording fake execution selections.
- Routing authority audits accept byte-identical canonical projections in fresh checkouts without a local ownership ledger while continuing to flag modified copies.
- Claude guidance distinguishes the active worktree pin, loaded scoped definitions, native tool-context effort and standalone CLI sessions.

## 0.18.2 - 2026-10-03

### Fixed

- Generate Claude and Copilot agent profiles with LF on every platform. Windows projection verification now accepts unchanged LF checkouts while preserving conflict protection for actual local edits.

## 0.18.1 - 2026-10-03

### Fixed

- Installed Codex, Copilot, and Claude orchestration skills, plus Codex root instructions, link to their embedded assignment routing contract instead of a source-only relative path. Regenerate the orchestration skill and Codex config when upgrading.

## 0.18.0 - 2026-10-03

### Fixed

- Claude skills install an owned, unconditional orchestration entry rule without replacing user `CLAUDE.md` imports or unrelated skills.
- Claude native plans preserve full model IDs and effort in complete scoped definitions, retain specialist permissions, and separate project routing roles from native agent identities. Loading and effective settings still require host evidence.
- Claude native names use bounded machine IDs rather than display titles containing spaces or slashes; regenerate profiles and use the emitted identity when upgrading.
- Harness readiness checks required projection files and reports missing paths; it explicitly leaves instruction loading, runtime settings, and execution unverified.

### Changed

- Every selected critical route now requires a nonblank justification, including direct route, dispatch, run start, and execution requests. Existing critical callers must provide their reason. Optional escalation inspection and configuration validation do not count as selected execution routes.

### Added

- An opt-in Claude Mods capability probe registers one reviewed scoped definition on request and observes native routing evidence. It is never installed automatically; mock tests do not establish live host support.

## 0.17.1 - 2026-09-30

### Fixed

- Preserve Unicode, quoted and newline Git paths in enforcement and worktree discovery; normalize platform path separators in regression checks.
- Preserve user-owned, active, ambiguous or unfinished worktrees during garbage collection.
- Allow enforcement after run completion without attaching evidence to closed runs; bind passed reviews to the reviewed Git state and reject stale or validation-time changes.
- Reject unsupported LiteLLM effort/options before provider calls and retain safe actionable diagnostics in public execution results.
- Include every Portable catalog capability and align bundle metadata with the generated contents.
- Prevent projection writes through nested aliases, predictable temporary symlinks and hardlinks; preserve files modified before pruning.
- Count independent learning evidence idempotently across run/eval associations, recheck promotion thresholds and align learning evidence with its schema.

## 0.17.0 - 2026-09-29

### Added

- Canonical Project Bootstrap skill: ordinary-language repository onboarding discovers authoritative knowledge, ownership and real validation, preserves existing decisions, keeps project agents minimal and routing optional, and verifies the resulting contract.
- Evidence-bound `embraion bootstrap plan` and `apply` operations for conservative project configuration. Plans execute no commands; stale, modified, unsafe or invalid plans fail before mutation. Existing populated settings, project routing, agents and artifact locks are preserved.
- Cross-host Bootstrap projection, generic minimal/mature/partial repository regression coverage and a behavioral grading case with explicit evidence limitations.

### Changed

- English and Russian onboarding, README, configuration, FAQ and host/routing documentation follow `init` -> host projection -> "Configure EmbrAIon for this project" -> ordinary engineering requests. Advanced tuning uses only confirmed host capabilities and project-owned choices.

## 0.16.3 - 2026-09-29

### Fixed

- Delegated assignments follow one host-neutral Core routing contract: resolve each assignment before dispatch, apply explicit project fields through verified native capabilities, and permit host-default inheritance only for actual host-default resolution. Unsupported settings and conflicting native precedence require a capability limitation or supported handoff.
- Task-class candidates retain their routing resolution so missing models and partial project overrides cannot be mistaken for host-default. Writable dispatch ownership and branch checks also cover the workspace-write access spelling.

### Added

- Native delegation guidance for Codex, Copilot CLI/VS Code/cloud, and Claude Code, with distinct model, effort, definition, and precedence behavior. All executable host skills receive their adapter guidance; Portable carries the canonical contract without runtime claims.
- Optional native preparation on the existing dispatch command, producing reviewable arguments or scoped definition overrides with explicit capability limitations and handoff requirements. Prepared plans never claim execution.
- Capability-aware cross-host regression coverage and a canonical assignment-routing behavioral eval in validation and both release gates.

## 0.16.2 - 2026-09-28

### Changed

- Host-native Lead orchestration dispatches architecture, ownership, dependency-direction, and cross-package work to matching Core specialists before writable implementation, regardless of final diff size; Lead integrates the results and retains final acceptance authority.

### Added

- Generic cross-package orchestration regression coverage for specialist dispatch, analysis-before-write ordering, scope preservation, result integration, and Lead final authority.

## 0.16.1 - 2026-09-28

### Fixed

- Independent child processes no longer inherit interpreter-scoped runtime resolution state. Cached runtime imports remain isolated from source `PYTHONPATH` during installation, probing, delegation, and prior-projection generation.
- Self-hosted framework validation and CI explicitly select source code and data while preserving the published stable project pin, artifact lock, project routing, and generated Codex Core agents.
- Framework-default routing and CLI-version tests use isolated project roots. Regression coverage exercises a newer source checkout under an older locked runtime environment.
- Generated Codex TOML and skill entry points use canonical LF bytes so clean clones preserve projection ownership across platforms; recorded legacy CRLF projections upgrade without forced replacement.

## 0.16.0 - 2026-09-28

### Added

- Canonical proportional Lead orchestration for ordinary-language engineering requests, assignment routing, safe parallelism, fresh validation, independent review, and final integration.
- Codex root `developer_instructions` derived from Core Lead semantics and native adapter guidance, alongside the existing model-neutral specialists.
- An orchestration skill carrying the derived Lead contract across Codex, Copilot, Claude Code, and Portable projections.

### Changed

- Codex merge mode preserves user instructions and unrelated TOML using syntax-aware ownership, updates only the managed orchestration subsection and required agent settings, and rejects ambiguous state even with `--force`.
- Delegated assignments resolve project routing before supported native spawn selection; static configuration is documented as guidance rather than deterministic per-spawn routing enforcement.

### Fixed

- Regression coverage explicitly preserves Core specialists and root Lead orchestration when project agents are empty.

## 0.15.3 - 2026-09-28

### Fixed

- Projection ownership and recovery evidence are now scoped by host and canonical destination, preserving root provenance during alternate destination installs with automatic compatibility for matching legacy ledgers.

## 0.15.2 - 2026-09-28

### Fixed

- Mixed API/native execution routes now require LiteLLM inputs only for candidates bound to that adapter on the current execution host, preserving provenance validation, fail-closed external fallback inputs, and native host handoff.

## 0.15.1 - 2026-09-27

### Fixed

- Routing-authority audit now distinguishes active concrete routing mappings from schema and telemetry field names, generic code, unrelated comments, and historical prose.
- Explicit audit paths are canonicalized before project-root comparison, fixing Windows/macOS path-alias false negatives while preserving fail-closed generated-projection ownership checks.

## 0.15.0 - 2026-09-27

### Added

- Project-defined task classes that map semantic work to Core route classes, optional roles and minimum data classes, and ordered host candidates.
- Task-class routing with availability fallback, explicit quality or critical escalation, candidate groups, and provenance in route results.
- An authority audit for duplicate project routing, deployment, execution, and pricing facts outside `.embraion/**`.

### Changed

- Task-class overrides take precedence over route-role, role, and route overrides while preserving Core access and privacy limits.
- Re-review assignments are classified from their current delta; unavailable deployments do not increase task complexity.

## 0.14.0 - 2026-09-27

### Added

- Framework-owned release artifact locking in `.embraion/project.yaml`, binding the project framework version to the canonical GitHub release tag, exact Python wheel identity, and verified server-side SHA-256 digest.
- `embraion framework verify` to re-download and verify the exact locked release artifact without installing it.
- `embraion framework install` to verify the locked wheel before installing it into the isolated project-runtime cache.
- A post-publication release smoke that exercises a real consumer `init → update → framework verify → framework install` flow using only the project pin/lock.

### Changed

- `embraion update` now resolves published release metadata before mutation and atomically writes `framework.version` together with `framework.artifact`.
- Existing version-only project overlays can upgrade without manual migration; missing compatible modular configuration files are materialized from framework defaults.
- Project runtime resolution uses the locked GitHub release wheel when a lock is present and binds reusable cache markers to the same artifact identity and digest.
- YAML configuration writes use atomic replacement, with `.embraion/project.yaml` written last as the update commit point.

### Security

- Artifact resolution and installation fail closed for missing release assets, malformed locks, invalid or mismatched digests, and version/release/asset mismatches.
- Consumer CI no longer needs a separately hardcoded EmbrAIon wheel SHA-256 or custom release-download/checksum parsing.


## 0.13.3 - 2026-09-27

### Added

- Complete English/Russian documentation parity with a site language switcher, beginner-first onboarding, and diagrams for host-native/provider execution, deployment-routing-execution-pricing, and guidance/enforcement.

### Changed

- English is the canonical documentation language and Russian is the only maintained translation; legacy Spanish, Hindi, Simplified Chinese, and legacy localization-tree content are removed.
- Framework localization validation now requires a Russian translation for every canonical English documentation page and rejects the legacy `localization/` tree.
- Packaged framework distributions now include `README.ru.md` and `TRADEMARKS.ru.md`, with installed-package regression coverage.
- Documentation metadata now points to `https://embraion.goryned.com/`.
- Routing, execution, provider, schema, and project-runtime behavior are unchanged from 0.13.2.

## 0.13.2 - 2026-09-26

### Fixed

- Security scanning no longer treats .NET `PublicKeyToken` assembly metadata as an API credential while preserving detection of standalone API-key, secret, token, and password assignments.
- Security scanning now honors explicit project `CONFIDENTIAL` aliases declared in `.embraion/execution.yaml`, so intentional project vocabulary is not reported as legacy data-class drift.

## 0.13.1 - 2026-09-26

### Fixed

- Provider-origin HTTP 402 now maps to quota exhaustion so consuming projects can retain non-operational billing health semantics.
- Provider-origin HTTP 404 now maps to provider unavailability for correct bounded fallback and availability observations.

## 0.13.0 - 2026-09-26

### Added

- Provider-neutral execution request/result, failure, health, bounded-attempt, fallback, and adapter contracts that preserve the original privacy, access, role, task, source/trust, and ownership ceilings.
- An optional LiteLLM loopback execution adapter with scoped credential resolution, signed context provenance, no internal retry or model substitution, provider/model and correlation evidence, bounded output, and child-process cleanup.
- Project-owned pricing configuration with approved official-source refresh, validated atomic snapshots, offline status, stale/diff reporting, and deterministic cost calculation without execution-time network dependency.
- Version-tied provider/adapter usage-overlap evidence for snapshot-derived token costing; ambiguous usage remains unknown instead of being guessed or treated as zero.

### Changed

- Execution and pricing remain opt-in project capabilities, so existing 0.12 projects retain their routing behavior unless they explicitly adopt the new contracts.
- Concrete provider/model selectors, pricing sources, SKU mappings, rates, and freshness policy remain project-owned; EmbrAIon Core remains model-, provider-, and project-agnostic.
- Pricing parser dependencies are required only for explicit refresh; offline pricing status and calculation use the last validated local snapshot.

## 0.12.0 - 2026-09-26

### Added

- Project-owned deployment/provider registries in `.embraion/deployments.yaml`, keeping EmbrAIon Core model-agnostic while giving consuming projects a canonical place for reusable host/model selections, supported effort, billing metadata, capabilities, and non-secret metadata.
- Deployment-aware routing and ordered fallback plans: `.embraion/routing.yaml` can reference deployment IDs, and `embraion route` fails closed on unknown, disabled, host-mismatched, effort-incompatible, or capability-ineligible deployments.
- `embraion deployment list/show` for human- and machine-readable inspection of the project deployment registry.

### Changed

- Compatible projects created before `deployments.yaml` existed are upgraded safely by creating only the new empty registry; missing older canonical modular configuration files still fail closed.
- Route/dispatch host names are now project-extensible rather than limited by CLI parser choices, while host projection installation remains limited to supported EmbrAIon adapters.

## 0.11.0 - 2026-09-26

### Added

- Parameterized project validation profiles: structured `.embraion/validation.yaml` entries can declare required/default runtime parameters projected as safely quoted command arguments or child-process environment variables and supplied with repeatable `embraion validation run --param NAME=VALUE`.
- Safe partial ownership for Codex `.codex/config.toml` through `--config-mode merge`, allowing EmbrAIon to manage its required `[agents]` settings while preserving project-owned agent settings and other Codex tables.
- `embraion projection verify` as a fail-closed CI gate that exits non-zero for missing, stale, conflicting, or obsolete managed projection output.


## 0.10.2 - 2026-09-25

### Fixed

- All non-Lead Core agents now explicitly prohibit recursive delegation. Project agents receive the same canonical guard whether they extend a Core role or are standalone, so generated Codex, GitHub Copilot, and Claude Code profiles preserve the Lead-only delegation boundary consistently across hosts.
- Projection contract tests now verify the recursive-delegation guard across all seven non-Lead Core profiles, inherited project agents, and standalone project agents.

## 0.10.1 - 2026-09-25

### Fixed

- Framework updates can now recover host-projection ownership in fresh worktrees when gitignored projection state is absent. Recovery is accepted only for files that are byte-identical to the exact previous pinned-version projection; locally modified or unproven files still fail closed as conflicts.
- Successful projection installation promotes recovered ownership into ordinary local projection state and removes the temporary recovery evidence.

## 0.10.0 - 2026-09-25

### Breaking

- The top-level `slots` key in `.embraion/knowledge.yaml` is now reserved for Project Contract Slots. EmbrAIon is still pre-1.0 and this change intentionally establishes the clean contract instead of carrying a compatibility shim for arbitrary legacy entries named `slots`.

### Added

- Canonical Project Contract Slots in `.embraion/knowledge.yaml` for constitution, architecture, source authority, compatibility, persistence, project engineering workflow, and specification bindings.
- `embraion context slots` for inspecting configured project bindings, plus repeatable `context build --slot` requests for explicit semantic context selection.

### Changed

- New project configuration seeds the canonical slot catalog with unbound values while preserving arbitrary project knowledge entries.
- Core context selection applies framework-owned default task triggers to bound contract slots and keeps project-owned metadata overrides authoritative.

## 0.9.4 - 2026-09-25

### Changed

- Generated GitHub Copilot agents now opt into repository custom instructions when invoked as subagents, closing the default delivery gap for repository governance such as `AGENTS.md`.
- Copilot adapter documentation now distinguishes requested tool aliases from effective host capabilities and documents skills as root/session-owned unless explicit per-subagent delivery is supported.
- Core skill documentation no longer assumes automatic root-to-subagent skill inheritance across hosts.

### Fixed

- Copilot custom-agent projections now emit `include-custom-instructions: true`, with contract tests covering Core agents and inherited project agents.

## 0.9.3 - 2026-09-25

### Changed

- Core agent access is now a host-agnostic contract projected into enforceable host-native controls for Codex, GitHub Copilot, and Claude Code; host and organization policy may tighten access but EmbrAIon never widens it.

### Fixed

- Claude Code agent projections now include explicit `tools` allowlists derived from Core `read-only` / `workspace-write` access instead of relying only on textual restrictions.
- Host access projection now fails closed when a supported execution host lacks a mapping for an agent access class.

## 0.9.2 - 2026-09-25

### Added

- Core Artifact Authority rule: project-specific naming, layout, schema, and formatting conventions apply to project-owned surfaces, while host-, framework-, tool-, package-, external-, and vendor-owned artifacts preserve their authoritative contracts.

### Fixed

- GitHub Copilot projections now map Core agent access to explicit host tool permissions, keeping read-only agents limited to read/search capabilities and writable agents explicitly scoped to read/search/edit/execute.
- Copilot projection contract tests now verify all seven projected Core agents, all eight Core skills, Lead exclusion, model-agnostic frontmatter, and inherited project-agent permissions.

## 0.9.1 - 2026-09-24

### Fixed

- Protected-source enforcement now covers deletions, rename sources, and dot-prefixed paths instead of allowing those changes to escape path checks.
- Runtime project configuration readers now validate canonical `.embraion/*.yaml` files against their schemas and fail closed on malformed user configuration.
- `embraion update` now refuses a target version that differs from the installed launcher and rejects non-mapping configuration instead of silently normalizing it.
- Generated Copilot and Claude Code agent frontmatter now safely quotes custom agent titles containing YAML-significant characters.

## 0.9.0 - 2026-09-24

### Added

- Explicit opt-in enforcement with `embraion enforcement status/check/install`, combining protected-source policy, executable validation evidence, and optional review gates.
- A conflict-safe GitHub Actions enforcement surface generated only on explicit request, with pinned EmbrAIon version, pull-request validation, protected-path checks, and optional approval enforcement.
- Harness audit visibility for the explicit GitHub Actions enforcement surface while native host hooks remain audit-only and are never installed silently.
- First-class executable project validation profiles through `embraion validation list` and `embraion validation run <profile>`.
- Redacted per-command validation evidence persisted under `.embraion/state/validation/`, with optional `--run-id` attachment to active execution evidence.
- Explicit skipped, failed, timeout, fail-fast, and machine-readable JSON behavior for project validation runs.
- Project-specific agent definitions in `.embraion/agents.yaml` with optional inheritance from non-Lead Core roles and native Codex, GitHub Copilot, and Claude Code projection.
- Project-agent safety checks that prevent Core agent ID shadowing, Lead inheritance, and access widening across inherited roles.

### Changed

- `embraion update` now safely normalizes compatible modular project configuration by adding only missing defaults, validating every candidate before writing, and leaving generated host projections/state untouched.
- Incompatible user-owned configuration and incomplete legacy layouts now fail closed instead of being rewritten heuristically.

## 0.8.1 - 2026-09-24

### Added

- A semantic model-agnostic validation invariant that rejects legacy model-tier route names, Lead-owned concrete model selection wording, obsolete `routing.overrides` paths, and model-routing overrides incorrectly documented under `.embraion/project.yaml`.

### Fixed

- Remaining Core and localized architecture wording now consistently keeps task/host routing with Lead, concrete model selection with the execution host, and project model overrides in `.embraion/routing.yaml`.

## 0.8.0 - 2026-09-24

### Added

- A dedicated Configuration documentation section with a full `.embraion/` template, file-by-file customization reference, and practical Codex, GitHub Copilot, and Claude Code setup examples.
- Dedicated `.embraion/routing.yaml` project configuration with its own schema, keeping model/effort/options overrides separate from project identity and policy.
- Dedicated `.embraion/policy.yaml` project configuration with its own schema for source classes, substantial-review policy, and default privacy.
- Dedicated `.embraion/knowledge.yaml` project configuration with its own schema for knowledge paths and context-selection metadata.
- Dedicated `.embraion/validation.yaml` project configuration with its own schema for project validation profiles.
- Dedicated `.embraion/agents.yaml` project configuration with its own schema for project-specific agent declarations, while `capabilities` remains in `project.yaml`.
- Model-agnostic project routing overrides by host, route class, and role. Overrides accept opaque host-owned model selectors, effort strings, and options without requiring an EmbrAIon model catalog.
- A projected `routing-configuration` skill that teaches AI clients to write optional model overrides only to `.embraion/routing.yaml` while preserving host-default behavior and Core safety policy.
- A validation invariant that rejects framework-owned model catalogs and adapter route-to-model maps if they are reintroduced.

### Changed

- Routing now resolves to the host's own default/automatic model policy unless a consuming project explicitly overrides it.
- Core route classes are now task-oriented (`bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, `critical`) instead of implying model strength or cost tiers.
- Lead and fallback policy no longer own concrete model selection or model-to-model fallback; those remain host-owned unless a project explicitly overrides them.
- Canonical and localized documentation now describe the same model-agnostic ownership model.
- Generated Codex configuration no longer pins a framework-chosen default model or reasoning effort.

### Removed

- Built-in host/provider model catalogs and hardcoded route-to-model mappings. Model availability is owned by the execution host or consuming project rather than EmbrAIon Core.

## 0.7.0 - 2026-09-24

### Added

- Selective host projection adoption through repeatable `--component` flags on `install` and `projection diff`, allowing mature repositories to adopt skills or agents without replacing existing host-owned configuration.
- Project initialization now creates `.embraion/.gitignore` so local runtime state and cache data stay untracked by default.

## 0.6.1 - 2026-09-24

### Added

- Minimal child-process safety helpers for environment allowlisting and stdout/stderr redaction in future execution adapters.

### Fixed

- Projection ownership state now retains obsolete generated entries until clean files are explicitly pruned, so later diff/prune operations remain deterministic even after an install without `--prune`.

## 0.6.0 - 2026-09-24

### Added

- Host-native project Skills projection for Codex, GitHub Copilot, and Claude Code using reusable `SKILL.md` directories.
- Project Overlay v2 contracts for canonical/protected/generated/external source classes, validation profiles, substantial-review policy, and default privacy classification.
- Ownership-aware projection planning with dry-run/diff, generated-file hashes, conflict detection, safe updates, and conservative obsolete-file pruning.
- Selective project-context records with data classification, role/task eligibility, trust/provenance, content hashes, and explicit character budgets without duplicating knowledge contents into state.
- Structured execution evidence records for route choice, access, owned paths, context identity, changed paths, validation, review, outcomes, and residual risk.
- Runtime credential redaction across persisted telemetry and execution state.
- Harness capability audit for generated agents/skills and native hook/enforcement surfaces.

### Changed

- Project initialization now creates Project Overlay v2 safety defaults.
- Re-installing an unchanged generated host projection is idempotent; locally modified or unowned conflicts are refused unless replacement is explicitly forced.


## 0.5.0 - 2026-09-24

### Added

- A full MkDocs Material documentation site with branded navigation, search, dark/light modes, and GitHub Pages deployment.
- Getting Started guides for installation, first-project bootstrap, and intentional project updates.
- Concept guides for agents, skills, knowledge, routing, and project overlays.
- Host guides for Codex, GitHub Copilot, Claude Code, and Portable projections.
- A consolidated CLI reference and walkthroughs for Minimal, Python, and Unity usage examples.
- Open-source documentation pages for contribution, support, security reporting, and governance.
- Deterministic documentation tests covering nav targets, internal links, site assets, CLI command coverage, and the published documentation URL.
- A dedicated documentation workflow that performs strict MkDocs builds on pushes and pull requests and deploys the built site to GitHub Pages from `main`.
- Strict documentation builds in the release preparation and tagged-release gates.

### Changed

- Package metadata and the repository README now point to the public documentation site while preserving Markdown sources in `docs/`.
- Framework, package, template, and reference-project pins are aligned at `0.5.0`.


## 0.4.3 - 2026-09-24

### Fixed

- The Unity reference project now explicitly enables the built-in `com.unity.modules.imgui` module required by `CounterSampleView`.
- Reference-project E2E now verifies that the IMGUI module dependency is present, preventing the sample UI from compiling against a disabled Unity module.

### Changed

- Unity reference documentation now states that IMGUI is a built-in Unity module rather than describing the sample as dependency-free.

## 0.4.2 - 2026-09-24

### Added

- A runnable Unity reference `SampleScene.unity` with a live value display and Increment / Reset controls.
- Stable Unity `.meta` GUIDs and build settings that link the sample scene to its controller and view scripts.
- Structural E2E checks for Unity scene/script/build-settings linkage.

### Changed

- The Unity reference keeps presentation in `CounterSampleView`, lifecycle/state coordination in `CounterController`, and deterministic state in pure C# `CounterState`.
- The sample UI uses built-in Unity IMGUI to stay dependency-free.

## 0.4.1 - 2026-09-23

### Changed

- The Unity reference project now uses the conventional `Assets/Scripts/` layout.
- Reference-project privacy checks no longer encode project-specific identifiers in the public repository; validation stays generic and structural.

## 0.4.0 - 2026-09-23

### Added

- Complete Minimal, Python, and Unity/C# reference projects under `examples/`.
- Deterministic consuming-project lifecycle E2E covering project status, diagnostics, all host projections, overwrite protection, forced regeneration, and clean `init` bootstrap.
- A dedicated wheel-backed Reference Projects E2E CI job that runs outside the source checkout.
- Validation for project-overlay schema, canonical repository/version alignment, and reference-project knowledge paths.

### Changed

- The canonical project-overlay template now tracks the active EmbrAIon framework version.
- Reference project manifests are version-locked to the active EmbrAIon framework and release validation fails on drift.

## 0.3.2 - 2026-09-23

### Changed

- Help now renders the EmbrAIon version and product name on one line: `EmbrAIon X.Y.Z — AI-First Engineering System`.

## 0.3.1 - 2026-09-23

### Added

- `embraion help` as a launcher-owned alias for the top-level command catalog.
- `embraion help <command>` and nested forms such as `embraion help cache prune` for command-specific help.

### Changed

- Top-level help is now organized into Project & setup, Health & runtime, AI execution, Engineering controls, Help, Examples, and More sections.
- Every top-level command and nested command now exposes a concise description of what it does and what it provides.
- Top-level `-h` / `--help` is launcher-owned, so the latest help catalog remains available inside projects pinned to older EmbrAIon runtimes.

## 0.3.0 - 2026-09-23

### Added

- Cross-platform compatibility CI across Linux, Windows, and macOS on Python 3.11 and 3.14.
- Network-backed end-to-end validation that a newer global launcher installs, delegates to, and reuses an exact older project-pinned EmbrAIon release.
- `embraion status` with both human-readable and `--json` output for launcher version, project pin, resolved runtime, runtime cache, and detected host projections.
- `embraion cache list` and conservative `embraion cache prune` commands for inspecting and cleaning invalid, stale, or explicitly old cached runtimes.

### Changed

- Release tag creation now waits for the cross-platform compatibility matrix before publishing a release.
- Runtime cache markers are touched when reused so optional age-based pruning can use last-use time.
- First-use pinned-runtime installation keeps pip output out of command stdout so delegated CLI output remains machine-safe and predictable.
- Human-readable diagnostic status markers use ASCII labels (`[OK]`, `[WARN]`, `[ERROR]`) for reliable Windows code-page and redirected-output compatibility.

## 0.2.2 - 2026-09-23

### Changed

- `embraion doctor` now prints a concise human-readable diagnostic report by default.
- Machine-readable structured output remains available through `embraion doctor --json`.
- The doctor exit-code contract is unchanged, so CI and automation can continue to use it safely.

## 0.2.1 - 2026-09-23

### Fixed

- `embraion doctor` no longer treats an arbitrary non-project working directory as a project root.
- Running `doctor` from a home directory or other ordinary folder now performs framework/installation diagnostics only and skips recursive security scanning, MCP inventory writes, and worktree inspection.
- Project-level diagnostics still run when the current directory is inside a Git repository or an explicit EmbrAIon project containing `.embraion/project.yaml`.

## 0.2.0 - 2026-09-23

### Added

- Project-aware CLI runtime resolver that reads the nearest `.embraion/project.yaml`, caches exact pinned releases in isolated virtual environments, and delegates ordinary commands to the pinned EmbrAIon version.
- Automatic compatibility handling for legacy `0.1.0-dev` project pins by resolving them to the published `0.1.0` distribution.
- Release preparation from a validated `release: vX.Y.Z` commit while preserving tag-only PyPI Trusted Publishing.

### Changed

- Package, framework, and CLI version declarations are aligned at `0.2.0`.
- `embraion init` and `embraion update` write the active global CLI distribution version into the project overlay.
- Installation documentation now explains one global launcher per machine plus isolated per-project pinned runtimes.
- Core concept names in localized README files link to canonical directories, and external products link to official sources.

## 0.1.0 - 2026-09-23

### Added

- First public EmbrAIon release.
- PyPI Trusted Publishing through GitHub Actions and the protected `pypi` environment.
- Standalone wheel and source distributions for installation without cloning the repository.
- Codex, GitHub Copilot, Claude Code, Portable, and source release archives.
- English, Russian, Simplified Chinese, Spanish, and Hindi README/documentation coverage.
- MIT licensing plus separate trademark and brand-assets policy.

### Changed

- Public installation uses the PyPI package through `pipx install embraion`.
