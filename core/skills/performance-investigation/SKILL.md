---
name: performance-investigation
description: Investigate a measurable performance concern against a comparable workload and target environment.
---

# Performance Investigation

Load for a performance regression, optimization request, or performance acceptance target. Skip when there is no performance question; do not benchmark every ordinary code change by default.

1. Define the user-visible metric, target or budget, workload, input sizes, warm-up state, and relevant environment. Record platform, build/configuration, CPU or GPU, memory and garbage-collection settings, and measurement tool as applicable.
2. Capture a reproducible baseline before changing code. Use repeated samples and distributions or ranges when variance matters; save raw or traceable measurements, not only a single favorable number.
3. Profile the representative path and separate measured bottlenecks from hypotheses. Change one bounded cause at a time while preserving correctness and project contracts.
4. Re-run the same workload and environment, compare distributions against the target, and run affected correctness checks. Measure on the actual target platform when making a target-platform claim; an Editor or development-machine result cannot establish Player or production performance.

Output: benchmark setup, baseline and candidate samples, profiler evidence, correctness evidence, interpretation, uncertainty, and any untested target. Follow canonical routing, privacy, validation, and review contracts.
