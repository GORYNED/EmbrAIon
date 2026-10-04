# External capabilities

External capabilities are optional project declarations in `.embraion/external-capabilities.yaml`. They describe independently installed software or host features that a project may need. EmbrAIon Core rules and project contracts remain authoritative. The file is absent by default; absence means an empty inventory. Declarations never install software, fetch sources, enable a host plugin, grant access, or prove that a skill ran.

The inventory has a strict, versioned [schema](https://github.com/GORYNED/EmbrAIon/blob/main/schemas/external-capabilities.schema.json). The host or user controls installation and discovery of `host-managed` capabilities. EmbrAIon records metadata and reports bounded diagnostics; it does not install, copy, or replace host capabilities. A project can ask in natural language to install a capability through its host's supported workflow, verify that installation there, then ask EmbrAIon to register its actual source, version or digest, license, host, access, and data class. Registration describes the project requirement; it is not a gate that makes an installed capability available to the host.

```yaml
schema-version: 1
capabilities:
  - id: spec-kit
    kind: host-managed
    source: https://github.com/github/spec-kit
    version: 1.2.3
    license: MIT
    hosts: [codex]
    host-requirements: {codex: [plugins]}
    env-vars: []
    access: external-execution
    data-class: PRIVATE
```

The example records a separately installed capability; its version and host requirements must be checked against the actual installation before use. Each entry needs a unique ID, kind, source, exact `version` **or** `sha256:` `digest`, license, supported `hosts`, environment-variable *names* in `env-vars`, `access`, and one of `PUBLIC`, `PRIVATE`, or `CONFIDENTIAL` in `data-class`. Optional `host-requirements` lists named host features for declared hosts; diagnostics display those names but cannot verify them locally. The access values are `read-only`, `workspace-write`, and `external-execution`. Supported hosts are `codex`, `claude-code`, `copilot`, and `portable`. Do not store credentials, token values, command arguments, or host configuration values in this file. URL sources must use a plain HTTPS repository path without credentials, query strings, or fragments. Host-native identifiers may use `host:<identifier>`.

Schema v1 still accepts `kind: managed-bundle`, `id: unity`, and `source: builtin:unity` so existing inventories can be read and diagnosed. This is **legacy compatibility**, not a shipped or selectable bundle. Diagnostics mark the legacy entry unavailable. Install rejects it for a host selected by the entry, and update rejects it, before writing configuration or projections. EmbrAIon does not convert it automatically or change its version. A `host-managed` entry cannot select skills for projection.

To migrate, first install the desired Unity capability independently through the chosen host and verify its identity and availability there. Then explicitly remove the `builtin:unity` entry from `.embraion/external-capabilities.yaml`; if useful, register the independently installed capability as a new `host-managed` entry with its actual metadata. Run install again only after removing the legacy entry. Previously projected Unity skill files are preserved until the legacy entry is explicitly removed and an owned-file prune is run. Modified or unowned files are preserved by that prune and require separate manual review. No equivalent replacement skill is assumed to exist.

Diagnostics distinguish six stages: `declared`, `installed-config`, `host-discovered`, `instructions-read`, `tools-ready`, and `executed`. Reading the inventory verifies only `declared`. The legacy built-in entry is unavailable. For host-managed capabilities, the local diagnostic has no live host instrumentation; installation and later host stages remain `unverified` unless a supplied observation claims them. Accepted claims are labeled `self-reported`, never verified. A declared source, present environment-variable name, or claimed JSON event does not establish host loading or execution. Diagnostic `ready` remains false without trusted live host evidence.

A read-only caller can supply a bounded observation report. It must include `schema-version: 1`, the exact `scope` returned by `observation_scope(...)` or diagnostics, the target `host`, a timezone-aware ISO `observed-at`, and capability records containing exact `id`, `source`, `version-or-digest`, and claimed `stages`. Reports more than 24 hours old or more than five minutes in the future, with changed inventory identity, or with unrecognized fields are ignored. The scope binds the resolved project path, framework version, host, and inventory; it is an identity checksum, not authentication. Supplied reports are self-reported metadata even when current and correctly bound. Environment checks reveal names and present/absent booleans only; values are never returned.

`embraion capabilities --path <project> --host codex --json` displays the diagnostic inventory. `--observation <report.json>` supplies a bounded report; the command does not discover host plugins or run tools. Missing or ambiguous required capability evidence is not considered ready. `embraion update` leaves host-managed versions and digests under project control; a legacy `builtin:unity` selection must be removed explicitly before update can proceed.
