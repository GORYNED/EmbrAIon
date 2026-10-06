# Evidence

Repository documentation and validation reports must describe observable current state.

Missing checks, unavailable environments, historical evidence, assumptions, and skips must be identified explicitly and never converted into implied passes.

## Reporting checks

- Report a check as passed only when it ran and passed in this session, and name the command or method. Never infer a pass from reading code, a similar earlier run, or a green result on another tree, and never state counts, timings, or output that were not observed.
- Give each required check one outcome: passed, failed, or not run. A skipped check is "not run" with its reason; a missing result is never "no issues found".
- Fresh evidence comes from a run on the final candidate. Historical evidence from another commit or environment carries over only when the later change cannot affect it, with the reason stated; rerun after any change that can. Keep date, commit, and environment next to each result.
- Do not weaken a guard silently. Never loosen or delete a test, validator, lint rule, threshold, or required check to obtain a pass; when a guard is wrong, say so and change it only in the open with the owner's agreement, reported as part of the change.
- Report a blocked or unavailable tool, platform, service, or device with the exact reason. Continue independent work, do not present a different tree or environment as the requested one, and leave missing evidence as an open item.
- Report failures immediately with the output that shows them, fix the cause rather than the symptom, and say with evidence when a failure is unrelated to the change. Report flaky or intermittent results with how often they failed; never hide them.
