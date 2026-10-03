# Knowledge maintenance

Declare source relationships in optional `.embraion/knowledge-maintenance.yaml`:

```yaml
documents:
  - id: architecture
    path: docs/architecture.md
    sources:
      - src/app.py
```

Paths must be project-relative regular files. A document can name multiple source files. `observed-version` may be supplied when an external source version has actually been observed; without it, external version drift remains unknown. No date or review state is inferred from file timestamps.

Run the explicit `snapshot_knowledge(project=...)` Python API after reviewing the declared relationships. It stores only paths, hashes, IDs, optional observed version, and baseline time in ignored `.embraion/state/knowledge-audit/baseline.json`. `audit_knowledge(project=...)` reads this baseline and reports `current`, `needs-review`, `missing`, or `unconfigured`. Changes to a source file, document, observed version, or configuration call for review. An audit does not rewrite documentation, create a new baseline, or promote learning output. A new snapshot replaces the baseline only when explicitly requested after review.

The existing selective context and learning workflows remain separate. Context hashes show which knowledge was selected for a task; the audit compares declared documents with their sources. Learning candidates remain advisory until the established governance process promotes them. No recurring schedule is created by this feature.
