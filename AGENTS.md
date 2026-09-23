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

## Agent naming

Canonical Core agents are job-like roles: `lead`, `worker`, `reviewer`, `architect`, `analyst`, `validator`, `researcher`, and `steward`.

## Separation of concerns

Agent role, access profile, model route, provider, and external integration state are independent dimensions.

A role never implies broader permissions or a more expensive model. Model choice never expands access.

## Data classes

Use exactly three canonical data classes: `PUBLIC`, `PRIVATE`, and `CONFIDENTIAL`. Unknown classification fails closed.

## Learning

Learning output is advisory until explicitly promoted. Runtime evidence may create candidates, but no learning tool may directly mutate Core. Promotion uses review, validation, applicable evals, and explicit approval.

## Security and integrations

- External integrations must be inventoried.
- Inventories store metadata and environment-variable names, never secret values.
- Unknown integration state, access expansion, provider/privacy mismatch, and embedded credentials fail closed according to policy.
- Security scanners report findings; they do not weaken policy to pass.

## Worktrees

Worktree cleanup is evidence-driven and fail-closed. Preserve ambiguous, dirty, locked, active, divergent, or unproven state. Salvage recoverable work before destructive cleanup.

## Evals

Use deterministic tests for schemas, code, references, and generated output. Use `evals/` for behavioral properties and baseline comparison.

## Spec Kit

Spec Kit is a recommended external capability for substantial specification-driven work. It remains independently managed and never overrides EmbrAIon Core or project truth.

## File naming

- Use lowercase kebab-case for repository-owned files.
- Prefer one or two words when practical.
- Standard ecosystem filenames are exceptions, including `README.md`, `AGENTS.md`, and `SKILL.md`.
- Python modules use standard `snake_case` where required by the Python import system.

## Brand terminology

- Use **AI-First Engineering System** in normal prose, metadata, headings, labels, and repository text.
- Reserve **AI-FIRST ENGINEERING SYSTEM** exclusively for graphical banners and brand artwork.
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
