# Host-native orchestration evidence

Candidate: EmbrAIon 0.16.0, 2026-09-28.

## Deterministic evidence

The automated orchestration and config tests exercise a temporary consumer with
`agents: []`, Core and additive project specialist files, valid root TOML,
proportional Lead semantics, assignment-dependent project routing, all-host skill
projection, instruction preservation, legacy ownership migration, upgrade drift,
idempotence, malformed managed state, and explicit whole-file replacement.
Packaged reference projects also inspect the Lead contract, repeat installation,
and verify the generated projection. These checks establish installed guidance
and ownership behavior, not actual runtime delegation.

Fresh local release validation on Windows 11 / Python 3.14.4 passed:

- Unit suite: 188 tests, one skip because directory symlinks are unavailable.
- Integration suite: 23 tests, one opt-in network skip; the explicitly enabled
  network resolver E2E subsequently passed one test with no skips.
- Installed-wheel packaged references: four tests with no skips, then four
  tests with no skips from a copied suite excluding checkout import paths.
- Framework validation, fail-on-high security scan, all four host bundles,
  four behavioral eval cases, strict English/Russian documentation build,
  wheel/sdist build, and installed-wheel validation outside checkout: passed.

Initial sandbox network/file-access failures and scanner findings in a generated
temporary dependency environment were retained as evidence. Authorized network
installation and removal of temporary dependencies from the checkout resolved
them without source-policy or validator changes. Linux/macOS and other supported
Python versions are validated by the canonical CI/release matrix separately.

Independent review found a parent/child TOML ownership regression. The managed
agent block now precedes user child tables; the new regression verifies preserved
child settings, immediate projection verification, and identical repeat install.
An independent bounded re-review confirmed the fix before final integration.

## Native runtime attempt

An isolated temporary project received the installed Codex projection and real
project validation profiles. The plain-language prompt requested a mock-backed
cross-platform camera manager API, device and resolution/FPS selection, lifecycle
handling, tests, and documentation. It did not ask for agents or name roles.
No consumer repository or real camera SDK was modified.

Codex CLI 0.158.0 authenticated through ChatGPT. The invocation used `exec`,
`--ephemeral`, `--ignore-user-config`, `--strict-config`, `--json`,
`--sandbox workspace-write`, a fixture-scoped trust override, and `-C` pointing
at that project. The invocation produced no strict-config parse error; this does
not establish specialist activation or that every projected instruction applied.
The session completed in about 20 seconds with process exit 0, but its initial
repository inspection command was rejected by execution policy. The agent
reported a read-only filesystem with escalation disabled; no implementation,
tests, or specialist dispatch was recorded.

Result: **infrastructure limitation / runtime delegation unverified**. Process
exit 0 is not an engineering or orchestration pass. The restriction was not
bypassed. Local JSON events and stderr remain in ignored build evidence rather
than being promoted into a successful behavioral baseline.

## Execution limits

Root project instructions require trusted configuration loading and remain
subject to higher-priority instructions and native execution controls. Static
TOML cannot deterministically invoke project routing before each spawn. Lead
receives guidance to classify and resolve each assignment, then apply supported
native choices or report an unsupported required choice before dispatch.
Model-neutral role files leave explicit spawn choices applicable; host-default
resolution retains native defaults or inheritance. The orchestration skill
provides conceptual parity to other hosts through their own skill loading.
