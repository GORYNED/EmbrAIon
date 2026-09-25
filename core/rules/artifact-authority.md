# Artifact Authority

Validate artifacts according to the contract of their authoritative owner.

Project-specific naming, layout, schema, and formatting conventions apply to project-owned surfaces. Host-native, framework-generated, tool-required, package/ecosystem, external, and vendor-owned artifacts must preserve the contract defined by the authority that owns their identity or format.

Project policy may tighten security, privacy, integrity, and mutation boundaries when that tightening is compatible with the authoritative contract. It must not make a valid host, framework, tool, package, or vendor artifact invalid merely because the project prefers a different local convention.

AI-generated project source remains project-owned unless it is emitted through an explicit host, framework, tool, package, or external projection contract.

Generated framework or host projections should be regenerated from their canonical source rather than hand-edited when the framework owns them.

Determine authority before applying project conventions: validate by authority, not by location or by the fact that a model generated the file.
