# Evals

`evals/` measures AI-First behavior that ordinary deterministic tests cannot fully prove.

Use evals to answer questions such as:

- Did the Reviewer remain read-only?
- Did the Worker stay inside owned paths?
- Did compatibility risk trigger the Steward?
- Did privacy filtering block an ineligible external route?
- Did debugging investigate a cause before proposing a fix?
- Did verification refuse to claim completion without required evidence?
- Did a routing or workflow change improve outcomes without unacceptable cost or regression?

## Structure

cases / graders / fixtures / baselines / reports

Baselines capture comparable reference metrics. Reports compare candidate behavior against an applicable baseline.

Useful metrics may include success rate, first-pass success, retry count, fallback count, escalation count, validation pass rate, review findings, wall time, and API/token usage where available.

Evals are not substitutes for unit or integration tests. They evaluate behavioral adherence and routing quality.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
