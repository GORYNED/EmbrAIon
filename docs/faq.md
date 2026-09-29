# FAQ

Direct answers to the conceptual questions that commonly appear after the quick start.

## Do I have to mention EmbrAIon in every prompt?

No.

After the project contract and host projection are installed, ordinary work should sound like ordinary engineering:

> Add retry behavior and regression coverage.

Think about EmbrAIon again when you intentionally change project knowledge, policy, validation, routing, agents, execution, or enforcement.

## Does EmbrAIon intercept my prompts?

No.

For host-native work, you talk directly to Codex, GitHub Copilot, Claude Code, or another supported host. EmbrAIon supplies generated host-native instructions and repository-owned project rules.

The optional `embraion execute` path is separate.

## Does routing actually change the model in the AI client's UI?

Not necessarily.

By default, routing resolves to `host-default`, so the host keeps control of its current model selection.

A project can record explicit model/effort/options overrides, but EmbrAIon does not transparently take over a host UI model picker. Use `embraion route` to inspect the project routing result.

## Why are deployment and routing separate?

Because they answer different questions:

- **Deployment:** what reusable concrete choice exists?
- **Routing:** when should a route or role select it?

For provider-neutral execution there is a third question:

- **Execution binding:** how may that deployment be invoked safely?

See the [Glossary](glossary.md) or [Engineering Model Deep Dive](reference/engineering-model.md).

## Do I need `.embraion/execution.yaml`?

Usually no.

You need it only when the project opts into the provider-neutral `embraion execute` path. Ordinary Codex/Copilot/Claude work does not require it.

## Are generated host files the source of truth?

No.

The canonical project contract lives in project-owned EmbrAIon configuration/knowledge. Generated host files are projections of that contract.

If a generated file drifts, use projection diff/verify and reinstall intentionally rather than maintaining a second policy copy by hand.

## Does a protected path mean the AI physically cannot edit it?

Not by text guidance alone.

Host projections tell the AI what it should respect. Deterministic protection comes from validation/enforcement and, where applicable, host/repository controls.

That distinction is intentional: **guidance is not enforcement**.

## Is `skipped` validation a pass?

No.

`skipped` means the profile has no executable commands. Configure real validation before relying on it as evidence or a merge gate.

## Do I need to configure every `.embraion/` file?

No.

Start with three questions:

1. What should the AI know? → `knowledge.yaml`
2. What should it respect? → `policy.yaml`
3. What proves the change works? → `validation.yaml`

Leave deployments, routing, execution, pricing, custom agents, and enforcement at their defaults until the project needs them.

## Can one repository use more than one AI host?

Yes.

A project can install multiple projections while keeping one canonical project contract.

## Does EmbrAIon run inside my finished application?

No.

EmbrAIon is an engineering layer around the repository. Your finished Python, Unity, web, or other application does not need EmbrAIon as an application runtime dependency.

## Does provider-neutral mean every provider or local model is supported automatically?

No.

Provider-neutral means Core does not hard-code one provider/model catalog. Concrete provider/model support still depends on a host or an intentionally configured and validated execution adapter/binding.

See [Security & Data Flow](security-data-flow.md) for the local-model/data-boundary implications.

## Can I use EmbrAIon in CI?

Yes.

Project validation and projection verification are CLI-friendly. EmbrAIon can also explicitly install a GitHub Actions enforcement surface:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

Installing the workflow does not silently make the status check required; repository branch/ruleset administration remains an explicit decision.

## Do I need to tell Lead which agents to use?

No. Lead selects the smallest useful specialist set according to scope, ownership, risk, and project policy. Trivial work can stay with Lead; substantial work receives proportional delegation and independent review.

## What does `agents: []` mean?

No additional project specialists. Core Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward remain available.

## Do I have to configure routing?

No. Routing is optional, including during Bootstrap. `overrides: {}` is a valid result.

## What happens with empty routing?

Resolution uses `host-default`: host defaults or inheritance select the model and effort. Orchestration and delegation continue; EmbrAIon does not invent a model mapping.

## How do I configure routing?

Ask:

> Configure EmbrAIon routing for this repository using the models and reasoning settings actually available to this host. Keep host-default where explicit routing adds no value, preserve project safety policy, and verify the resulting routes.

Lead uses the `routing-configuration` skill, stores reusable choices in `.embraion/deployments.yaml`, route/role/task-class selection in `.embraion/routing.yaml`, and verifies the result. See [Routing](model-routing.md).

## Can Lead use different models for different subagents?

Yes, where the active native host surface supports and can verify the resolved settings. Each assignment is classified and resolved independently. Role != Route != Model. Supported mechanisms differ between Codex, Copilot CLI/VS Code/cloud, and Claude Code; see [Hosts](hosts/index.md).

## What if the host cannot apply an explicit model or effort?

Lead reports a capability limitation before dispatch. It must not silently inherit, substitute, cap, or claim the setting was applied. A supported handoff needs verified effective settings and fresh privacy/access checks when changing hosts. Preparing a route or definition is not execution evidence.

## What does “Configure EmbrAIon for this project” do?

It loads the canonical Core [Project Bootstrap](configuration/bootstrap.md) procedure: inspect the repository and existing configuration, bind useful knowledge, preserve policy, discover real validation, decide whether project agents are needed, keep routing optional, and verify/report the result.

## Will Bootstrap invent architecture or documentation?

No. It reuses authoritative documents. A missing canonical document can be created only for an actual concern, with sufficient verified repository evidence and material future value. Otherwise the slot stays unbound and the limitation is reported.

## Will Bootstrap overwrite existing project settings?

It preserves valid knowledge, intentional custom settings, stricter policy, project agents, and existing routing unless tuning is requested. Changes need repository evidence. Generated host output remains derived and is regenerated through official mechanisms with ownership checks.

## What validation gets created?

Actual commands found in repository workflow and CI: cheap frequent `fast`, sufficient normal-change `affected`, and broad local `full`. No invented commands. Empty profiles remain `skipped`; unavailable tooling or external CI is reported as a limitation.

## Can I rerun Bootstrap later?

Yes. Rerun after repository workflow or architecture changes. It should converge safely without duplicate entries, documents, or agents, and update only what new evidence justifies.

## Does Bootstrap install external dependencies?

It does not silently install dependencies or tooling just to make validation green. Established repository setup may be followed within authorization; missing infrastructure and any required provisioning decision are reported.

## What remains manual?

Decisions that require user authority or unavailable evidence: host trust/settings, unverified model selectors, ambiguous ownership, credentials/integrations, provisioning outside established workflow, and repository enforcement rules. Bootstrap reports these boundaries. You review the configuration diff and evidence.

## What should I read next?

- New to the system: [EmbrAIon in 60 Seconds](getting-started/in-60-seconds.md)
- Unfamiliar term: [Glossary](glossary.md)
- Security/privacy question: [Security & Data Flow](security-data-flow.md)
- Configuration problem: [Troubleshooting](guides/troubleshooting.md)
- Precise architecture: [Engineering Model Deep Dive](reference/engineering-model.md)
