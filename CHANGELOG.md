# Changelog

## Unreleased

### Added

- Project-aware CLI runtime resolver that reads the nearest `.embraion/project.yaml`, caches exact pinned releases in isolated virtual environments, and delegates commands to the pinned EmbrAIon version.
- Automatic compatibility handling for legacy `0.1.0-dev` project pins by resolving them to the published `0.1.0` distribution.

- PyPI Trusted Publishing release path through GitHub Actions and the protected `pypi` environment.
- Standalone wheel/sdist release artifacts for installation without cloning the repository.

- Full Hindi and Spanish localization for the main README, documentation, and trademark policy.
- Localization completeness validation now covers Russian, Simplified Chinese, Hindi, and Spanish.

- Standard MIT License for EmbrAIon source code and documentation.
- Canonical trademark and brand-assets policy.
- Russian and Simplified Chinese informational translations of the brand policy.
- Localized licensing documentation.

### Changed

- Main development version advanced to `0.2.0.dev0` and package, framework, and CLI version declarations are now kept aligned.
- `embraion init` and `embraion update` write the active CLI distribution version into the project overlay.

- README installation guidance now uses the published PyPI package, with explicit Windows and macOS setup, per-machine installation, per-project activation, and upgrade instructions.
- Core concept names in the main localized README files now link directly to their canonical capability directories, while supported AI clients link to their official product pages.

- Package version prepared for the first public `v0.1.0` release.

- Framework and Python package metadata now declare MIT licensing.
- Main and brand README files now make the brand-assets exclusion explicit.
