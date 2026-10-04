# External capabilities

External capabilities are optional project declarations in `.embraion/external-capabilities.yaml`. They describe software or host features that a project may need. EmbrAIon Core rules and project contracts remain authoritative. The file is absent by default; absence means an empty inventory. Declarations never install software, fetch sources, enable a host plugin, grant access, or prove that a skill ran.

The inventory has a strict, versioned [schema](https://github.com/GORYNED/EmbrAIon/blob/main/schemas/external-capabilities.schema.json). A managed bundle is shipped in the pinned EmbrAIon framework. A host-managed capability is independently installed and controlled by the AI host or user. Only selected, manifest-listed built-in skills can be projected into a host skill directory. Host-managed entries are diagnostic metadata and are never copied by EmbrAIon.

```yaml
schema-version: 1
capabilities:
  - id: unity
    kind: managed-bundle
    source: builtin:unity
    version: 0.21.0
    license: MIT
    hosts: [codex]
    host-requirements: {codex: [skills]}
    env-vars: []
    access: workspace-write
    data-class: PRIVATE
    selected-skills: [unity-asset-audit]
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

Each entry needs a unique ID, kind, source, exact `version` **or** `sha256:` `digest`, license, supported `hosts`, environment-variable *names* in `env-vars`, `access`, and one of `PUBLIC`, `PRIVATE`, or `CONFIDENTIAL` in `data-class`. Optional `host-requirements` lists named host features for declared hosts; diagnostics display those names but cannot verify them locally. The access values are `read-only`, `workspace-write`, and `external-execution`. Supported hosts are `codex`, `claude-code`, and `copilot`, `portable`. Do not store credentials, token values, command arguments, or host configuration values in this file. URL sources must use a plain HTTPS repository path without credentials, query strings, or fragments. Host-native identifiers may use `host:<identifier>`.

For `builtin:unity`, the ID must be `unity`, `version` must exactly match both the project's framework pin and the running framework, and `selected-skills` must name skills in `extensions/unity/manifest.yaml`. The manifest must identify the same framework version and license. A selected source must be under `extensions/unity/skills/<skill-id>` and contain `SKILL.md`. A missing, mismatched, or unsafe source stops projection. The built-in Unity skills are EmbrAIon framework content; they do not install the Unity editor or any third-party tool. A host-managed entry cannot select skills for projection.

Diagnostics distinguish six stages: `declared`, `installed-config`, `host-discovered`, `instructions-read`, `tools-ready`, and `executed`. Reading the inventory verifies only `declared`. For a built-in bundle, diagnostics can verify `installed-config` by checking the pinned framework manifest and selected skill files. For host-managed capabilities, and for all later host stages, the local diagnostic has no live host instrumentation. Those stages remain `unverified` unless a supplied observation claims them; accepted claims are labeled `self-reported`, never verified. A declared source, present environment-variable name, or claimed JSON event does not establish host loading or execution. Diagnostic `ready` remains false without trusted live host evidence.

A read-only caller can supply a bounded observation report. It must include `schema-version: 1`, the exact `scope` returned by `observation_scope(...)` or diagnostics, the target `host`, a timezone-aware ISO `observed-at`, and capability records containing exact `id`, `source`, `version-or-digest`, and claimed `stages`. Reports more than 24 hours old or more than five minutes in the future, with changed inventory identity, or with unrecognized fields are ignored. The scope binds the resolved project path, framework version, host, and inventory; it is an identity checksum, not authentication. Supplied reports are self-reported metadata even when current and correctly bound. Environment checks reveal names and present/absent booleans only; values are never returned.

`embraion capabilities --path <project> --host codex --json` displays the diagnostic inventory. `--observation <report.json>` supplies a bounded report; the command does not discover host plugins or run tools. Missing or ambiguous required capability evidence is not considered ready.

`embraion update` validates the target Unity manifest and selected sources, then advances an existing managed built-in bundle version with the framework pin. Host-managed versions and digests remain project-owned and unchanged. Invalid selections or inconsistent old pins stop the update before configuration writes.
