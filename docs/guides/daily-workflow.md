# Daily Workflow

EmbrAIon should make ordinary AI-assisted engineering more disciplined, **not more ceremonial**.

After setup, most days should start with the product or engineering outcome you want, not with framework administration.

![Daily AI-First workflow](../assets/diagrams/en/05-daily-workflow.svg){ loading=lazy }

## Before substantial work

```bash
embraion doctor
embraion status
```

For a repository you use every day, you do not need to run every diagnostic before every tiny edit. Use them when starting a substantial task, after an EmbrAIon update, or when project behavior looks wrong.

## Describe the task normally

Ask your AI client for the actual engineering outcome:

> Fix the retry flow and add regression coverage.

You should not need to manually select every model, agent, or validation command. The host can use the repository's projected EmbrAIon roles and skills plus the project-owned `.embraion/` contract.

For high-risk or ambiguous work, being explicit about the expected outcome or evidence is still useful. EmbrAIon reduces repeated setup; it does not replace clear requirements.

## Let the project contract guide the work

The project contract can supply:

- architecture and source-of-truth knowledge;
- protected/private path rules;
- project-specific specialists;
- optional model/deployment routing;
- validation profiles;
- substantial-review requirements.

The AI client still performs the reasoning and tool use. EmbrAIon makes the surrounding engineering rules durable.

## Change configuration only when the intent is configuration

If you say:

> Configure routing so ordinary work stays on the host default but complex architecture uses our reviewed deployment.

the host should change the relevant `.embraion/` configuration.

If you say:

> Fix the reconnect bug.

the host should use the existing project contract, not casually rewrite it.

This distinction keeps ordinary product work separate from changes to the AI-First operating model.

## During implementation

Use project knowledge as source of truth and avoid editing generated projections to express canonical project policy.

When host projection changes are needed, preview first:

```bash
embraion projection diff --host codex --destination .
```

## Validate the change

```bash
embraion validation run affected
```

If the repository has not configured an `affected` profile yet, do that first. `skipped` is not equivalent to `passed`.

## Review substantial work

Use an independent reviewer appropriate to the repository. Review should inspect correctness, regressions, policy boundaries, and validation evidence rather than merely restate the implementation.

Projects that use structured run evidence can attach validation/review records. See [Runs & Review](runs-review.md).

## Finish

Before merge or delivery, the useful questions are:

- Did the requested behavior change correctly?
- Did relevant project validation pass?
- Were protected/canonical boundaries respected?
- Was substantial work independently reviewed when required?
- Is any residual risk explicit?

If the project has CI enforcement installed, that surface can make selected gates deterministic at merge time. It remains an explicit project choice.

## After an EmbrAIon upgrade

```bash
pipx upgrade embraion
cd MyProject
embraion update
embraion doctor
embraion projection diff --host codex --destination .
```

Updating the project configuration does not silently refresh generated host projections. Review projection changes separately.
