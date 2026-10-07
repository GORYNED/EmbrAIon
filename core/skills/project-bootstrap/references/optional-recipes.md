# Optional file recipes

Recipes for `.embraion/` files that `embraion init` does not create. Create a file only when the request needs it, and never leave an empty file behind (`embraion validate --strict` reports it as inert). `embraion validate --strict` checks only key names and passes a wrong shape; the loader command in each recipe checks the full shape, so always run it and fix what it reports instead of guessing values.

## declare-integration

Creates `integrations.yaml`: the MCP servers the host configuration must contain. `embraion security scan` then reports every difference as a high-severity `integration-drift` finding.

- Discover: read the host configuration the servers live in: `.mcp.json` (`generic`), `.vscode/mcp.json` (`vscode`), `.claude/settings.json` and `.claude/settings.local.json` (`claude-code`), `.codex/config.toml` (`codex`). `embraion mcp inventory` lists them. Declare only servers that are already configured. Adding a new server to the host is a separate, explicit action.
- Ask for each server's `access` (`read-only`, `workspace-write`, `external-execution`); host configuration does not reveal it. Ask whether a server is machine-local.
- Write names only: `env-vars` lists variable names, never values. Omit `command` for a URL server. A machine-absolute path in `command` or `args` is a finding unless `portable: false` is set for a deliberately machine-local server.

```yaml
schema-version: 1
servers:
  - id: docs
    host: generic
    command: npx
    args: ["-y", "docs-server"]
    transport: stdio
    access: read-only
    env-vars: [DOCS_TOKEN]
```

Verify: `embraion security scan --path . --fail-on high` (it loads the full shape), then `embraion doctor`.

## declare-external-capability

Creates `external-capabilities.yaml`: software or host features installed independently of EmbrAIon. A declaration is not an installation and not proof that a host loaded it.

- Discover from the installed capability: its source, exact version or digest, license. Never guess them.
- Ask the host(s) (`codex`, `claude-code`, `copilot`, `portable`), the `access` level, and the `data-class`.
- Required per entry: `id` (kebab-case), `kind: host-managed`, `source` (a plain HTTPS repository URL such as `https://github.com/<owner>/<repo>`, or `host:<identifier>`), exactly one of `version` or `digest` (`sha256:` plus 64 hex digits), `license`, `hosts`, `env-vars` (names only), `access`, `data-class`. Never create `managed-bundle` entries.

```yaml
schema-version: 1
capabilities:
  - id: docs-helper
    kind: host-managed
    source: https://github.com/example-org/docs-helper
    version: 1.2.3
    license: MIT
    hosts: [claude-code]
    env-vars: []
    access: read-only
    data-class: PUBLIC
```

Verify: `embraion capabilities --path . --host <host>`. A reported `declared` stage is all it can prove.

## limit-code-structure

Creates `organization.yaml`: incremental checks of file names, namespaces, and engine-specific assembly and asset-metadata rules. The checker never changes files.

- Discover: the folders the team owns, vendor and generated folders to put under `exclude`, existing naming practice. Every `roots` entry must be an existing folder.
- Ask which rule to enforce only when the request is broad. Enable only the sections the request needs; each section is independent.
- `filenames`: lowercase kebab-case names under `roots` for the listed `extensions`; `allow` adds exact basenames; `suffixes` adds folder-bound suffixes; `case_collisions` defaults to on.
- `namespaces`: `rules` map a folder `path` to a `namespace` prefix, with optional `require_declaration` and `exceptions`.
- `assemblies` and `unity_meta` apply only to engine projects that have assembly definition files or asset `.meta` files; the organization page in the documentation describes them. Do not enable them for other projects.
- Existing violations do not waive a new one. Report them; do not mass-rename files to make the check pass.

```yaml
exclude:
  - vendor/**
filenames:
  enabled: true
  roots: [docs]
  extensions: [.md]
  allow: [NOTICE.md]
```

Verify: `embraion organization check --require-config --path .`. For an incremental gate add `--base-ref <base>`.

## track-doc-sources

Creates `knowledge-maintenance.yaml`: which document depends on which source files, so a changed source flags the document for review. It never rewrites documents.

- Discover which files each document describes by reading it. Paths must be project-relative regular files.
- Write `documents` entries with `id`, `path`, and at least one `sources` path. `observed-version` only when an external version was actually observed.
- After the user agrees the relationships are right, run `embraion knowledge snapshot --path .` once. It stores a local baseline under `.embraion/state/`; a later snapshot replaces the baseline only when explicitly requested.

```yaml
documents:
  - id: architecture
    path: docs/architecture.md
    sources:
      - src/app.py
```

Verify: `embraion knowledge audit --path .` (`current`, `needs-review`, `missing`, or `unconfigured`).

## shape-final-report

Creates `report.yaml`: the sections of the final report of substantial work. EmbrAIon renders it into the projected orchestration skill and checks report text against it.

- Ask the section names and their order when the request does not give them. Keep Core's own report expectations: do not drop `Validation` or `Risks` unless the user asks.
- Required: `schema-version: 1` and `sections`. Optional: `workers` (`section`, `task-status`, `columns`, `summary`), `pull-request` (`section`), `guidance` (free text lines).

```yaml
schema-version: 1
sections: [Changed, Validation, Risks]
pull-request:
  section: Changed
```

Verify: `embraion report template`. Then refresh the projection: `embraion status` lists installed hosts; run `embraion install --host <host> --destination .` for each, then `embraion projection verify --host <host> --destination .`.

## claude-native-agents

Creates `claude-native.yaml`: routing roles to project as native Claude agents. It contains no model or effort; those come from routing and deployments.

- Prerequisite: routing already selects an eligible deployment for each role and route class. Without that the command reports an explicit-settings error. Configure routing first.
- Ask which roles, route classes, and data classes to project, and whether reads are limited to the project (`read-policy.project-only`, `read-policy.deny-protected`).
- `assignments` need `role`, `route-class` (`bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, `critical`), `data-class`, `access` (`inspect`, `plan`, `review`, `write`, `external-read`). `bindings` map a routing role to a native agent id.

```yaml
bindings:
  reviewer: reviewer
assignments:
  - role: reviewer
    route-class: substantial
    data-class: PRIVATE
    access: review
read-policy:
  project-only: true
  deny-protected: true
```

Verify: `embraion route --validate`, `embraion claude-native status`. Then install the component with `embraion install --host claude-code --destination . --component scoped-agents`. Installing hooks (`embraion claude-native install-hooks`) edits `.claude/settings.json`; run it only after the user agrees. A new Thread is needed before the host sees the agents.

## project-skill

Creates `.embraion/skills/<name>/SKILL.md`: a project-owned procedure projected next to the Core skills for every installed host.

- Discover: read the procedure from existing project documents. Check that no Core skill already covers it; a project skill must not reuse a Core skill name.
- Name: lowercase kebab-case, at most 64 characters. Required front matter: `name` equal to the directory name, and a non-empty `description` that says when to use it, in the words a user would say. Put long material in `references/` beside it. No symbolic links.
- Keep project facts in the skill; keep reusable mechanisms out of it.

```markdown
---
name: release-checklist
description: Follow the project's release checklist when the user asks to prepare, cut, or publish a release.
---

# Release checklist

1. ...
```

Verify: `embraion install --host <host> --destination .` for each installed host (it fails before writing when the skill is invalid), then `embraion projection verify --host <host> --destination .`.
