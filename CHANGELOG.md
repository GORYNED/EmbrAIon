# Changelog

## Unreleased

### Added

- Complete Minimal, Python, and Unity/C# reference projects under `examples/`.
- Deterministic consuming-project lifecycle E2E covering project status, diagnostics, all host projections, overwrite protection, forced regeneration, and clean `init` bootstrap.
- A dedicated wheel-backed Reference Projects E2E CI job that runs outside the source checkout.
- Validation for project-overlay schema, canonical repository/version alignment, and reference-project knowledge paths.

### Changed

- The canonical project-overlay template now tracks the active EmbrAIon framework version.
- Reference project manifests are version-locked to the active EmbrAIon framework and release validation fails on drift.

## 0.3.2 - 2026-09-23

### Changed

- Help now renders the EmbrAIon version and product name on one line: `EmbrAIon X.Y.Z — AI-First Engineering System`.

## 0.3.1 - 2026-09-23

### Added

- `embraion help` as a launcher-owned alias for the top-level command catalog.
- `embraion help <command>` and nested forms such as `embraion help cache prune` for command-specific help.

### Changed

- Top-level help is now organized into Project & setup, Health & runtime, AI execution, Engineering controls, Help, Examples, and More sections.
- Every top-level command and nested command now exposes a concise description of what it does and what it provides.
- Top-level `-h` / `--help` is launcher-owned, so the latest help catalog remains available inside projects pinned to older EmbrAIon runtimes.

## 0.3.0 - 2026-09-23

### Added

- Cross-platform compatibility CI across Linux, Windows, and macOS on Python 3.11 and 3.14.
- Network-backed end-to-end validation that a newer global launcher installs, delegates to, and reuses an exact older project-pinned EmbrAIon release.
- `embraion status` with both human-readable and `--json` output for launcher version, project pin, resolved runtime, runtime cache, and detected host projections.
- `embraion cache list` and conservative `embraion cache prune` commands for inspecting and cleaning invalid, stale, or explicitly old cached runtimes.

### Changed

- Release tag creation now waits for the cross-platform compatibility matrix before publishing a release.
- Runtime cache markers are touched when reused so optional age-based pruning can use last-use time.
- First-use pinned-runtime installation keeps pip output out of command stdout so delegated CLI output remains machine-safe and predictable.
- Human-readable diagnostic status markers use ASCII labels (`[OK]`, `[WARN]`, `[ERROR]`) for reliable Windows code-page and redirected-output compatibility.

## 0.2.2 - 2026-09-23

### Changed

- `embraion doctor` now prints a concise human-readable diagnostic report by default.
- Machine-readable structured output remains available through `embraion doctor --json`.
- The doctor exit-code contract is unchanged, so CI and automation can continue to use it safely.

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
