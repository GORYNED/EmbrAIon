# Validation Configuration

`.embraion/validation.yaml` declares the **configuration** for commands that provide real project evidence. This page explains how to define profiles; [Validation & Evidence](../validation.md) explains what happens when they run and how evidence is used.

Simple profiles remain valid and backwards compatible:

```yaml
profiles:
  fast:
    - python -m unittest discover -s tests/unit -p "test_*.py"
  affected:
    - python -m unittest discover -s tests -p "test_*.py"
  full:
    - python -m unittest discover -s tests -p "test_*.py"
    - python -m compileall src
```

An empty profile is valid configuration, but running it produces `skipped` — not a false pass. Commands execute sequentially from the repository root.

## Runtime parameters

A profile can use the structured form when the project needs values that are only known at execution time:

```yaml
profiles:
  affected:
    commands:
      - pwsh -NoLogo -NoProfile -File tools/validation/validate.ps1 affected
    parameters:
      base-ref:
        argument: --BaseRef
        default: main
      head-ref:
        argument: --HeadRef
        default: HEAD

  full:
    commands:
      - pwsh -NoLogo -NoProfile -File tools/validation/validate.ps1 full
    parameters:
      justification:
        environment: PROJECT_FULL_JUSTIFICATION
        required: true
```

Supply declared values with repeatable `--param NAME=VALUE` options:

```bash
embraion validation run affected \
  --param base-ref=origin/main \
  --param head-ref=HEAD

embraion validation run full \
  --param justification=persistence-migration
```

A parameter targets either one command-line argument or one child-process environment variable. Optional `commands` uses one-based command indexes to restrict a parameter to selected commands:

```yaml
parameters:
  test-filter:
    argument: --filter
    commands: [1]
```

Values passed as command-line arguments are shell-quoted for the current platform. On Windows, argument values containing `cmd.exe` metacharacters are rejected instead of being interpolated into a shell command; use an environment parameter when such a value is required. Environment parameters are added only to the child validation process. Unknown parameters, missing required values, invalid command indexes, unsafe Windows argument values, and malformed configuration fail closed.

Structured validation evidence records which parameter names were used, but never persists their raw values or the expanded command containing them. Known runtime parameter values are also scrubbed from captured child stdout/stderr in addition to normal EmbrAIon redaction. Do not use validation parameters as a substitute for a secret manager.

## Timeouts

A structured profile can bound each command with the optional `timeout-seconds` key. A number applies to every command of the profile; a list gives one value per command, in order, and `null` leaves that command unbounded:

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
      - python tools/package.py
    timeout-seconds: [1800, null]
```

Without the key, commands run without a timeout, as before. `--timeout SECONDS` on the command line overrides the configured value for every command of that run. A list whose length differs from the command count, or a value that is not a positive number, fails closed.

## Optional commands and prerequisites

A command can stay a plain string. It can also be a mapping, in the same `commands` list or in a simple profile list:

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
      - command: ./tools/lint.sh
        required: false
      - command: ./tools/extra-check.sh
        requires:
          executables: [example-tool]
          env: [EXAMPLE_TARGET]
          platforms: [linux, macos]
```

- `required` is optional and defaults to `true`.
- `requires` is optional. `executables` are looked up on `PATH` (a name with a path separator is resolved from the project root), `env` names must be set and not empty in the command environment, and `platforms` is a list of `linux`, `macos`, or `windows`.

A command whose prerequisite is missing is not started. It is reported as `blocked` with a reason, not as `failed`. A blocked required command makes the profile fail. A blocked optional command does not.

A command with `required: false` still runs, and its failure or timeout is recorded in the evidence. It does not fail the profile. The profile stays `passed` if at least one command passed, and the record gets a `warnings` count. If every command is optional and none passed, the profile is `skipped` with a `skip-reason`, not `passed`, because nothing was proved. A command that was never given `required` or `requires` behaves exactly as before. Unknown keys, a non-boolean `required`, an unknown platform, or an empty name fail closed.

## Clean-tree guard

A structured profile can require that validation does not change the working tree:

```yaml
profiles:
  gate:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
    clean-tree: true
```

