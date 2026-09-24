# Daily Workflow

EmbrAIon should make ordinary AI-assisted engineering more disciplined, not more ceremonial.

A typical day can stay simple.

## Before work

```bash
embraion doctor
embraion status
```

For a repository you use every day, you do not need to run every diagnostic before every tiny edit. Use them when starting a substantial task, after an EmbrAIon update, or when project behavior looks wrong.

## Describe the task normally

Ask your AI client for the actual engineering outcome you want.

For substantial work, it is useful to include intent such as:

> Follow the repository's EmbrAIon project knowledge and safety policy. Use relevant projected roles/skills, stay inside owned source boundaries, run affected validation, request independent review, and report residual risk.

The host performs the AI work. EmbrAIon supplies the surrounding contract.

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
