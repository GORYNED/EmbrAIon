# Project Overlay

A consuming repository connects to EmbrAIon through `.embraion/project.yaml`.

The overlay identifies:

- the pinned EmbrAIon version;
- project identity;
- project knowledge locations;
- project-specific agents;
- external capabilities.

Project overlays may add stricter rules but must not silently weaken Core hard gates.

The project repository remains the canonical source for its product specification, architecture, compatibility contracts, validation evidence, and domain semantics.
