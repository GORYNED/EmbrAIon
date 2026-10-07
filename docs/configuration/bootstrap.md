# Project Bootstrap

Ask your agent:

> Configure EmbrAIon for this project.

Lead loads the canonical Core `project-bootstrap` skill. This reusable procedure is projected to Codex, GitHub Copilot, Claude Code, and Portable. It is an AI-host procedure, not a new CLI command or a promise that static files execute onboarding automatically. Host trust, permissions, skill loading, and native capabilities still apply. Portable carries the procedure for a consuming integration; it cannot run an AI session itself.

When the skill is already available, the agent can perform launcher setup, `init`,
and host projection installation for a new repository. It checks an existing or
partial installation first and preserves unrelated configuration. If the host has
not loaded this skill, it must discover the official installation instructions;
that discovery and a fresh host session are separate from file verification.
The agent asks for permission only where a shared machine installation needs it,
then executes the commands itself.

## Discover before changing

Bootstrap inspects the repository and existing `.embraion/**` first: README and contributor instructions, architecture and decision records, source authority, compatibility and persistence contracts, specifications, CI, package manifests, build/test/lint scripts, generated and vendor paths, public APIs, serialization, and release workflow. A missing document does not prove that its concern is absent.

Existing project decisions remain authoritative. Bootstrap preserves valid entries, intentional custom settings, stricter policy, project agents, and existing routing unless tuning is requested. It makes the smallest changes supported by evidence and reports unresolved ambiguity rather than replacing a decision by guesswork.

## What gets configured

| Concern | Bootstrap result |
| --- | --- |
| Knowledge | Bind existing authoritative documents to Project Contract Slots; add extra knowledge only when useful for context selection |
| Policy | Identify canonical, protected, generated, and external paths; preserve privacy, review requirements, and enforcement intent |
| Validation | Discover actual repository/CI commands and configure useful `fast`, `affected`, and `full` profiles |
| Project agents | Prefer `agents: []` when Core roles suffice; preserve existing specialists and add only stable project responsibilities with bounded access |
| Routing | Preserve host-default or existing choices; tune only when explicitly requested |
| Host projections | Inspect consistency and regenerate through official install/update mechanisms when justified |

Knowledge slots are `constitution`, `architecture`, `source-authority`, `compatibility`, `persistence`, `engineering-workflow`, `specification`, and `deferred-tasks`. YAML references documents rather than copying their content. Optional slots without an authoritative source remain null or unbound.

Bootstrap may create a missing canonical document only when the concern actually exists, repository evidence is sufficient, and the document materially improves future engineering. It derives facts from verified code, structure, CI, and contracts. Insufficient evidence means an unbound slot and a reported limitation, not invented architecture, lifecycle, compatibility, or persistence facts.

Policy follows actual ownership. First-party code remains first-party despite unusual layout. A file's importance alone does not make it protected. Unknown classification fails closed; canonical data classes remain `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`. Deterministic enforcement is not enabled merely to finish setup.

## Real validation

Bootstrap reads CI workflows and supported project tooling before choosing commands:

- `fast`: inexpensive feedback suitable for frequent use;
- `affected`: sufficient correctness checks for ordinary changes;
- `full`: the broad local delivery/release gate, with external or multi-platform CI limitations reported separately.

It does not invent commands or silently install dependencies just to obtain a green check. Existing cheap checks should replace empty defaults. An empty profile remains `skipped`, never `passed`. Before execution, commands are checked against repository workflow and permissions; unsafe or unavailable checks are reported as limitations. External CI success is not claimed from a local command.

## Optional routing

The minimal prompt does not ask for model tuning. `overrides: {}` is a complete valid routing result: Lead orchestration and delegation still work using host-default selection.

For deliberate tuning, ask:

> Configure EmbrAIon completely for this project, including routing using the models and reasoning settings actually available to my AI host.

Lead inspects confirmed host-native selectors, efforts, options, and surface capabilities where available. Reusable concrete choices belong in `.embraion/deployments.yaml`; role, route, and task-class selection belongs in `.embraion/routing.yaml`. Role != Route != Model. No choice changes access, privacy, ownership, review, or validation requirements. If availability or application cannot be verified, Lead preserves existing choices and reports the capability limitation. See [Routing](../model-routing.md) and the [host pages](../hosts/index.md).

For routing alone:

> Configure EmbrAIon routing for this repository using the models and reasoning settings actually available to this host. Keep host-default where explicit routing adds no value, preserve project safety policy, and verify the resulting routes.

An advanced request can add concrete constraints without replacing the short normal prompt:

> Configure EmbrAIon for this project. Reuse existing authoritative documents, preserve all intentional settings and stricter policy, discover real CI checks, keep fast inexpensive, report unavailable checks, leave optional routing on host-default, and show the resulting diff and verification evidence.

## Optional deterministic planning

The Core skill owns semantic discovery, documentation decisions, routing tuning, and verification. An advanced optional helper can collect candidates without executing repository commands:

```bash
embraion bootstrap plan --output .embraion/state/bootstrap-plan.json
```

Review the plan and original sources for authority, command safety, local CI context, and cost. The helper recognizes only a limited set of document names and command forms; it is not a complete repository analyzer. It never authors documentation, configures models, installs dependencies, or runs validation. It fills unbound slots and empty profiles and can populate an empty canonical source list conservatively; populated settings, routing, agents, privacy, review, and enforcement are preserved.

Apply only an unchanged, reviewed plan:

```bash
embraion bootstrap apply --plan .embraion/state/bootstrap-plan.json
```

Apply validates schemas and rejects modified plans, stale source/configuration evidence, changed discovery, and mismatched project roots. Store plans under local `.embraion/state/` or outside the repository. If candidates need semantic correction, make bounded evidence-backed configuration changes and generate/review a fresh plan; do not edit the JSON to bypass checks. Helper application is not verification: Lead still runs applicable diagnostics and real validation.

## Verify and report

Bootstrap performs proportional verification after configuration, using applicable official commands:

```bash
embraion doctor
embraion status
embraion context slots
embraion policy show
embraion validation list
embraion route --validate
embraion route --audit-authority
embraion projection diff --host codex --destination .
```

Use the installed host and destination for projection checks, including selected components/config mode for partial adoption. Run real configured validation profiles where safe and appropriate. Inspect generated output before regeneration; do not manually edit it or resolve ownership conflicts with an automatic `--force`.

The report identifies bound knowledge, policy and validation changes, the agents and routing decisions, files/documents changed, checks actually run, skips, infrastructure limitations, and unresolved ambiguity. Review the canonical diff and evidence before relying on the configuration.

## Rerun and ordinary work

Rerun the same prompt after repository workflow or architecture changes. Bootstrap should converge safely without duplicate knowledge, docs, agents, or oscillating classifications. It updates only what new evidence justifies.

Then work normally:

> Fix the retry flow and add regression coverage.

You do not need to mention EmbrAIon or choose roles for every task. Lead reads the contract, delegates proportionally, classifies each assignment independently, resolves routing, verifies native application when configured, collects validation/review, and retains final authority.

Manual decisions remain where evidence or authorization is needed: unavailable host selectors, ambiguous ownership/authority, credentials and external integrations, dependency provisioning outside established workflow, host trust/settings, and repository rules for enforcement. Bootstrap surfaces these boundaries instead of inventing facts or silently expanding access.
