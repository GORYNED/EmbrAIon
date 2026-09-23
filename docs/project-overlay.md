# Project Overlay

A consuming repository opts into EmbrAIon through `.embraion/project.yaml`.

The overlay records:

- the declared EmbrAIon repository and framework version;
- project identity;
- project knowledge locations;
- project-specific agents;
- external capabilities.

Project overlays may add stricter rules but must not silently weaken Core hard gates.

## Current v0.1.x version behavior

`embraion init` writes the framework version exposed by the currently running EmbrAIon installation into `.embraion/project.yaml`.

The current `v0.1.x` implementation does not automatically resolve that recorded version when later running `install` or `sync`. Those commands generate from the framework data available to the currently running CLI. The version field is therefore a project compatibility declaration and intentional update boundary, not yet a per-project runtime resolver.

For exact reproducibility, run the CLI/framework distribution that matches the version recorded by the project.

The project repository remains the canonical source for its product specification, architecture, compatibility contracts, validation evidence, and domain semantics.
