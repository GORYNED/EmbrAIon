# Architecture Decision Records

Projects can require an architecture decision record when a change makes an architecture-level decision. The check reads Git history and never changes files. It is opt-in: without `.embraion/decisions.yaml` it returns `skipped`, and `embraion check` does not run it.

The records live in one folder. Bind it with the `decisions` [project contract slot](knowledge.md#project-contract-slots); the default is `docs/architecture/decisions/`.

```yaml
# .embraion/knowledge.yaml
slots:
  decisions: docs/architecture/decisions
```

The folder holds one Markdown file per record named `NNNN-<kebab-title>.md`, an index (`README.md` by default), and a template (`0000-template.md` by default). Accepted records are immutable apart from metadata; a change supersedes a record with a new one and links the two both ways. Status changes go through the owner or the project's process. The `architecture-decision` skill describes how to write a record; the planning, orchestration, and review skills ask whether a task makes such a decision and whether it is recorded.

## Configuration

`.embraion/decisions.yaml` selects the check and declares what counts as architectural. An empty file enables the check with the default trigger; `triggers: []` declares none. The file is read from the head of the change, so changes to it need the same review as any policy file.

```yaml
index: README.md          # optional index file inside the folder
template: 0000-template.md     # optional template file inside the folder
triggers:                 # optional; replaces the default trigger when present
  - id: assembly-references
    paths: ["**/*.asmdef"]
    changes: [modified]
    patterns: ['"references"']
  - id: persisted-format
    paths: ["src/storage/format/**"]
extra-triggers:           # optional; appended to the default or declared triggers
  - id: public-contract
    paths: ["src/api/**"]
```

`extra-triggers` has the same item shape as `triggers`. It adds triggers to whatever `triggers` resolves to, which is the default trigger when `triggers` is absent, so a project that wants one more rule need not copy the default. Trigger ids must be unique across the default trigger, `triggers` and `extra-triggers`; a duplicate id is an error. Without `extra-triggers`, nothing changes.

A trigger fires for a changed file when all of these hold:

- the file path matches one of `paths` (repository-relative globs; `**/` also matches zero directories);
- the kind of change is in `changes` (`added`, `deleted`, `modified`, `renamed`; all four when omitted); a rename matches on either path;
- when `patterns` is given, at least one added or removed line of the file matches one of the regular expressions.

The default trigger, `package-added-or-removed`, fires when a package manifest is added or deleted: `**/package.json`, `**/*.asmdef`, `**/pyproject.toml`, `**/Cargo.toml`, `**/go.mod`, or `**/*.csproj`. Changed manifests are not a default trigger, because most changes to them are routine dependency updates. Detection is deliberately conservative: a missed trigger is cheap to fix in review, while a false positive on routine work gets the check disabled. Declare project triggers for dependency declarations, assembly references, namespace or folder ownership rules, persisted formats and stable identifiers, and platform or build files.

## The gate

`embraion decisions check --base-ref origin/main` compares the merge base of the base ref and `HEAD` with `HEAD`. It passes when:

- no trigger fires (`no-trigger`);
- the change adds or modifies a record Markdown file directly inside the decisions folder; the index and the template do not count (`recorded`); or
- the change carries a waiver (`waived`).

Otherwise it fails with `missing-record`. A waiver is a `Decision-Waiver: <reason>` trailer on any commit of the change, or the `--waiver "<reason>"` option, which a pull request workflow can fill from a field of the pull request body. A blank reason is not a waiver. The waiver text appears in the report, and the reviewer decides whether the reason holds.

`embraion check --base-ref <ref>` runs this check when `.embraion/decisions.yaml` exists. Without `--base-ref` it prints `NOT RUN  decisions` with the reason and does not fail, so a missing base is never reported as a pass.

## Scaffold

```bash
embraion adr new "Move parsing into its own package"
embraion adr new "Move parsing into its own package" --locale ru --status Proposed
```

The command creates the next numbered record from the project template, adds a row to the index, and with `--locale <code>` creates a localized copy next to it (`NNNN-<title>-ru.md`; a `0000-template-ru.md` next to the template is used for it when present). In a project without records it also creates the folder, the template, and the index; their layout (a `README.md` index with an `ADR | Status | Decision` table, the lifecycle statuses, and a template with context, decision, consequences, alternatives, validation, and rollout sections) is the format the first projects using this workflow settled on, and the project owns it from then on. Numbers are never reused: the next number is above every number found in the folder, the index, and the folder's history on any ref. A new row follows the columns of an existing index table by header name. The title must contain ASCII words for the file name, or pass `--slug`. The template can use `{{number}}`, `{{title}}`, `{{status}}`, and `{{date}}`; `--date` fixes the date, so the same inputs give the same files.
