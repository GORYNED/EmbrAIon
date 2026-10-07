# Security

EmbrAIon treats execution permissions, data classification, provider eligibility, external integrations, generated configuration, credentials, and mutation rights as enforceable engineering constraints.

Security policy belongs in Core rules and project policy. Host/provider adapters implement their mechanics, while deterministic tools inspect configuration, external integrations, and persisted evidence.

## Fail-closed behavior

The framework should fail closed when:

- a task cannot be safely classified;
- a provider or execution path is not permitted for the relevant data;
- an integration has unknown or unexpectedly broader access;
- a secret appears in persisted configuration;
- generated configuration drifts from its approved source;
- a writable action exceeds its access profile or owned paths;
- protected project sources would be mutated without the required path.

Security findings are evidence, not permission to weaken the controlling policy.

## Runtime redaction and environment handling

Runtime state applies credential redaction before persistence.

For child processes launched by EmbrAIon-owned adapters, the framework constructs a minimal allowlisted environment instead of forwarding the host environment wholesale. Captured child-process output is redacted before it is stored as evidence.

Host-native agents launched by an external AI client remain subject to that host's own environment and credential controls. EmbrAIon does not claim to override security boundaries owned by the host.

## External integrations

MCP and other external server/tool configuration is inventoried separately from Core policy. Inventory records privacy-safe metadata and drift rather than secret values.

Use:

```bash
embraion security scan --path . --fail-on high
embraion mcp inventory
```

to inspect deterministic security and integration surfaces.

### Declared integrations

