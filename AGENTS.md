# EmbrAIon Agent Instructions

EmbrAIon is the upstream source of truth for reusable AI-First engineering behavior.

## Repository ownership

- Put vendor-neutral behavior in `core/`.
- Put host/provider-specific representation in `adapters/`.
- Put deterministic executable operations in `tools/`.
- Put machine-readable contracts in `schemas/`.
- Put project bootstrap material in `templates/`.
- Keep product/domain-specific semantics in consuming-project overlays.

## Agent naming

Canonical Core agents are named as job-like roles, not activities or document types.

Preferred examples: `lead`, `worker`, `reviewer`, `architect`, `analyst`, `validator`, `researcher`, `steward`.

Do not create generic Core agents named after a task noun such as `specification`, `test`, or `routing` when a clear occupational role exists.

## File naming

- Use lowercase kebab-case for repository-owned files.
- Prefer one or two words when practical.
- Standard ecosystem filenames are exceptions, including `README.md`, `AGENTS.md`, and `SKILL.md`.
- Do not create long prose-like filenames when a shorter canonical term is sufficient.

## Capability taxonomy

- **Rule** — required, prohibited, or protected behavior.
- **Agent** — job-like responsibility and ownership.
- **Skill** — repeatable task procedure.
- **Workflow** — ordered execution sequence.
- **Routing** — model/provider/effort/execution selection policy.
- **Tool** — deterministic operation.
- **Adapter** — host/provider integration.
- **Knowledge** — facts and architecture, not commands.

## Spec Kit

Spec Kit is a recommended external capability for substantial feature, architecture, and specification work. EmbrAIon must integrate with it without copying or redefining upstream Spec Kit internals. Spec Kit artifacts never override Core rules, project architecture, product truth, or validation contracts.

## Brand terminology

- Use **AI-First Engineering System** in normal prose and title case.
- Use **AI-FIRST ENGINEERING SYSTEM** for the canonical all-caps brand category.
- The lowercase-F spelling is forbidden.

## README timestamps

- Every `README*.md` ends with a last-updated timestamp.
- Any README edit updates its timestamp in the same change.
- Canonical format: `YYYY-MM-DD HH:mm UTC`.
- Localized README files may localize the label.

## Change discipline

- Prefer the minimum justified change.
- Preserve compatibility unless a breaking change is explicit.
- Keep Core independent from any single host, provider, platform, or consuming project.
- Do not weaken Core hard rules from a project overlay.
- Add validation with machine-readable contracts.
- Keep model facts in adapter catalogs and routing policy in Core.
- Do not silently duplicate canonical policy.

## Completion reporting

For substantial work report: Changed, Architecture, Validation, Risks, and Workers.
