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

Before an authorized release merge, complete author self-review, required tests/CI and the independent host-native Reviewer cycle. Reviewer explicitly confirms the current full source PR-head SHA after all fixes. Any later candidate change requires renewed confirmation. User merge and release authorization remain separate gates; Copilot Review is not required. The resulting squash commit has a new SHA and triggers the automated checks below.

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
- Core assignment routing and capability-aware Codex, Copilot, Claude Code, and Portable regressions;
- generation of host projections;
- strict documentation build.

Only after those checks pass does the workflow create the immutable release tag and dispatch the tagged build.

The tagged build validates the version/tag contract again, builds distributions and release archives, creates the GitHub Release, and publishes Python distributions to PyPI.

## Self-host upgrade

After the GitHub Release passes the consumer artifact lock smoke, the workflow proposes the self-host upgrade: on `main` it runs `embraion update` and then `embraion install` for the Codex (`--config-mode merge`), Copilot, Claude Code and Portable hosts with the released launcher and opens a `chore/self-host-vX.Y.Z` pull request. A pin that is already at or above the release produces no pull request. Pull requests opened with the workflow token do not start `pull_request` workflows, so the job dispatches `validate` and `docs` for the branch. The pull request follows the ordinary review and merge gates and is never merged automatically.

Creating the pull request requires the repository setting that allows GitHub Actions to create pull requests. Without it the job fails after pushing the branch. After enabling the setting, re-run the job: it opens the pull request from the existing branch when the branch holds exactly the result of the run, and otherwise fails so that someone reviews the branch.

Assignment-routing eval fixtures verify grading and regression behavior. They do not claim live native host execution. Native selection evidence must distinguish prepared arguments, capability limitations, handoffs, and applied settings.

## Pre-1.0 compatibility

Patch releases are intended for compatible fixes and improvements. Minor releases may intentionally evolve framework contracts. Project pinning allows upgrades to remain explicit.

## Optional capability changes

The 0.20 optional inventories, organization configuration and knowledge-maintenance bindings are additive. Validate schemas, selected bundle paths, installed wheel resources and every host projection before publication. Run genuine skill evaluation when an authenticated native host is available; report host failures and unavailable evidence explicitly. Deterministic fixtures and fake-host tests do not replace live behavioral evidence or justify claims of improvement. No provider login or credential configuration is installed by a release.
