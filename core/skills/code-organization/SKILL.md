---
name: code-organization
description: Place new or moved code in the owning project structure before creating types or files, and assess explicitly scoped reorganizations.
---

# Code Organization

Use before adding, moving, or renaming a source file or type. For everyday work, decide placement as part of the change; reorganize existing code only when the requested scope calls for it.

1. Inspect nearby source, existing meaningful folders, dependency direction, and project-owned architecture, source-authority, and coding-standard contracts. Resolve applicable `.embraion/knowledge.yaml` bindings, including custom entries. Do not invent a rule when the project has none.
2. Identify the feature or responsibility that owns the code, then place it with that owner. Prefer an existing coherent folder. Add a folder only when it clarifies an actual boundary; avoid arbitrary depth and unrelated root-level `Helpers`, `Utils`, or `Common` dumping grounds.
3. Use shared code only for a genuinely common purpose with a valid dependency direction. Check that the proposed location does not create reverse or cyclic dependencies. Follow project-specific folder, namespace, and assembly rules where they exist. Run a configured project organization check when available and relevant; report its scope and result. Keep names clear; do not strip prefixes mechanically.
4. When a requested audit or migration has an explicit scope, map old locations to proposed locations with an ownership and dependency rationale. Identify identity, persistence, import, build, and reference risks before moving code. Apply compatibility-migration or an installed domain skill only when its trigger matches. Preserve stable identifiers, metadata, and actual contracts; update affected references and validate the resulting structure.

Do not turn an ordinary feature or fix into an opportunistic repository-wide reshuffle. Escalate unresolved ownership or dependency boundaries to the appropriate project authority or Architect.