A project can declare the MCP servers it expects in the optional, schema-checked `.embraion/integrations.yaml` ([schema](https://github.com/GORYNED/EmbrAIon/blob/main/schemas/integrations.schema.json)). Without the file nothing is compared and the scan behaves as before.

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

Each entry names the server `id` and the `host` whose configuration holds it: `generic` (`.mcp.json`), `vscode` (`.vscode/mcp.json`), `claude-code` (`.claude/settings.json` and `.claude/settings.local.json`), or `codex` (`.codex/config.toml`). It also records `command`, `args`, `transport`, `access` (`read-only`, `workspace-write`, or `external-execution`), and environment-variable **names** in `env-vars`; never store values. Omit `command` for a URL server. A host without an explicit type runs a command server over `stdio` and a URL server over `http`. Entries are portable by default: a machine-absolute path in `command` or `args` is a finding. Set `portable: false` only for a deliberately machine-local server, such as one in an ignored `.claude/settings.local.json`: it may use machine-absolute paths and is not reported as missing where it is not configured, but a configured copy is still compared with its declaration. A Codex entry with `enabled = false` only switches a server off, so it is neither compared nor reported as unexpected; a declaration for it is reported as missing. Other hosts have no per-server `enabled` key, and their entries are always compared.

Two optional fields, `cwd` (the working directory of the server) and `required` (`true` or `false`), are compared only when a declaration sets them; a declaration without them compares as before. Only Codex configuration carries these keys, so only `host: codex` entries may set them; the other hosts reject them as an invalid declaration. For Codex, `cwd` is compared with the `cwd` string, where a missing key counts as unset, and `required` is compared with the `required` boolean, where a missing key counts as `false`. A difference is an `integration-mismatch` finding that names the field. Working-directory values are omitted to protect local paths and credentials; `required` reports the expected and observed booleans. A portable entry must not declare a machine-absolute `cwd`. A Codex server with `enabled = false` is still skipped before these fields are compared.

When the file exists, `embraion security scan` and `embraion doctor` compare it with the observed configuration and report each difference as a high-severity `integration-drift` finding: a declared server that is not configured (`integration-missing`), a configured server that is not declared (`integration-unexpected`), a server whose command, arguments, transport, environment-variable names, or declared `cwd` or `required` value differ (`integration-mismatch`), a non-portable declaration, an invalid declaration file, or host configuration that cannot be read. The scan therefore fails closed at the default `--fail-on high`. Findings never print argument values, redact credential-like command values, and report schema errors by location only. `access` is declared metadata; host configuration does not expose it, so it is not compared.

## Scan findings

`embraion security scan` reads the project's text files and reports each finding with a category and severity:

| Category | Severity | Finds |
| --- | --- | --- |
| `private-key` | critical | a PEM private-key header |
| `api-key` | high | a key, secret, token, or password assigned a literal value |
| `access-token` | high | a provider-prefixed token without a key in front of it: GitHub classic and fine-grained (`ghp_…`, `github_pat_…`), cloud access key IDs (`AKIA…`), model-provider keys (`sk-…`), Google API keys (`AIza…`), and Slack tokens (`xox…`) |
| `machine-path` | medium | a home-directory path such as `/Users/<name>/`, `/home/<name>/`, or `C:\Users\<name>\` (also with forward slashes or JSON-escaped backslashes) |
| `policy-drift` | medium | a legacy data-class name that no execution alias declares |
| `integration-drift` | high | a difference between declared and observed MCP servers; only when `.embraion/integrations.yaml` exists, see [Declared integrations](#declared-integrations) |

A token body must contain a digit, so identifiers and documentation placeholders with these prefixes are not reported. CI runner and shared homes and placeholder names such as `user`, `example`, or `<name>` are not machine paths. When the project keeps ignored local source paths (see [Source registry](configuration/sources.md#local-availability)), tracked content that contains one of them is also reported as `machine-path`. The finding names the source ID and the file, never the path. A `machine-path` finding stays below the default `--fail-on high`; pass `--fail-on medium` to make it fail. `embraion security redact` and evidence redaction replace a bare prefixed token with `<REDACTED:access-token>`.

By default the scan reads Markdown, YAML, JSON, TOML, plain-text, Python, PowerShell, and shell files plus `.gitignore` and `.editorconfig`, outside tool folders such as `.git`, `.venv`, `node_modules`, and `Library`. `--all-files` also reads every other tracked or unignored untracked file of at most 2 MiB that contains no NUL byte, such as C#, native, or Unity asset sources; outside Git it reads every other file outside the tool folders. Those files are checked only for `private-key`, `access-token`, and `machine-path`; the keyword-based `api-key` check would flag ordinary code assignments there. `--all-files` adds no files from Git submodules.

With `--all-files`, the scan reads `sources` from the project's `.embraion/policy.yaml` and waives only the `machine-path` check for content the project cannot edit, using the same glob matching as policy elsewhere (`fnmatch` plus `**` for zero or more folders):

- other text files under `external` or `generated` are still checked for private keys and access tokens;
- configuration and documentation files under `external` keep every check except `machine-path`, because they are vendor-owned; those under `generated` keep every check, because generated configuration is what tools load and is fixed by regenerating it from its source;
- EmbrAIon configuration under `.embraion/` and a path that also matches `canonical` or `protected` keep every check.

Secrets are therefore never skipped. The output reports how many files had the machine-path check waived (`machine-path-waived-files` with `--json`). A missing, unreadable, or malformed policy waives nothing. The scan reads only the explicit `sources` lists, not the entries derived from local projection ledgers, so its result does not depend on local state. Without `--all-files` the policy is not consulted, so the default scan is unchanged.

## Canonical data classes and compatibility aliases

Core policy uses exactly `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`.

A project may preserve historical vocabulary at an **execution boundary** through an explicit `dataClassAliases` mapping in `.embraion/execution.yaml`. For example, mapping `CONFIDENTIAL` to a project-specific legacy label does not create a new Core class and does not weaken privacy policy.

Aliases exist for compatibility, not for inventing weaker classifications. New projects should normally use the canonical classes directly.

## Project policy and enforcement

Project-owned source classes, privacy defaults, review rules, and enforcement settings live in `.embraion/policy.yaml`.

A green test or behavioral eval cannot override privacy, protected-source, permission, or security failures. Likewise, model routing cannot widen these boundaries.

See [Policy & Protected Paths](configuration/policy.md), [Execution & providers](configuration/execution.md), and [Enforcement](guides/enforcement.md).
