# Daily Workflow

EmbrAIon should make AI-assisted engineering more disciplined, **not more ceremonial**.

!!! tip "In plain English"
    Most days you should talk about the product, not the framework.

## A normal day

| Step | What you do | What EmbrAIon contributes |
| --- | --- | --- |
| 1 | Ask for the engineering outcome | Project knowledge, policy, roles, and optional routing are already attached to the repo |
| 2 | Let the host implement | Host-native AI does the reasoning/tools |
| 3 | Run affected validation | Real project commands produce evidence |
| 4 | Review substantial work | Project review policy/evidence applies |
| 5 | Merge/deliver | Optional enforcement can make selected gates deterministic |

Example:

> Fix the retry flow and add regression coverage.

That should normally be enough.

## Before substantial or suspicious work

```bash
embraion doctor
embraion status
```

Use diagnostics after framework updates, before substantial work, or when project behavior looks wrong — not as ceremony before every tiny change.

## Behind the scenes

![Daily AI-First workflow](../assets/diagrams/en/05-daily-workflow.svg){ loading=lazy }

The project contract can supply architecture knowledge, protected/private path rules, project-specific specialists, optional model/deployment routing, validation profiles, and review requirements.

## Configuration changes are different from product work

This changes the AI-engineering system:

> Configure routing so complex architecture uses our reviewed deployment.

This does not:

> Fix the reconnect bug.

For ordinary product work, the host should use the existing project contract rather than casually rewriting it.

## Validate

```bash
embraion validation run affected
```

If the profile is empty, configure it first. `skipped` is not equivalent to `passed`.

## Review and finish

Ask:

- Did the requested behavior change correctly?
- Did relevant validation pass?
- Were protected/canonical boundaries respected?
- Was substantial work independently reviewed when required?
- Is residual risk explicit?

If CI enforcement is installed, it can make selected gates deterministic at merge time.

## After an EmbrAIon upgrade

```bash
pipx upgrade embraion
cd MyProject
embraion update
embraion doctor
embraion projection diff --host codex --destination .
```

Updating project configuration does not silently rewrite host projections.
