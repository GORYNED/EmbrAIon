# EmbrAIon Agent Instructions

EmbrAIon is the upstream source of truth for reusable AI-First engineering behavior.

## Repository ownership

- Put vendor-neutral behavior in `core/`.
- Put host/provider-specific representation in `adapters/`.
- Put deterministic executable operations in `tools/`.
- Put machine-readable contracts in `schemas/`.
- Put project bootstrap material in `templates/`.
- Keep product/domain-specific semantics in consuming-project overlays.

## Capability loading

- `core/catalog.yaml` is the canonical discovery index.
- Prefer conditional capability loading over injecting the entire Core into every task.
- Every catalog path must resolve to exactly one canonical capability.
- Skills use one directory per skill with `SKILL.md` as the entry point.
- Supporting skill files belong beside that skill and must not become global context by accident.

## Agent naming

Canonical Core agents are job-like roles: `lead`, `worker`, `reviewer`, `architect`, `analyst`, `validator`, `researcher`, and `steward`.

Do not create generic Core agents named after task nouns when a clear occupational role exists.

## Separation of concerns

Agent role, access profile, model route, and provider are independent dimensions.

A role never implies broader permissions or a more expensive model. Model choice never expands access.

## File naming

- Use lowercase kebab-case for repository-owned files.
- Prefer one or two words when practical.
- Standard ecosystem filenames are exceptions, including `README.md`, `AGENTS.md`, and `SKILL.md`.

## Evals

Use deterministic tests for schemas, code, references, and generated output. Use `evals/` for behavioral properties such as role adherence, permission discipline, routing choices, and completion behavior.

## Spec Kit

Spec Kit is a recommended external capability for substantial specification-driven work. It remains independently managed and never overrides EmbrAIon Core or project truth.

## Brand terminology

- Use **AI-First Engineering System** in normal prose and title case.
- Use **AI-FIRST ENGINEERING SYSTEM** for the canonical all-caps brand category.
- The lowercase-F spelling is forbidden.

## README timestamps

- Every `README*.md` ends with a last-updated timestamp.
- Any README edit updates its timestamp in the same change.
- Canonical format: `YYYY-MM-DD HH:mm UTC`.

## Change discipline

- Prefer the minimum justified change.
- Preserve compatibility unless a breaking change is explicit.
- Keep Core independent from any single host, provider, platform, or consuming project.
- Do not weaken Core hard rules from a project overlay.
- Do not silently duplicate canonical policy.

## Completion reporting

For substantial work report: Changed, Architecture, Validation, Risks, and Workers.
