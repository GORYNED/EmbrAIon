# Localization Strategy

English documentation under `docs/` is the canonical and complete public documentation for the current EmbrAIon release.

Localized material is maintained in tiers so translations do not pretend to be complete when they are not.

## Current policy

- **English** — canonical, complete, and release-authoritative.
- **Russian** — primary maintained translation for the product overview and core runtime/configuration concepts.
- **Simplified Chinese, Spanish, and Hindi** — curated translated subsets. Their index pages link only to pages that actually exist and point readers to canonical English documentation for newly added capabilities.

A translated page must not invent a different contract. When it disagrees with current English documentation or machine-readable schemas, the English canonical documentation and schemas control.

## When English documentation changes

A documentation PR should ask:

1. Is this a user-facing contract change or only wording?
2. Does the Russian primary translation need a matching update?
3. Do curated localization indexes still link only to existing pages?
4. Should the other translated subsets gain the new topic now, or explicitly continue pointing to English?

Do not add placeholder links to translations that do not exist.

## Terminology

Technical identifiers such as command names, file paths, route classes, data classes, schema keys, and host names should normally remain unchanged inside localized prose.

Examples:

- `.embraion/routing.yaml`
- `bounded-write`
- `CONFIDENTIAL`
- `embraion validation run`

Translate the explanation, not the executable identifier.

## Completeness claims

Localized indexes should clearly say when they are a subset.

Do not describe a partial translation as the complete documentation for a release.

## Contributing translations

Prefer updating the canonical English page first, then translate from that reviewed state. Keep links relative and verify that every linked localized page exists.

The strict documentation build validates the canonical MkDocs site. Repository validation additionally checks localization contracts, but human review remains responsible for semantic translation quality.
