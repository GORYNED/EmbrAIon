# Completion report

`.embraion/report.yaml` is an optional, project-owned contract for the final report of substantial work. EmbrAIon does not choose the sections for you; it renders the contract you declare, embeds it in the projected `orchestration` skill, and checks report text against it.

```yaml
schema-version: 1
sections: [Changed, Architecture, Validation, Risks, Workers]
workers:
  section: Workers
  task-status: [completed, cancelled, incomplete]
  columns: [Status, Worker, Role, Billing, Access, Data, Runs, Cost, Routing, Validation]
pull-request:
  section: Changed
guidance:
  - Name the provider, task, access, and selection reason before each external worker attempt.
```

- `sections` are the top-level sections of the final report, in required order. Each appears exactly once as a Markdown heading or a bold-only line.
- `workers` (optional) requires one table with exactly these columns inside `workers.section`, preceded by a `Task status: <value>` line using one of `task-status`. Cells must not contain absolute machine paths, credential-like values, code fences, or diffs.
- `pull-request` (optional) makes `--pull-request` require a full pull request URL in that section.
- `guidance` lines are rendered into the template and the skill verbatim. They are not validated.

## Template and validation

```bash
embraion report template
embraion report validate report.md --pull-request
embraion report validate update.md --kind intermediate
```

A `final` report must match the contract. An `intermediate` update must not contain the Workers table or section. Section headings use ATX (`## Name`) or a bold-only line; setext underlines and a trailing colon are not recognized. Fenced code blocks are ignored while parsing, so quoted examples do not count.

Validation is structural. It cannot tell whether the content is true, and it does not replace review.

## Projection

When `.embraion/report.yaml` exists, `embraion install --component skills` adds a *Project completion report contract* section to the projected `orchestration` skill for every host. Run `embraion projection verify` to detect a stale projection after changing the contract.

<sub>Last updated: 2026-10-06 01:40 UTC</sub>
