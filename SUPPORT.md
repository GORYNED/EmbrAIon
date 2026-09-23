# Support and Compatibility Policy

EmbrAIon is currently pre-stable. The public compatibility contract is intentionally stricter for patch releases than for minor releases before 1.0.

## Supported platforms

The supported operating-system families are:

- Windows
- macOS
- Linux

## Supported Python

EmbrAIon requires Python **3.11 or newer**.

Compatibility CI validates:

- Python 3.11 as the minimum supported version;
- the selected current latest Python 3 release used by the project CI, currently Python 3.14.

Intermediate supported Python 3 versions are expected to work when they satisfy package dependencies, but the release gate focuses on the minimum and selected latest versions.

## Version compatibility before 1.0

### Patch releases: `0.x.y`

Patch releases are intended for bug fixes, documentation improvements, diagnostics, compatibility fixes, and other changes that should not require a project migration.

### Minor releases: `0.x.0`

Before 1.0, minor releases may intentionally evolve:

- CLI behavior;
- schemas and contracts;
- generated host projections;
- routing metadata;
- framework structure;
- installation or runtime behavior.

Release notes should describe material migration or compatibility impact.

## Project pinning

Each consuming project may pin its EmbrAIon framework version in `.embraion/project.yaml`.

The global launcher may be newer than the project runtime. EmbrAIon resolves the project's exact published runtime when needed, allowing older projects to remain reproducible while upgrades are performed intentionally.

## What support covers

Public Issues are appropriate for:

- reproducible bugs;
- supported-platform compatibility problems;
- feature requests;
- documentation problems.

Security vulnerabilities must be reported privately according to [SECURITY.md](SECURITY.md).

## Out of scope

Support is not guaranteed for:

- Python versions below 3.11;
- modified or repackaged EmbrAIon distributions that change canonical Core behavior;
- third-party provider/service outages;
- unsupported operating systems;
- unpublished source snapshots treated as production releases.

## Stable compatibility

The long-term stable compatibility contract will be formalized before EmbrAIon 1.0.
