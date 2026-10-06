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

## Scan findings

`embraion security scan` reads the project's text files and reports each finding with a category and severity:

| Category | Severity | Finds |
| --- | --- | --- |
| `private-key` | critical | a PEM private-key header |
| `api-key` | high | a key, secret, token, or password assigned a literal value |
| `access-token` | high | a provider-prefixed token without a key in front of it: GitHub classic and fine-grained (`ghp_…`, `github_pat_…`), cloud access key IDs (`AKIA…`), model-provider keys (`sk-…`), Google API keys (`AIza…`), and Slack tokens (`xox…`) |
| `machine-path` | medium | a home-directory path such as `/Users/<name>/`, `/home/<name>/`, or `C:\Users\<name>\` (also with forward slashes or JSON-escaped backslashes) |
| `policy-drift` | medium | a legacy data-class name that no execution alias declares |

A token body must contain a digit, so identifiers and documentation placeholders with these prefixes are not reported. CI runner and shared homes and placeholder names such as `user`, `example`, or `<name>` are not machine paths. A `machine-path` finding stays below the default `--fail-on high`; pass `--fail-on medium` to make it fail. `embraion security redact` and evidence redaction replace a bare prefixed token with `<REDACTED:access-token>`.

By default the scan reads Markdown, YAML, JSON, TOML, plain-text, Python, PowerShell, and shell files plus `.gitignore` and `.editorconfig`, outside tool folders such as `.git`, `.venv`, `node_modules`, and `Library`. `--all-files` also reads every other tracked or unignored untracked file of at most 2 MiB that contains no NUL byte, such as C#, native, or Unity asset sources; outside Git it reads every other file outside the tool folders. Files inside Git submodules are not included. Those files are checked only for `private-key`, `access-token`, and `machine-path`; the keyword-based `api-key` check would flag ordinary code assignments there.

## Canonical data classes and compatibility aliases

Core policy uses exactly `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`.

A project may preserve historical vocabulary at an **execution boundary** through an explicit `dataClassAliases` mapping in `.embraion/execution.yaml`. For example, mapping `CONFIDENTIAL` to a project-specific legacy label does not create a new Core class and does not weaken privacy policy.

Aliases exist for compatibility, not for inventing weaker classifications. New projects should normally use the canonical classes directly.

## Project policy and enforcement

Project-owned source classes, privacy defaults, review rules, and enforcement settings live in `.embraion/policy.yaml`.

A green test or behavioral eval cannot override privacy, protected-source, permission, or security failures. Likewise, model routing cannot widen these boundaries.

See [Policy & Protected Paths](configuration/policy.md), [Execution & providers](configuration/execution.md), and [Enforcement](guides/enforcement.md).
