# Release Process

EmbrAIon will use versioned framework releases.

The intended contract is:

- GitHub is the source of truth.
- Framework releases are tagged and documented.
- New projects bootstrap from a released version.
- Existing projects pin a framework version in `.embraion/project.yaml`.
- The global launcher resolves exact published pins into isolated per-version runtimes cached under `~/.embraion/versions/`.
- Updates occur intentionally with release notes and validation; `embraion update` changes only the current project's pin.

The repository is currently pre-stable; the release process will be hardened before the first stable version.
