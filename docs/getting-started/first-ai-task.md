# Your First AI Task

Once EmbrAIon is initialized and your host projection is installed, **normal engineering should feel normal**.

!!! tip "In plain English"
    You ask for the product or engineering outcome. The repository already carries the project rules.

## Configure the contract first

After `embraion init` and host projection installation, ask:

> Configure EmbrAIon for this project.

[Project Bootstrap](../configuration/bootstrap.md) discovers existing truth and real checks while preserving project decisions. Then use ordinary engineering requests.

## The day-one flow

| You do | Behind the scenes | You verify |
| --- | --- | --- |
| Ask: “Add a retry action when the connection fails.” | Lead applies project rules and selects useful roles without another delegation prompt | Review the code change |
| Let the host implement | Existing routing/default model policy stays in effect | Make sure protected paths were respected |
| Run project checks | EmbrAIon executes the validation profile | Confirm `passed`, not `skipped` |
| Review substantial work | Lead obtains independent read-only review when Core or stricter project policy requires it | Decide whether to merge |

## 1. Check project health

```bash
embraion doctor
embraion status
```

For a small task in a repository you already trust, you do not need to run diagnostics before every edit.

## 2. Ask for the outcome

After setup, prefer the normal engineering request:

> Add a retry action when the connection fails and add regression coverage.

Avoid framework-heavy prompts like:

> Use EmbrAIon, load the right agent, choose the model, read these files, run these checks, and then implement retry behavior.

That setup should already belong to the repository.

**After installation, you should barely think about EmbrAIon during ordinary product work.** Think about EmbrAIon again when you intentionally change the project contract itself — knowledge, policy, validation, routing, agents, or enforcement.

## 3. What happens behind the scenes

```text
your task
  ↓
AI host
  ↓
generated EmbrAIon host files
  +
project knowledge / policy / optional routing
  ↓
implementation
```

The AI host still performs the reasoning and edits. In Codex, the `config` projection places Lead guidance in root `developer_instructions`, so you can use ordinary language without naming roles. Lead handles trivial work directly; for larger work it proactively selects only roles that add value: Analyst for requirements, Architect for boundaries, Researcher for uncertain facts, Worker for bounded implementation, Validator for checks, Reviewer for independent review, and Steward for compatibility and persistence.

Each delegated assignment has bounded scope, ownership, acceptance criteria, and expected evidence. Lead may parallelize read-only discovery and independent writes; overlapping files, shared contracts, and dependencies require serialization or explicit isolation. Lead classifies and resolves routing for each assignment before native spawn, integrates specialist results, and retains final acceptance authority. Empty project `agents: []` preserves Core roles.

This guidance depends on trusted host configuration, supported native capabilities, permissions, and higher-priority instructions. It does not make orchestration deterministic; validation and review still need real evidence. See [Codex](../hosts/codex.md) for projection and merge ownership details.

All supported host projections also carry the canonical `orchestration` skill with the generated Core Lead contract. Codex, Copilot, Claude Code, and Portable share this guidance, while each host controls skill loading. Codex's root instructions provide an additional entry point without requiring skill selection.

## 4. Validate

```bash
embraion validation list
embraion validation run affected
```

!!! warning
    `skipped` is not a pass. It means the profile has no executable commands.

## 5. Review and finish

For meaningful changes, collect fresh proportional checks and inspect residual risk. Substantial implementation requires independent read-only Reviewer evaluation when Core or stricter project policy requires it; the implementation owner cannot provide its own independent approval. Lead resolves findings, refreshes validation after fixes, and requests fresh review when the changes invalidate prior review evidence. Missing, skipped, historical, or unavailable checks are not a fresh pass.

If host projections were intentionally changed:

```bash
embraion projection diff --host codex --destination .
```

![Your first AI task](../assets/diagrams/en/08-first-ai-task.svg){ loading=lazy }

Next: [Daily Workflow](../guides/daily-workflow.md).
