# Model Routing

EmbrAIon routing is model-agnostic.

Core decides the engineering constraints that should survive model churn:

- role;
- complexity / route class;
- data class;
- access mode;
- owned paths;
- validation and review requirements.

It does **not** maintain a canonical list of current model names.

## Default behavior

Without a project override, routing resolves to `host-default`. The selected host remains responsible for its own available models and automatic/default model policy.

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

A default result therefore has no framework-selected model:

```json
{
  "host": "codex",
  "route": "strong",
  "role": null,
  "resolution": "host-default",
  "model": null,
  "effort": null,
  "options": {},
  "data": "PRIVATE"
}
```

New models can appear in a host without requiring an EmbrAIon release.

## Optional project overrides

A project may override a route or role in `.embraion/project.yaml`:

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
          options:
            thinking: maximum
```

The strings are intentionally open-ended. EmbrAIon validates the structure, not a global model catalog.

Resolution precedence is:

1. role override, when a role is supplied;
2. route override;
3. host default/automatic selection.

A role override is merged over the route override, so a role can replace only the fields it needs.

## AI-First configuration

Every installed host projection includes the reusable `routing-configuration` skill. It tells the AI that model overrides belong in `.embraion/project.yaml` under `routing.overrides`, and that EmbrAIon itself has no model registry.

The intended user experience is therefore conversational rather than manual configuration. A user can simply tell the AI already working in the repository:

> Configure EmbrAIon routing for this repository using the models currently available to you. Keep host-default where no explicit choice is needed. Put any model, effort, or host-specific overrides only in `.embraion/project.yaml` under `routing.overrides`, mapped to the appropriate route classes or roles. Do not weaken privacy, access, ownership, validation, or review policy.

The AI should inspect host-native model choices when available, edit only the relevant override subtree, and verify the affected routes. Users may still edit the YAML directly, but they do not need to.


A user does not need to edit YAML manually. They can ask the AI client already working in the repository to inspect the models/settings available in that client and update the project's EmbrAIon routing overrides.

The AI should change only project overrides. It must not weaken privacy, access, owned-path, protected-source, validation, or review policy to make a model fit.

## What EmbrAIon validates

EmbrAIon can deterministically validate:

- route-class names;
- data-class names;
- project-override structure;
- role/route precedence;
- access and privacy policy that is independent from model identity.

The execution host remains authoritative for whether a particular selector or option is actually available to the current user/account.

This separation keeps Core usable with future models and hosts that did not exist when the current EmbrAIon release was published.
