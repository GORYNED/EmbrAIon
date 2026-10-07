# Runtime & Version Resolution

EmbrAIon separates the **global launcher version** from the **framework release pinned by each project**.

## One launcher, multiple project pins

A project records its framework contract in:

```text
.embraion/project.yaml
```

A v0.14+ project pin can include the exact published wheel identity and its verified SHA-256 digest:

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: 0.16.0
  artifact:
    schema: 1
    source: github-release
    release: v0.16.0
    asset: embraion-0.16.0-py3-none-any.whl
    digest: sha256:<64-lowercase-hex>
```

The artifact lock is framework-owned. Consumer CI does not need a separate wheel URL, hardcoded checksum variable, or custom checksum parser.

Older version-only manifests remain valid. The next successful `embraion update` upgrades them automatically and materializes the lock; no manual migration is required.

Ordinary commands locate the nearest project and resolve its pin:

![Runtime and version resolution](../assets/diagrams/en/07-runtime-version-resolution.svg){ loading=lazy }

If the pin differs from the launcher version, EmbrAIon installs the exact pinned distribution into an isolated cache:

```text
~/.embraion/versions/<version>/
```

For locked projects, the runtime resolver downloads the exact release asset from the canonical GitHub release URL, verifies its SHA-256 digest **before** pip installs it, and records the artifact identity in the runtime marker. A cached runtime is reusable only when its recorded artifact identity and digest match the project lock.

Different repositories can therefore remain on different EmbrAIon releases on the same machine.

## Update, verify, install

Upgrade the global launcher first, then update the project:

```bash
pipx upgrade embraion
cd MyProject
embraion update
```

`embraion update` targets the installed launcher version. Before changing the project pin it resolves the canonical GitHub Release, requires exactly one expected wheel asset, requires GitHub's server-side `sha256:` digest, validates the release tag / asset name / URL, and validates the candidate project configuration.

The manifest write is the update commit point: `framework.version` and `framework.artifact` are replaced together in one atomic YAML write. Missing release metadata, a missing artifact, a malformed digest, or incompatible project configuration fails closed before the pin changes.

To verify the locked release artifact without installing it:

```bash
embraion framework verify
```

To install the exact digest-verified release into the isolated runtime cache:

```bash
embraion framework install
```

Both commands read only the project pin/lock for artifact identity. They do not require consumer-owned checksum logic.

## Consumer CI

GitHub Actions workflows can use the reusable setup action instead of their own setup step and pin reader:

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0  # history for --base-ref
  - uses: GORYNED/EmbrAIon/actions/setup@v<release>
    with:
      python-version: "3.13"  # optional, the default
      project-path: .         # optional, a directory at or below the project root
  - uses: GORYNED/EmbrAIon/actions/check@v<release>
```

