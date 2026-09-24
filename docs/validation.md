# Validation

Validation is evidence that a framework or project change preserves intended contracts. Consuming-project validation profiles are declared in `.embraion/validation.yaml` and executed with `embraion validation run <profile>`. Each execution produces redacted structured evidence that can optionally attach to an active EmbrAIon run.

The validation system grows in layers:

- schema validation;
- capability-reference validation;
- adapter/projection parity;
- routing-policy validation;
- installation and doctor checks;
- security and integration inventory checks;
- integration tests;
- behavioral eval comparison against applicable baselines.

A passing result should identify what was checked rather than merely report generic success.

Behavioral improvement is evaluated separately from deterministic correctness. A better aggregate eval score never overrides a hard security, privacy, permission, compatibility, or mutation failure.

## Project validation profiles

Inspect configured profiles:

```bash
embraion validation list
```

Execute fresh project evidence:

```bash
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

Profile commands execute sequentially from the consuming repository root. Results preserve command identity, exit code, duration, redacted output tails, and overall status. Empty profiles are `skipped`; a failing or timed-out command produces a failed profile.

The evidence record is stored beneath `.embraion/state/validation/`, which is local runtime state and ignored by the project-local `.gitignore`.
