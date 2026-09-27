# Localization

English is the **original, canonical, and release-authoritative** EmbrAIon documentation.

Russian is the only maintained translation. The public documentation site builds both languages from the same navigation and exposes a language switcher.

## Policy

- **English (`en`)** — original source and canonical contract.
- **Russian (`ru`)** — complete maintained translation of every public documentation page.
- No other public documentation languages are maintained.

Technical identifiers stay unchanged inside Russian prose when translating them would make commands or configuration ambiguous. Examples include `.embraion/routing.yaml`, `bounded-write`, `CONFIDENTIAL`, and `embraion validation run`.

## File structure

The site uses the suffix structure from `mkdocs-static-i18n`:

```text
docs/
├── index.md
├── index.ru.md
├── configuration/
│   ├── policy.md
│   └── policy.ru.md
└── ...
```

English files keep their normal `.md` names. Russian translations use `.ru.md`.

## Completeness

Every canonical English Markdown page under `docs/` must have a matching Russian `.ru.md` page.

The build uses `fallback_to_default: false`, and repository validation checks translation parity so an untranslated Russian page is not silently replaced by English.

## Contribution workflow

1. Update the English source first.
2. Update the matching Russian translation in the same PR.
3. Keep technical identifiers, commands, paths, schema keys, and host names exact.
4. Run the strict documentation build and `embraion validate`.
5. Review both language versions before merge.

When English and Russian differ in meaning, the English source and machine-readable framework contracts remain authoritative.
