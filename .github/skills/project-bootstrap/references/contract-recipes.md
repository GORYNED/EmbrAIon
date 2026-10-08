# Project contract recipes

Recipes for the files `embraion init` creates: knowledge, validation, agents, project identity, and the framework pin. Read the file first, change only what the request names, keep everything else. `embraion validate --strict` checks only key names; the loader commands below check the full shape, so always run them. `embraion doctor` can still report "everything looks good" for a wrong agent or validation shape.

## set-up

Whole-project request: follow the Project Bootstrap procedure in SKILL.md. It composes `bind-knowledge`, `protect-paths`, `project-validation`, `project-agents`, and `project-identity`. If the launcher or project contract is absent, the agent completes the official launcher installation (subject to required permission), `init`, and requested host projection itself before applying the recipes. If setup is partial, inspect and repair the existing contract instead of resetting it. Leave routing and every optional file alone unless the user asks for them. Finish with `embraion doctor`, `embraion validate --strict`, `embraion check`, projection verification, and a fresh host loading check when available; report each outcome as passed, failed, or not run. An unchanged second request must not alter the project.

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

## validation-guards

Fills per-command and per-profile options of `validation.yaml` `profiles`: optional commands, prerequisites, a clean-tree guard, and a log size limit. These need the structured form (`commands:` list).

- A command is a string or a mapping: `command`, `required` (default `true`), `requires` with `executables`, `env` (names only), `platforms` (`linux`, `macos`, `windows`). A missing prerequisite reports `blocked`, not `failed`; a blocked required command fails the profile, an optional one does not. A failing `required: false` command is recorded as a warning.
- `clean-tree: true` fails the profile when validation changes the working tree (a tree that was already dirty is the baseline). `output-limit-bytes` (at least 1024) keeps only the head and tail of a very large log.
- Owner decision: the request must say which commands become optional, which prerequisites to add, or that the tree must stay clean. Do not infer it. Never mark a command optional or add a prerequisite to make a failing profile pass; making checks weaker or skippable lowers validation.

```yaml
profiles:
  affected:
    commands:
      - python -m unittest discover -s tests
      - command: ./tools/lint.sh
        required: false
      - command: ./tools/extra-check.sh
        requires: {executables: [example-tool], env: [EXAMPLE_TARGET], platforms: [linux, macos]}
    clean-tree: true
    output-limit-bytes: 1048576
```

Verify: `embraion validation list`, then `embraion validation run <profile>` for a profile you confirmed is safe.

## plan-validation

Fills `validation.yaml` `areas`, `impact`, `full-reasons`, `default-area`, so a change runs only the checks that prove what it touched. Optional; without these keys nothing changes.

- Discover which folders each existing check proves (CI path filters help) and which paths are risky enough to need the whole `full` profile.
- `areas.<name>` has `paths` (globs) and `commands` (command lines) and/or `profiles` (every command of those profiles). `impact` is an ordered list of rules with `id`, `paths`, and `areas` and/or `full: <reason>`. `full-reasons` is the closed list of reasons; declaring one needs a `full` profile. `default-area` handles a path that matches nothing; without it the whole planned profile runs.
- Owner decision: a plan can make a change run fewer checks, and `default-area` decides what an unmatched path runs. Write them only when the request asks for change-based validation, and ask which paths must force the full profile and what the default area is when the request leaves them open. Never narrow a profile to make a failing check go away.

```yaml
areas:
  library:
    paths: [src/**]
    commands: [python -m unittest discover -s tests]
  docs:
    paths: [docs/**]
    profiles: [fast]
impact:
  - id: data-format
    paths: [src/schema/**]
    full: data-migration
full-reasons: [data-migration, release-gate]
default-area: library
```

Verify: `embraion validation list` (loads the full shape), then `embraion validation explain <profile> --base-ref <base>` (read-only; says why each area and command was selected). `embraion validation plan` writes a plan file; use it only when asked.

## project-agents

Fills `agents.yaml` `agents`. Prefer `agents: []`: Core roles (Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, Steward) cover most work. Add a specialist only for a stable project responsibility that no Core role covers.

- Required: `id` (kebab-case, not a Core id), `purpose`, `access` (`read-only` or `workspace-write`), `responsibilities` (list). Optional: `title`, `extends` (a non-Lead Core role; access must not widen it), `restrictions`, `triggers`, `outputs`.
- Owner decision for access: prefer `access: read-only`. Create a `workspace-write` specialist only when the request says it must write. Never `extends: lead`.

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

- Run `embraion update --check` (read-only), inspect the current pin, artifact lock,
  launcher origin, available release and existing projections. Do not move the pin
  unless the user requested an update.
- When the launcher is older than the intended release, use its observed install
  method to upgrade it yourself. Treat a machine-wide install as a shared-software
  change: obtain explicit permission if the request did not authorize it. Never
  send the user a command to copy. Verify the resulting launcher version and
  official artifact before running `embraion update`; an unknown install method
  or failed verification blocks the pin change.
- Run `embraion update` to record the exact release artifact lock. Preserve
  unrelated project values, then run `embraion install --host <host> --destination .`
  for each installed host, `embraion projection verify`, `embraion doctor`, and
  `embraion status`. Use a fresh host session to test loading when available.
  After a partial failure, inspect state and retry only the failed idempotent
  step. A repeated unchanged request makes no project or projection changes.

## hydrate-lfs-worktrees

Fills `project.yaml` `worktree.lfs`: `none` (default) or `hydrate`. With `hydrate`, `embraion worktree create` and `worktree register` fetch and verify the Git LFS content of the new worktree. Set it only for a repository that uses LFS (`.gitattributes` with `filter=lfs`). Any other value is an error. Verify: `embraion policy show` (it loads `project.yaml`; `embraion validate --strict` does not check the value).

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
