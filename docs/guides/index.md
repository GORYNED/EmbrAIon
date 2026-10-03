# Use & Automate

This section covers the normal engineering lifecycle after EmbrAIon is configured.

## Choose your path

- **I just want the daily workflow:** ask for the outcome → validate → review → merge.
- **I want deterministic delivery controls:** learn validation evidence, structured runs/review, and optional merge enforcement.

## Everyday path

1. [Daily Workflow](daily-workflow.md)
2. [Validation & Evidence](../validation.md)
3. [Troubleshooting](troubleshooting.md)

## Engineering controls

- [Runs & Review](runs-review.md)
- [Enforcement](enforcement.md)
- [Engineering skills](engineering-skills.md)
- [Live skill evaluations](skill-evals.md)
- [Task continuity](task-continuity.md)
- [Knowledge maintenance](knowledge-maintenance.md)
- [Optional Unity capabilities](unity-capabilities.md)

Structure checks are incremental: [code organization](../configuration/organization.md) reports new violations in changed files without treating old debt as a waiver. External capability declarations remain separate from proof of host loading or tool execution; see [external capabilities](../configuration/capabilities.md).

!!! note
    Validation and enforcement execute real checks. Generated host instructions guide the AI client but do not replace host-native security boundaries.
