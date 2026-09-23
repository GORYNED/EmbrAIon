# Changelog

## Unreleased

## 0.2.1 - 2026-09-23

### Fixed

- `embraion doctor` no longer treats an arbitrary non-project working directory as a project root.
- Running `doctor` from a home directory or other ordinary folder now performs framework/installation diagnostics only and skips recursive security scanning, MCP inventory writes, and worktree inspection.
- Project-level diagnostics still run when the current directory is inside a Git repository or an explicit EmbrAIon project containing `.embraion/project.yaml`.

## 0.2.0 - 2026-09-23

### Added

- Project-aware CLI runtime resolver that reads the nearest `.embraion/project.yaml`, caches exact pinned releases in isolated virtual environments, and delegates ordinary commands to the pinned EmbrAIon version.
- Automatic compatibility handling for legacy `0.1.0-dev` project pins by resolving them to the published `0.1.0` distribution.
- Release preparation from a validated `release: vX.Y.Z` commit while preserving tag-only PyPI Trusted Publishing.

### Changed

- Package, framework, and CLI version declarations are aligned at `0.2.0`.
- `embraion init` and `embraion update` write the active global CLI distribution version into the project overlay.
- Installation documentation now explains one global launcher per machine plus isolated per-project pinned runtimes.
- Core concept names in localized README files link to canonical directories, and external products link to official sources.

## 0.1.0 - 2026-09-23

### Added

- First public EmbrAIon release.
- PyPI Trusted Publishing through GitHub Actions and the protected `pypi` environment.
- Standalone wheel and source distributions for installation without cloning the repository.
- Codex, GitHub Copilot, Claude Code, Portable, and source release archives.
- English, Russian, Simplified Chinese, Spanish, and Hindi README/documentation coverage.
- MIT licensing plus separate trademark and brand-assets policy.

### Changed

- Public installation uses the PyPI package through `pipx install embraion`.
