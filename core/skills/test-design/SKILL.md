---
name: test-design
description: Derive proportional falsifiable checks from a change's risks and externally visible contracts.
---

# Test Design

Load when behavior, persistence, integration, or a regression needs a test strategy. Skip a separate test-design exercise for a trivial, reversible documentation or formatting edit with no behavior risk; still perform required project checks.

1. List plausible failure modes and affected contracts, then map each risk to an assertion that would fail if the behavior were wrong. Follow project workflow, source authority, validation profile, and existing test conventions.
2. Establish expected results from an accepted contract, historical behavior, independent reference, or justified invariant before deriving assertions from the new implementation. Prefer externally visible behavior, historical fixtures, round trips, and boundary cases. Avoid assertions that repeat the implementation's own formula or merely check that a fixture contains the expected wording.
3. Choose the smallest useful set of unit, integration, property, or manual checks based on blast radius. Include the relevant consumer or entry point when isolated units cannot demonstrate the requested result. Where practical and permitted, confirm that a controlled wrong result or disabled wiring makes the check fail; do not run untrusted mutation commands without required isolation. Reuse installed project libraries and infrastructure; do not install a new testing library automatically.
4. Exercise the relevant failure path and report what was actually run. Mark platform, environment, or unavailable checks as limits, never as passes. Broaden only for a concrete remaining risk or required gate.

Stop when material failure modes have sufficient coverage or remaining checks require unavailable evidence. Output: a risk-to-assertion map, chosen or omitted checks with reasons, fresh results, and unresolved coverage, including any runtime or platform property the checks cannot prove. Use the canonical validation and review procedures for execution and readiness.
