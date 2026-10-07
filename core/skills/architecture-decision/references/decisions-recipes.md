# Decision-record configuration

How to turn a request such as "require a decision record for dependency changes" into project configuration. The skill body says how to write a record; this file says how to make the project enforce one. `embraion validate --strict` checks only key names, so always run the loader command below.

## bind-decisions

Fills `.embraion/decisions.yaml` (`index`, `template`, `triggers`) and the `decisions` slot of `.embraion/knowledge.yaml`.

Steps:

1. Find the project's decision records. If a folder with records exists, bind it: `slots.decisions: <folder>` in `knowledge.yaml` (a folder, not a file). Never create a second folder. If none exists and the user wants records, run `embraion adr new "<title>"` for the first real decision: it creates the folder `docs/architecture/decisions/`, the template, the index, and the record. Do not create an empty scaffold with no decision to record. When the default folder is used, the slot can stay unbound.
2. Create `.embraion/decisions.yaml`. The check is off until the file exists. An empty file turns it on with one default trigger: a package manifest added or deleted (`package.json`, `*.asmdef`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.csproj`). Changed manifests are not a default trigger because most are routine updates.
3. Translate the request into `triggers`. A trigger fires for a changed file when its path matches `paths` (repository-relative globs; a whole `**/` segment matches zero folders), the kind of change is in `changes` (`added`, `deleted`, `modified`, `renamed`; all four when omitted), and, when `patterns` is given, an added or removed line matches one of the regular expressions. `triggers` replaces the default trigger when present; `triggers: []` declares none.
4. `index` and `template` are file names inside the folder; set them only when the project uses names other than `README.md` and `0000-template.md`.
5. Discover the manifests and the places the request points at (`git ls-files`); do not guess paths. Ask only what the request leaves open, such as whether version bumps of existing dependencies count. A broad trigger on a manifest also fires on routine version bumps; offer a narrower `patterns` entry and let the user choose.

```yaml
# .embraion/decisions.yaml
triggers:
  - id: dependency-change
    paths: ["**/package.json", "**/pyproject.toml", "**/requirements*.txt"]
    changes: [added, deleted, modified]
  - id: persisted-format
    paths: ["src/storage/format/**"]
```

```yaml
# .embraion/knowledge.yaml
slots:
  decisions: docs/architecture/decisions
```

Verify:

- `embraion decisions check --require-config --path . --base-ref <base>` (loads the full shape; `<base>` is the default branch, fetched). Without a base ref the check cannot compare, so say it was not run.
- `embraion context slots` for the binding, then `embraion check --base-ref <base>`, which runs the decisions check once the file exists.
- CI must call `embraion check --base-ref <base>` with the history fetched. Changing the CI workflow is a separate request; say what is missing instead of editing it.

A change that fires a trigger passes with a new or updated record, or with a `Decision-Waiver: <reason>` commit trailer whose reason a reviewer accepts. Never add a waiver to make a failing check pass.
