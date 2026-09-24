# Project Overlay

A consuming repository opts into EmbrAIon through `.embraion/project.yaml`.

The overlay records:

- the declared EmbrAIon repository and framework version;
- project identity;
- project knowledge locations;
- project-specific agents;
- external or local capabilities;
- optional host routing overrides.

Project overlays may add stricter rules but must not silently weaken Core hard gates.

## Model-agnostic routing overrides

EmbrAIon does not require a model catalog in the project. Without an override, a route uses the selected host's default/automatic model policy.

When a user wants explicit routing, their AI client can edit only the relevant override:

```yaml
routing:
  overrides:
    codex:
      routes:
        strong-high:
          model: any-host-model-selector
          effort: high
      roles:
        reviewer:
          model: any-review-model-selector
```

Selectors are opaque host-owned strings. Role overrides are applied over route overrides. These settings affect model selection only; they cannot expand privacy, access, protected-source, validation, or review permissions.

## Version pinning and resolution

Ordinary commands find the nearest `.embraion/project.yaml`, read `framework.version`, and compare it with the global launcher version.

When the project pin differs from the launcher, EmbrAIon prepares an isolated runtime under:

```text
~/.embraion/versions/<version>/
```

and installs the exact published `embraion==<version>` distribution there. The command is then delegated to that runtime.

A single machine can therefore use one current launcher while different repositories remain reproducibly pinned to different EmbrAIon releases.

Launcher-owned setup and inspection commands intentionally avoid unnecessary delegation where appropriate. In particular, `init`, `update`, `status`, cache management, and help remain available from the current launcher.

## Creating and updating a pin

```bash
embraion init
```

writes the active launcher version into a new project overlay.

```bash
embraion update
```

updates only the current project's pin. An explicit version can be selected with:

```bash
embraion update --framework-version <published-version>
```

Setting `EMBRAION_HOME` is an explicit development override and disables automatic version delegation for that process.

## Ownership

The consuming repository remains the source of truth for its product specification, architecture, compatibility contracts, validation evidence, domain semantics, and project-specific knowledge.
