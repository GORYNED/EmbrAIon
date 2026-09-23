# Validation

Validation is evidence that a framework change preserves intended contracts.

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
