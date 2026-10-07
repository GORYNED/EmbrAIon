# Project contract recipes

Recipes for the files `embraion init` creates: knowledge, validation, agents, project identity, and the framework pin. Read the file first, change only what the request names, keep everything else. `embraion validate --strict` checks only key names; the loader commands below check the full shape, so always run them. `embraion doctor` can still report "everything looks good" for a wrong agent or validation shape.

## set-up

Whole-project request: follow the Project Bootstrap procedure in SKILL.md. It composes `bind-knowledge`, `protect-paths`, `project-validation`, `project-agents`, and `project-identity`. Leave routing and every optional file alone unless the user asks for them. Finish with `embraion doctor`, `embraion validate --strict`, and `embraion check`; report each outcome as passed, failed, or not run.

## bind-knowledge

Fills `knowledge.yaml` `slots.*` and custom entries. A slot is `null` (unbound), a path string, or an object.

- Slots: `constitution`, `architecture`, `source-authority`, `compatibility`, `persistence`, `engineering-workflow`, `specification`, `decisions` (a folder; see the decisions recipe), `deferred-tasks`.
- Discover: read the candidate document and confirm it governs that concern. A file name alone is not proof. Paths must exist inside the repository.
- Ask only when two documents compete for one slot.
- Never copy document text into YAML. Leave a slot `null` when no authoritative source exists.
- A custom entry is any other top-level key. Object fields: `path` (required), `data-class` (`PUBLIC`, `PRIVATE`, `CONFIDENTIAL`), `trust` (`project`, `external`, `generated`), `roles`, `triggers`. Use the object form when roles or triggers improve context selection. `roles` must name Core roles or declared agents.

```yaml
slots:
  architecture: docs/architecture.md
  persistence:
    path: docs/persistence.md
    data-class: PRIVATE
product-glossary:
  path: docs/glossary.md
  roles: [architect, lead]
  triggers: [terminology]
```

Verify: `embraion context slots`, then `embraion validate --strict` (it warns about missing paths and unknown roles).

## project-validation

Fills `validation.yaml` `profiles`. Names `fast`, `affected`, `full` are the convention; other names are allowed. A profile is a list of shell commands, or a structured object.

- Discover real commands from CI workflows, package scripts, task runners, and development docs. Check that each script exists and where it must run. Never invent a command; never copy release, publish, deploy, or install steps.
- Ask only whether a slow, networked, or side-effecting command may run on the user's machine.
- Commands run in order from the repository root. An empty profile is reported as `skipped`, never as a pass.
- Structured form, for runtime parameters or timeouts:

```yaml
profiles:
  fast:
    - python -m unittest discover -s tests
  affected:
    commands:
      - ./tools/validate.sh affected
    parameters:
      base-ref: {argument: --base-ref, default: main}
    timeout-seconds: 600
  full: []
```

Verify: `embraion validation list` (loads the full shape), then `embraion validation run <profile>` for a profile you confirmed is safe. Report the real outcome. Never claim a command you did not run.

## project-agents

Fills `agents.yaml` `agents`. Prefer `agents: []`: Core roles (Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, Steward) cover most work. Add a specialist only for a stable project responsibility that no Core role covers.

- Required: `id` (kebab-case, not a Core id), `purpose`, `access` (`read-only` or `workspace-write`), `responsibilities` (list). Optional: `title`, `extends` (a non-Lead Core role; access must not widen it), `restrictions`, `triggers`, `outputs`.
- Prefer `access: read-only`. Never `extends: lead`.

```yaml
agents:
  - id: api-reviewer
    title: API Reviewer
    extends: reviewer
    purpose: Review public API changes.
    access: read-only
    responsibilities:
      - check public API compatibility
    triggers:
      - api change
```

Verify: `embraion projection diff --host <host> --destination .` (the first command that loads this file), then `embraion install --host <host> --destination .` for each installed host from `embraion status`. Without install the specialist does not exist in the host.

## project-identity

Fills `project.yaml` `project.name` and the open `capabilities` mapping. `capabilities` is project metadata only; it selects no model and bypasses no policy. Keep `framework` untouched. Verify: `embraion status`, `embraion validate --strict`.

## update-framework

Fills `project.yaml` `framework.repository`, `framework.version`, `framework.artifact`. Never edit them by hand: the artifact lock must match the release.

- Run `embraion update --check` (read-only) and report the result.
- Move the pin only when the user asks to: `embraion update`. It needs a launcher at the target version. When the launcher is older, tell the user to upgrade it; installing software is their decision.
- Afterwards run `embraion install --host <host> --destination .` for each installed host, then `embraion doctor` and `embraion status`.

## task-housekeeping

Fills `project.yaml` `housekeeping`: `on-task-start` (default `false`), `local-branches` (default `true`), `remote-branches` (default `false`), `worktrees` (default `true`), `preserve-branches` (list of branch names or patterns). Switches must be booleans.

- It removes only branches and worktrees the agent created itself, and only those that pass the completion and integration gates. Ownership is never inferred from names. Turning on `remote-branches` deletes remote branches: owner decision, ask first.
- Ask which branches to preserve when the request does not name them.

```yaml
housekeeping:
  on-task-start: true
  local-branches: true
  remote-branches: false
  worktrees: true
  preserve-branches: [main, "release/*"]
```

Verify: `embraion worktree gc` (a dry run that loads the section and lists what it would preserve or remove). Do not pass `--apply` unless the user asks.
