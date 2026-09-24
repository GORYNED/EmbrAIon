# Changelog

## Unreleased

### Added

- Dedicated `.embraion/routing.yaml` project configuration with its own schema, keeping model/effort/options overrides separate from project identity and policy.
- Model-agnostic project routing overrides by host, route class, and role. Overrides accept opaque host-owned model selectors, effort strings, and options without requiring an EmbrAIon model catalog.
- A projected `routing-configuration` skill that teaches AI clients to write optional model overrides only to `.embraion/routing.yaml` while preserving host-default behavior and Core safety policy.
- A validation invariant that rejects framework-owned model catalogs and adapter route-to-model maps if they are reintroduced.

### Changed

- Routing now resolves to the host's own default/automatic model policy unless a consuming project explicitly overrides it.
- Core route classes are now task-oriented (`bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex`, `critical`) instead of implying model strength or cost tiers.
- Lead and fallback policy no longer own concrete model selection or model-to-model fallback; those remain host-owned unless a project explicitly overrides them.
- Canonical and localized documentation now describe the same model-agnostic ownership model.
- Generated Codex configuration no longer pins a framework-chosen default model or reasoning effort.

### Removed

- Built-in host/provider model catalogs and hardcoded route-to-model mappings. Model availability is owned by the execution host or consuming project rather than EmbrAIon Core.

## 0.7.0 - 2026-09-24

### Added

- Selective host projection adoption through repeatable `--component` flags on `install` and `projection diff`, allowing mature repositories to adopt skills or agents without replacing existing host-owned configuration.
- Project initialization now creates `.embraion/.gitignore` so local runtime state and cache data stay untracked by default.

## 0.6.1 - 2026-09-24

### Added

- Minimal child-process safety helpers for environment allowlisting and stdout/stderr redaction in future execution adapters.

### Fixed

- Projection ownership state now retains obsolete generated entries until clean files are explicitly pruned, so later diff/prune operations remain deterministic even after an install without `--prune`.

## 0.6.0 - 2026-09-24

### Added

- Host-native project Skills projection for Codex, GitHub Copilot, and Claude Code using reusable `SKILL.md` directories.
- Project Overlay v2 contracts for canonical/protected/generated/external source classes, validation profiles, substantial-review policy, and default privacy classification.
- Ownership-aware projection planning with dry-run/diff, generated-file hashes, conflict detection, safe updates, and conservative obsolete-file pruning.
- Selective project-context records with data classification, role/task eligibility, trust/provenance, content hashes, and explicit character budgets without duplicating knowledge contents into state.
- Structured execution evidence records for route choice, access, owned paths, context identity, changed paths, validation, review, outcomes, and residual risk.
- Runtime credential redaction across persisted telemetry and execution state.
- Harness capability audit for generated agents/skills and native hook/enforcement surfaces.

### Changed

- Project initialization now creates Project Overlay v2 safety defaults.
- Re-installing an unchanged generated host projection is idempotent; locally modified or unowned conflicts are refused unless replacement is explicitly forced.


## 0.5.0 - 2026-09-24

### Added

- A full MkDocs Material documentation site with branded navigation, search, dark/light modes, and GitHub Pages deployment.
- Getting Started guides for installation, first-project bootstrap, and intentional project updates.
- Concept guides for agents, skills, knowledge, routing, and project overlays.
- Host guides for Codex, GitHub Copilot, Claude Code, and Portable projections.
- A consolidated CLI reference and walkthroughs for Minimal, Python, and Unity usage examples.
- Open-source documentation pages for contribution, support, security reporting, and governance.
- Deterministic documentation tests covering nav targets, internal links, site assets, CLI command coverage, and the published documentation URL.
- A dedicated documentation workflow that performs strict MkDocs builds on pushes and pull requests and deploys the built site to GitHub Pages from `main`.
- Strict documentation builds in the release preparation and tagged-release gates.

### Changed

- Package metadata and the repository README now point to the public documentation site while preserving Markdown sources in `docs/`.
- Framework, package, template, and reference-project pins are aligned at `0.5.0`.


## 0.4.3 - 2026-09-24

### Fixed

- The Unity reference project now explicitly enables the built-in `com.unity.modules.imgui` module required by `CounterSampleView`.
- Reference-project E2E now verifies that the IMGUI module dependency is present, preventing the sample UI from compiling against a disabled Unity module.

### Changed

- Unity reference documentation now states that IMGUI is a built-in Unity module rather than describing the sample as dependency-free.

## 0.4.2 - 2026-09-24

### Added

- A runnable Unity reference `SampleScene.unity` with a live value display and Increment / Reset controls.
- Stable Unity `.meta` GUIDs and build settings that link the sample scene to its controller and view scripts.
- Structural E2E checks for Unity scene/script/build-settings linkage.

### Changed

- The Unity reference keeps presentation in `CounterSampleView`, lifecycle/state coordination in `CounterController`, and deterministic state in pure C# `CounterState`.
- The sample UI uses built-in Unity IMGUI to stay dependency-free.

## 0.4.1 - 2026-09-23

### Changed

- The Unity reference project now uses the conventional `Assets/Scripts/` layout.
- Reference-project privacy checks no longer encode project-specific identifiers in the public repository; validation stays generic and structural.

## 0.4.0 - 2026-09-23

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
