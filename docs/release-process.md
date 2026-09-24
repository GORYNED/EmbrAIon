# Release Process

EmbrAIon uses versioned framework releases published from validated release commits.

## Contract

- GitHub `main` is the upstream source of truth.
- Stable releases use immutable `vX.Y.Z` tags.
- Python distributions are published to PyPI through Trusted Publishing.
- GitHub Releases include source plus Codex, Copilot, Claude Code, and Portable artifacts.
- New projects bootstrap from a published framework version.
- Existing projects pin a version in `.embraion/project.yaml`.
- The global launcher resolves exact published pins into isolated per-version runtimes.
- Project upgrades are intentional and are performed with `embraion update`.

## Release gate

A release commit uses the exact message:

```text
release: vX.Y.Z
```

Before the tag is created, CI validates:

- Linux, Windows, and macOS compatibility;
- minimum and selected latest Python versions;
- framework validation;
- unit and integration tests;
- project resolver E2E;
- packaged reference-project E2E;
- security scanning;
- behavioral eval smoke;
- generation of host projections;
- strict documentation build.

Only after those checks pass does the workflow create the immutable release tag and dispatch the tagged build.

The tagged build validates the version/tag contract again, builds distributions and release archives, creates the GitHub Release, and publishes Python distributions to PyPI.

## Pre-1.0 compatibility

Patch releases are intended for compatible fixes and improvements. Minor releases may intentionally evolve framework contracts. Project pinning allows upgrades to remain explicit.
