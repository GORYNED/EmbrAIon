# Runtime & Version Resolution

EmbrAIon separates the **global launcher version** from the **framework version pinned by each project**.

## One launcher, multiple project pins

A project records its exact framework release in:

```text
.embraion/project.yaml
```

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: <published-version>
```

Ordinary commands locate the nearest project and resolve its pin:

```text
global embraion launcher
        ↓
nearest .embraion/project.yaml
        ↓
framework.version
        ↓
matching project runtime
```

If the pin differs from the launcher version, EmbrAIon can install the exact published distribution into an isolated cache:

```text
~/.embraion/versions/<version>/
```

Different repositories can therefore remain on different EmbrAIon releases on the same machine.

## Inspect resolution

```bash
embraion status
embraion status --json
```

The status report shows the launcher, project pin, resolved runtime, cache state, and detected host projections.

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

## Updating a project

The safe sequence is:

```bash
pipx upgrade embraion
cd MyProject
embraion update
embraion doctor
```

`embraion update` is launcher-owned. Safe configuration normalization targets the **installed launcher version only** so the current runtime does not guess the schema/defaults of another release.

It may add compatible missing defaults and update the project pin while preserving project-owned values. It validates all candidate canonical `.embraion/` files before writing any of them.

It does not silently refresh host projections.

## Moving to a different specific release

Install that launcher version first, then run `embraion update` from the project. This keeps configuration normalization owned by the same release contract that will be written.

## Development override

`EMBRAION_HOME` selects an explicit framework checkout for framework development. Automatic version resolution can also be disabled intentionally with `EMBRAION_DISABLE_VERSION_RESOLUTION=1`.