Without the key, nothing is checked, as before. With `clean-tree: true`, EmbrAIon reads `git status --porcelain=v1 -z --untracked-files=all` before the first command and again after the last one, and compares the two.

- A tree that was already dirty is allowed. Its state is the baseline, and only new differences fail. A file that was already modified and is edited again counts as a difference, because the content is compared too.
- The `.embraion/state/` directory is ignored, because validation writes its own evidence there.
- A failure names up to 20 changed paths and the profile fails with a `failure-reasons` entry that starts with `clean-tree guard failed`.
- Outside a Git work tree, with a locked index, or when `git` cannot establish the tree state, the guard is `blocked` and the profile fails before starting commands. The reason also says so when Git refuses the directory (for example, because of its ownership) and gives Git's first message line.
- The guard also compares the exact HEAD before and after the run. A changed HEAD fails even when the file snapshot is unchanged.
- A file larger than 64 MiB is compared by its size only, not by its content.

The record gets a `clean-tree` object with `status` (`passed`, `failed`, or `blocked`), `baseline-dirty`, `changed-count`, and `changed-paths`. A profile without commands is `skipped` and is not checked.

Validation starts each command inside a process container. On Windows the target is held until a kill-on-close Job Object is assigned; on POSIX it starts in a new process group. A timeout, a root that exits with live members of that container, failed containment, or output streams that do not close produce failure evidence. If termination or output drain cannot be confirmed, later commands do not start, including when the affected command is optional. POSIX commands must keep their children in the assigned process group: a child that deliberately starts a new session (or daemonizes) leaves that group and cannot be detected or terminated by this mechanism. The Windows Job Object contains such children unless they are explicitly allowed to break away; EmbrAIon does not grant breakaway permission.

## Output limit

By default each command's full redacted output is kept in its log, and the record keeps a tail of at most 8000 characters per stream. A very large output can make the log huge. A structured profile can bound it with `output-limit-bytes` (an integer of at least 1024):

```yaml
profiles:
  full:
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
    output-limit-bytes: 1048576
```

When a stream is larger than the limit, EmbrAIon keeps only the first and the last half of the limit, cut on line boundaries, and puts a marker between them in the log:

```text
[... output truncated: 9400000 bytes (210000 lines) omitted; total 9500000 bytes, 211000 lines ...]
```

Only the kept parts are read into memory. Each part is redacted on its own. A private key block that the cut would split is dropped from the kept part, so half a key never reaches the log. Without the key, the log is not cut.

In both cases, when a stream is longer than the record tail, the command row gets `stdout-head` or `stderr-head` (the first 8000 characters) and an `output` object with the `bytes` and `lines` totals per stream and `log-truncated`. Short output adds no fields. The record shows `output-limit-bytes` when the profile sets it.

## Validation plan

A project can describe which checks prove which part of the code. This is optional. A project without these keys behaves exactly as before.

```yaml
profiles:
  affected:
    - python -m unittest discover -s tests -p "test_*.py"
  full:
    - python -m compileall src
    - python -m unittest discover -s tests -p "test_*.py"
    - python tools/package.py

areas:
  library:
    paths: [src/**]
    commands:
      - python -m unittest discover -s tests -p "test_*.py"
  docs:
    paths: [docs/**, "*.md"]
    commands:
      - python tools/check-links.py
  packaging:
    paths: [tools/package.py]
    profiles: [full]

impact:
  - id: data-format
    paths: [src/schema/**]
    areas: [docs]
    full: data-migration

full-reasons: [data-migration, release-gate]
default-area: library
```

Keys:

- `areas` maps an area name to `paths` (globs) and to the proof: `commands` (command lines) and/or `profiles` (every command of those profiles). At least one proof is required.
- `impact` is an ordered list of rules. Each rule has an `id`, `paths` (globs), and `areas` and/or `full`. Every rule that matches a changed path applies, in the order written. `full` names a reason from `full-reasons` and escalates the plan to the `full` profile. If several rules escalate, the first one in the list names the reason.
- `full-reasons` is a closed list of reason ids. A rule or a `--full-justification` value outside the list is an error. Declaring a reason or a `full` rule requires a `full` profile.
- `default-area` is optional. A changed path that matches no area and no rule selects this area. Without it, such a path selects the whole planned profile, so the project checks more instead of less.

