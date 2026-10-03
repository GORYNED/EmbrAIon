---
name: unity-asset-audit
description: Audit a named Unity asset scope for metadata, references, imports, and ownership without automatic repository-wide rewrites.
---

# Unity Asset Audit

Load for an explicitly requested Unity asset/reference audit or a concrete broken-asset symptom. Skip routine code work without asset risk and avoid scanning or rewriting every asset by default.

1. Define the folders, asset types, scenes, packages, and failure question. Read project ownership, Unity version, import rules, and source-authority contracts before evaluating findings.
2. Inspect GUID and `.meta` pairing, duplicate or missing IDs, broken object references, importer settings, addressable/resource references, and package/assembly boundaries relevant to that scope. Distinguish a verified broken reference from a textual match or speculative unused asset.
3. Classify each finding by reproducible evidence, affected consumer, and safe action. For serialized mutations, use already installed Unity Editor APIs or official project tooling where possible. Preserve identity on moves; do not mass-delete, reserialize, or regenerate metadata from an audit alone.
4. If fixes are in scope, validate a representative affected scene, prefab, or asset in the project's Unity version and run the checks required by impact. Keep the audit evidence and fix diff separate enough to trace each action.

Output: scoped inventory, evidence-backed findings, changed asset/metadata paths if any, validation results, and unresolved references. Follow Core compatibility-migration, validation, and review gates.
