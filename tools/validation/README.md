# Validation

Deterministic framework validators belong here.

Validation should cover:

- schema validity;
- capability catalog references;
- duplicate or missing capability IDs;
- broken relative paths;
- skill directory / `SKILL.md` consistency;
- adapter route references to known models;
- generated projection drift;
- project-overlay compatibility.

Behavioral adherence that cannot be proven deterministically belongs in `evals/`, not here.

<sub>Last updated: 2026-09-23 19:21 UTC</sub>
