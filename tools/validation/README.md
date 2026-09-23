# Validation

The executable validation command is:

```bash
embraion validate
```

It checks:

- JSON/YAML syntax;
- framework, catalog, agent, model, and eval schemas;
- capability catalog paths and duplicate IDs;
- skill directory and `SKILL.md` consistency;
- adapter routes referencing known models;
- English/Russian/Chinese documentation parity;
- required README timestamps;
- migration guards such as obsolete privacy or adapter names.

Behavioral adherence that cannot be proven deterministically belongs in `evals/`.

<sub>Last updated: 2026-09-23 20:05 UTC</sub>
