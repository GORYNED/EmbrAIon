# Source registry

Projects can add `.embraion/sources.yaml`. It says, for each stable source ID, what the source is for, whether agents may write it, and where its documentation is. The file is optional. Without it nothing changes.

The registry is committed. It never holds a path on one machine. Machine paths go in ignored local state (see [Local availability](#local-availability)).

```yaml
schema-version: 1
sources:
  - id: App
    role: canonical-code
    write: workspace-write
    description: The application repository.
    doc: docs/sources.md
  - id: SharedLib
    role: shared-library
    write: workspace-write
  - id: OldApp
    role: reference
    write: read-only
  - id: VendorSdk
    role: external-upstream
    write: forbidden
    data-class: CONFIDENTIAL
```

## Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable source ID. It must be unique. |
| `role` | yes | One of the roles below. |
| `write` | yes | `read-only`, `workspace-write`, or `forbidden`. |
| `description` | no | One short sentence. |
| `doc` | no | Repository-relative path of the document that governs the source. The file must exist. |
| `data-class` | no | `PUBLIC`, `PRIVATE`, or `CONFIDENTIAL`. It can only raise the class of the source. |

Roles:

- `canonical-code`: the project's own authoritative code.
- `shared-library`: a first-party library that several projects reuse.
- `reference`: an example or an earlier implementation, kept for reading.
- `external-upstream`: a vendor or third-party source the project does not own.
- `application-data`: runtime or user data.

Write policies:

- `read-only`: agents read the source and never write it.
- `workspace-write`: agents may write it in an authorized task.
- `forbidden`: agents must not write it in any task.

## Rules

`embraion validate` checks the file. Unknown keys, unknown values, and a bad `schema-version` are errors. So are these:

- a duplicate `id`;
- an `id` that is not listed in `privacy.sources` of `.embraion/policy.yaml`, when that map is declared (see [Policy](policy.md#privacy-default));
- a `doc` that is absolute, leaves the project, or does not exist;
- a `data-class` below the class declared for the source. The base is `privacy.sources` for that ID, or `privacy.default-class` when the map is not declared.

A raised `data-class` is the effective class of the source. An execution request must use a data class at least that high. This also applies when `privacy.sources` is not declared; then only IDs with a raised `data-class` are checked and other IDs stay unchecked.

## Write policy in execution

When the file exists, a request with `access: workspace-write` may name only sources whose `write` is `workspace-write`. A request that names a `read-only`, `forbidden`, or unregistered source is refused before any provider is selected. Read-only requests are not checked for write policy. An invalid registry fails closed: it refuses every execution request, including read-only ones, until the file is fixed. Without the file the request checks are unchanged.

## Local availability

A source can exist on one machine and not on another. Record where it is in the ignored file `.embraion/state/sources-local.yaml`. It maps a source ID to an absolute path:

```yaml
App: /absolute/path/on/this/machine
```

Write it by hand or run `embraion sources set <id> <path>`. It is never committed. Commands print only the ID and `available`, `missing`, or `unset`. They never print the path. `embraion security scan` reports a medium `machine-path` finding for tracked content that contains a recorded path. It skips paths with fewer than two segments.

`embraion sources set` takes no lock, so run it once at a time. It refuses a symbolic-link `.embraion` or state folder.

The local file is discovery data. It cannot change a role or a write policy.

## Commands

```bash
embraion sources list [--json]
embraion sources status [--json]
embraion sources set <id> <path>
```

See the [CLI reference](../reference/cli.md#embraion-sources).
