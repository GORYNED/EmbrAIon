# Your First AI Task

Once EmbrAIon is initialized and your host projection is installed, **normal engineering should feel normal**.

!!! tip "In plain English"
    You ask for the product or engineering outcome. The repository already carries the project rules.

## The day-one flow

| You do | Behind the scenes | You verify |
| --- | --- | --- |
| Ask: “Add a retry action when the connection fails.” | The host can use projected roles/skills plus project knowledge and policy | Review the code change |
| Let the host implement | Existing routing/default model policy stays in effect | Make sure protected paths were respected |
| Run project checks | EmbrAIon executes the validation profile | Confirm `passed`, not `skipped` |
| Review substantial work | Review/evidence rules apply if configured | Decide whether to merge |

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

The AI host still performs the reasoning and edits.

## 4. Validate

```bash
embraion validation list
embraion validation run affected
```

!!! warning
    `skipped` is not a pass. It means the profile has no executable commands.

## 5. Review and finish

For meaningful changes, use the repository's review policy and inspect residual risk.

If host projections were intentionally changed:

```bash
embraion projection diff --host codex --destination .
```

![Your first AI task](../assets/diagrams/en/08-first-ai-task.svg){ loading=lazy }

Next: [Daily Workflow](../guides/daily-workflow.md).
