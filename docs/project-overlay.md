# Project Overlay

A consuming repository opts into EmbrAIon through `.embraion/project.yaml`.

The overlay records:

- the declared EmbrAIon repository and framework version;
- project identity;
- project knowledge locations;
- project-specific agents;
- external capabilities.

Project overlays may add stricter rules but must not silently weaken Core hard gates.

## Automatic version resolution

The current public `v0.1.0` release records a project version but does not resolve it automatically. Current `main` implements the resolver for the next release.

For ordinary commands, the global launcher finds the nearest `.embraion/project.yaml`, reads `framework.version`, and compares it with the launcher version. When they differ, EmbrAIon prepares an isolated runtime under `~/.embraion/versions/<version>/` and installs the exact `embraion==<version>` PyPI distribution there.

The cached runtime is then used for the command. A single machine can therefore have one global launcher while different repositories remain pinned to different EmbrAIon releases.

`embraion init` and `embraion update` intentionally bypass project delegation:

- `init` writes the active global launcher version into a new project overlay;
- `update` changes only the current repository's pin;
- an explicit `--framework-version` selects a specific release.

Legacy `0.1.0-dev` pins written by the first release are normalized to the published `0.1.0` distribution.

Setting `EMBRAION_HOME` is an explicit development override and disables automatic version delegation for that process.

The project repository remains the canonical source for its product specification, architecture, compatibility contracts, validation evidence, and domain semantics.