Globs use the same matcher as the source policy in `policy.yaml`. A glob that is empty, absolute, contains `..`, has an unbalanced bracket, or is too complex is an error. An unknown area, profile, or reason is an error. Shape errors fail against the schema.

Compute and read a plan:

```bash
embraion validation plan affected --base-ref origin/main
embraion validation explain affected --base-ref origin/main --include-worktree
```

`plan` writes a deterministic `plan.json` (default `.embraion/state/validation/plan.json`, or `--output FILE`). `explain` prints why each area and command was or was not selected and writes nothing. Changed paths come from Git: the diff between the merge base of `--base-ref` and `--head-ref` (default `HEAD`). `--include-worktree` adds staged, unstaged, and untracked files that Git does not ignore. Files under `.embraion/state/` are ignored. `--head-ref` cannot be combined with `--include-worktree`, because local changes are compared with `HEAD`; the command fails with exit code 2. Stored plan files are redacted like the run evidence.

The plan file has `schema-version: 1` and these fields: `profile`, `config-digest`, `inputs` (refs and resolved SHAs), `changed-paths`, `matched-rules`, `selected-areas`, `skipped-areas` (with reasons), `escalation`, `fallback`, `selected-commands` (with their sources), `skipped-commands`, `status` (`selected` or `skipped`), and `skip-reason`.

Run with a plan:

```bash
embraion validation run affected --base-ref origin/main
embraion validation run affected --plan .embraion/state/validation/plan.json
embraion validation run full --base-ref origin/main --full-justification release-gate
```

- `validation run <profile>` without `--base-ref`, `--include-worktree`, or `--plan` runs every command of the profile, as before.
- A plan selects commands from areas, from the area `profiles`, and, on escalation or fallback, from the whole profile. Duplicates run once.
- A plan that selects nothing, for example because nothing changed, ends as `skipped` with its reason. It is never a pass.
- `--plan` accepts only a plan for the same profile that matches the current configuration. The complete selection and its provenance are recomputed from the recorded Git inputs; removing required commands, adding commands from unselected areas, or altering escalation is rejected. The base and head refs must still resolve to the recorded SHAs, and for a plan made with `--include-worktree` the set of changed files must be the same. Otherwise the run fails closed and asks you to compute the plan again.
- Every command keeps the run settings of the place it was selected from. A command from a profile uses that profile's `required`, `requires`, timeout, and parameters; the planned profile comes first when several profiles list the same command. A command from an area's `commands` is always required and has no prerequisites, timeout, or parameters.
- A parameter applies only to the commands of the profile that declares it. If a plan runs commands of another profile (for example `full` after an escalation) that has a required parameter without a default, pass it with `--param`, or the run fails closed. `--full-justification` does not fill parameters. Two profiles in one plan must declare a parameter of the same name identically.
- An escalation also applies the `clean-tree` guard of the profiles it runs, and the smallest `output-limit-bytes` among them.
- The run evidence contains the plan (`plan`) and a copy at `.embraion/state/validation/<evidence-id>/plan.json` (`plan-path`).
- Plan options on a project without `areas` are an error.

`validation list` also lists the areas when they exist.

## Choosing profiles

A useful convention:

- `fast` — inexpensive checks for rapid feedback;
- `affected` — checks appropriate for the current change;
- `full` — the broad project gate before high-risk delivery or release.

The schema also permits additional named profiles.

## Run validation

```bash
embraion validation list
embraion validation run fast
embraion validation run affected
embraion validation run full
```

Useful options:

```bash
embraion validation run affected --json
embraion validation run affected --fail-fast
embraion validation run affected --timeout 120
embraion validation run full --run-id task-001
```

Each execution persists redacted structured evidence under `.embraion/state/validation/`, plus one full redacted log per command under `.embraion/state/validation/<evidence-id>/`. See [Validation & Evidence](../validation.md#evidence-behavior).

## Safety

Validation commands are executable project configuration. Keep them deterministic and repository-local where practical, review changes to them like code, and do not put secrets directly in command strings.

Malformed `validation.yaml` fails closed against the project schema.

For evidence and execution semantics, continue with [Validation & Evidence](../validation.md).
