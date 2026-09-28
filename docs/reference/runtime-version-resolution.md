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
  version: 0.15.2
  artifact:
    schema: 1
    source: github-release
    release: v0.15.2
    asset: embraion-0.15.2-py3-none-any.whl
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
