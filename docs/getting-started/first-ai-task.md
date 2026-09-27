# Your First AI Task

Once EmbrAIon is initialized and your AI-client projection is installed, **normal engineering should feel normal**.

You describe the engineering outcome. The repository already carries the project contract.

## 1. Check project health

```bash
embraion doctor
embraion status
```

Fix configuration errors before asking the AI to make a substantial change.

## 2. Give the AI a normal task

For example:

> Add a retry action when the connection fails.

You do not have to begin every task with a long framework prompt.

The installed host projection tells the AI client about reusable EmbrAIon roles/skills and where the canonical project settings live. The host can then apply project knowledge, safety policy, routing, validation, and review requirements as appropriate.

For a new or partially adopted repository, you may still choose to be explicit:

> Add a small user-facing feature. Follow this repository's EmbrAIon project knowledge and policy, run the configured affected validation, and report residual risk.

That is useful while establishing trust in the project configuration, but it should not be required forever.

## 3. Let the host use the project contract

Depending on the AI client, the repository may contain generated EmbrAIon agents and skills. Those files translate reusable Core behavior and project-specific agents into host-native instructions.

The AI host still performs the actual reasoning and code execution.

A useful way to think about the flow is:

```text
task
 ↓
host understands EmbrAIon projections
 ↓
project knowledge + policy + optional routing
 ↓
implementation / analysis / review
 ↓
project validation
 ↓
evidence + human decision
```

## 4. Do not manually route unless you intend to

If `.embraion/routing.yaml` has no override for the task, the host keeps its own default/automatic model policy.

If your repository deliberately defines routing, the Lead/host can resolve the appropriate route class and role without you manually selecting every worker.

You only need to configure routing when the project actually wants a reusable selection policy.

## 5. Run project validation

Inspect available profiles:

```bash
embraion validation list
```

If `affected` has real commands configured:

```bash
embraion validation run affected
```

An empty profile reports `skipped`; it is not treated as evidence of a pass. Configure `.embraion/validation.yaml` before relying on validation as a gate.

## 6. Review meaningful changes

For meaningful changes, use independent review appropriate to your project. EmbrAIon can record review/evidence and can optionally enforce review through an explicitly installed CI surface, but it does not remove the human decision to merge.

## 7. Inspect the final state

Useful checks:

```bash
embraion doctor
embraion status
```

If you changed host configuration intentionally, preview projection ownership before reinstalling:

```bash
embraion projection diff --host codex --destination .
```

## What a normal task looks like

![Your first AI task](../assets/diagrams/en/08-first-ai-task.svg){ loading=lazy }

For a practical recurring routine, continue with [Daily Workflow](../guides/daily-workflow.md).
