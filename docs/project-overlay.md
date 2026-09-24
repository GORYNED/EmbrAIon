# Project Overlay

A consuming repository opts into EmbrAIon through files under `.embraion/`. `project.yaml` keeps framework/project identity plus validation/agents/capabilities, `knowledge.yaml` owns project knowledge references, `policy.yaml` owns sources/review/privacy policy, and `routing.yaml` owns optional host routing overrides.

The project configuration currently records:

- `project.yaml` — declared EmbrAIon repository/version, project identity, validation profiles, project-specific agents, and local capabilities;
- `knowledge.yaml` — project knowledge paths plus optional data class, trust, role, and trigger metadata;
- `policy.yaml` — canonical/protected/generated/external source patterns, substantial-review policy, and default privacy class;
- `routing.yaml` — optional host model/effort/options overrides;

Project configuration may add stricter rules but must not silently weaken Core hard gates.

## Project knowledge

Project knowledge references live in `.embraion/knowledge.yaml`:

```yaml
project: knowledge/project.md
architecture:
  path: knowledge/architecture.md
  data-class: PRIVATE
  trust: project
  roles:
    - architect
  triggers:
    - architecture
```

Context selection reads only this dedicated file. Knowledge content itself remains in ordinary project files; EmbrAIon stores references and selection metadata here.

## Project policy

Project safety policy lives in `.embraion/policy.yaml`:

```yaml
sources:
  canonical: []
  protected: []
  generated: []
  external: []

review:
  substantial-required: true

privacy:
  default-class: PRIVATE
```

This file is the project-owned source for source classification boundaries, substantial-review requirements, and the default data class.

## Routing configuration

Model-agnostic routing overrides live in `.embraion/routing.yaml`, separate from project identity and the remaining project policy. EmbrAIon does not require a model catalog. Without an override, a route uses the selected host's default/automatic model policy.

When a user wants explicit routing, their AI client edits the dedicated routing file:

```yaml
overrides:
  codex:
    routes:
      complex:
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
