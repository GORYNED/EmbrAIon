# Pre-Adoption Hardening

EmbrAIon includes a compact set of contracts that make first adoption in a real repository safer.

## Host skills

Reusable Core skills are projected using host-native project layouts:

| Host | Skill directory |
| --- | --- |
| Codex | `.agents/skills/<skill>/SKILL.md` |
| GitHub Copilot | `.github/skills/<skill>/SKILL.md` |
| Claude Code | `.claude/skills/<skill>/SKILL.md` |

Agents remain responsibility definitions. Skills remain reusable procedures.

## Project policy overlay

Projects can classify source paths, declare validation profiles, require independent review for substantial work, and set a default privacy class.

## Projection ownership

Installed host projections persist generated-file hashes under `.embraion/state/`.

A later projection diff classifies files as create, safe update, unchanged, conflict, obsolete-but-owned, or obsolete-and-modified.

Mature repositories can scope install and diff to host-native components such as `skills` without taking ownership of existing host configuration or agents. Ownership state is preserved for previously managed but currently unselected components.

## Context provenance

Structured knowledge entries can declare path, data class, trust source, eligible roles, and task triggers.

`embraion context build` selects eligible files deterministically and stores only provenance metadata and hashes. Knowledge contents are not duplicated into runtime state.

## Execution evidence

`embraion run` records route choice, access, owned paths, context identity, changed paths, validation, review, outcome, and residual risk.

Completed writable runs are checked against owned scope and project-protected path patterns.

## Redaction and harness audit

Runtime state applies credential redaction before persistence.

For child-process adapters owned by EmbrAIon, `allowlisted_environment()` constructs a minimal environment instead of forwarding the host environment wholesale, and `redact_child_output()` sanitizes captured stdout/stderr before persistence. Host-native agents launched by external hosts remain subject to those hosts' own environment controls.

`embraion harness audit` reports generated agents and skills plus host-native hook/enforcement availability. Hook execution stays explicit: EmbrAIon does not silently install executable policy hooks into a consuming repository.
