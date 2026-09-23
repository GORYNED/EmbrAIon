# Minimal Reference Project

This is the smallest complete consuming-project example.

It contains:

- a pinned `.embraion/project.yaml`;
- one project knowledge document;
- no product-specific code;
- no committed generated host projections.

From this directory:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

Generated host files are disposable. CI recreates them in a temporary copy and verifies overwrite protection and forced regeneration.

<sub>Last updated: 2026-09-23 23:55 UTC</sub>