The `check` action runs `embraion framework install` for a locked pin and then `embraion check`, so the workflow carries no project flags: the organization modes, security threshold and scan scope come from the `check` section of `.embraion/policy.yaml` (see [Check options](../configuration/policy.md#check-options)). It takes `project-path` (default `.`, the project root or a directory below it), `base-ref`, `upload-evidence` (default `false`), and `evidence-retention-days` (default `14`). With `upload-evidence: "true"` it uploads `.embraion/state/validation/` of the project root, which it resolves the way `embraion check` does, as a workflow artifact with a run-unique name, also when a check fails. That directory holds the evidence of the validation profiles that `check.validation-profiles` runs. It is hidden, so the action uploads hidden files. When no profile ran, the upload step warns that no files were found. **The artifact carries the full output of the profile commands**, so anything those commands print is stored with the run; keep `upload-evidence` off for sensitive output and lower `evidence-retention-days`. Locating the artifact never fails the action. Without `base-ref` it compares against `origin/<base branch>` on pull requests; elsewhere checks that need a base ref are reported as not run. It expects EmbrAIon to be installed by the setup action first and has no `python-version` input. `embraion check` runs every check the project configuration selects; see the [CLI reference](cli.md#embraion-check).

The action sets up Python, reads `.embraion/project.yaml` with the same reader as `embraion framework pin`, and installs exactly the pinned release. With an artifact lock it downloads the canonical release wheel and verifies its SHA-256 before pip installs it; without a lock it installs `embraion==<version>`. It then confirms the installed version. A missing or inexact pin, a mismatched lock, or a digest mismatch fails the step. Outputs: `version` and `digest` (empty without a lock).

The action ref selects only the bootstrap code. The installed release always comes from the project pin, so `embraion update` takes effect without a workflow edit; move the ref only to adopt newer bootstrap behavior. The pin reader runs from the action's own release in an isolated environment with PyYAML only, and project text cannot issue workflow commands to the log. The steps use `bash` and are written for Linux and macOS runners; Windows runners are not covered. Commands in a locked project still run from the digest-bound runtime cache described above.

Other CI systems can follow the same contract: `embraion framework pin` prints `version=` and `digest=` lines and fails on an inexact pin. `embraion enforcement install` generates a workflow that uses the action.

## Inspect resolution

```bash
embraion status
embraion status --json
```

The status report shows the launcher, project pin, resolved runtime, cache state, and whether the project has an artifact lock and digest.

## Cache management

```bash
embraion cache list
```

Dry-run pruning:

```bash
embraion cache prune --older-than 90
```

Apply intentionally:

```bash
embraion cache prune --older-than 90 --apply
```

The active launcher and current project's resolved runtime are protected from age-based pruning.

## Moving to a different specific release

Install that launcher version first, then run `embraion update` from the project. Configuration normalization and artifact-lock generation are owned by the same release contract that will be written.

## Development override

`EMBRAION_HOME` selects an explicit framework checkout for framework development. Automatic version resolution can also be disabled intentionally with `EMBRAION_DISABLE_VERSION_RESOLUTION=1`.

Resolver-owned `EMBRAION_VERSION_RESOLVED`, `EMBRAION_RESOLVED_VERSION`, `EMBRAION_RESOLVED_PROJECT`, and the resolver's `EMBRAION_HOME` apply only to the delegated interpreter. Validation and other independent child commands receive a clean environment and resolve their own project. An explicit user development override remains inherited. Cached runtime installation, probes, and delegation also exclude `PYTHONPATH` so checkout imports cannot replace the locked distribution.

The framework repository is itself an EmbrAIon project. Its pin and artifact lock stay on the latest published stable release while source development advances. From a checkout, use `python tools/source.py <command>` for source CLI operations and `python tools/source.py test unit` or `test integration` for source tests. The runner selects checkout code and data, removes inherited resolver state, and uses the local `.venv` when present; otherwise the current Python must have the framework dependencies installed. Source CLI commands retain the repository's project overlay and routing. Repository validation profiles and source CI steps use this entry point; installed-package checks outside the checkout continue to use the packaged CLI.

Both test commands accept `--jobs N` or `--jobs auto` (the CPU count, at most 4). With more than one job, test modules run in separate worker processes that take modules from a shared queue, largest files first. Each process uses its own temporary directory (`TMPDIR`, `TEMP`, and `TMP`). The command prints one summary per process and a combined total, keeps the failure output, and exits non-zero if any process fails or if the number of tests run differs from the number discovered. Without `--jobs`, with `--jobs 1`, and with `--jobs auto` on a one-CPU machine, the tests run in one process exactly as before. A worker that exits with a non-zero status counts as crashed even if it wrote a result. Modules that cannot share a machine with parallel processes may be named in `SEQUENTIAL_MODULES` in `tools/parallel_tests.py`; they then run in the parent process after the parallel phase. The list is empty at present.

Isolation audit of the parallel runner, from reading the code and searching the tests for shared state. Tests use no fixed ports (servers bind port 0). Tests that write under `build/` use unique temporary directories or `mkdir(exist_ok=True)`. Tests that create projects or checkouts use temporary directories. The CLI tests that start `embraion` as a subprocess set `EMBRAION_CACHE_HOME` to a temporary directory or turn version resolution off, so they do not touch the user's runtime cache. Code that reads `~/.codex`, `~/.claude`, or `~/.agents/skills` only reads. One test writes shared state: `test_clean_project_bootstrap_and_update` in `tests/integration/test_reference_projects.py` calls `update_project` in the test process. That installs the runtime for pin 0.8.1 into the real runtime cache (`~/.embraion/versions/`, changed by `EMBRAION_CACHE_HOME`) and fills the pip cache. It is the only module that does this, and the unit and integration suites run one after the other, so no two processes write there at the same time. A new test that writes to the runtime cache, the user's home, a fixed path, or a fixed port must set its own location, or be named in `SEQUENTIAL_MODULES`.
