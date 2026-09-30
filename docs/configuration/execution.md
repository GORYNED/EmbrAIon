# Execution & Providers

EmbrAIon's provider-neutral execution runtime is an **optional** project capability.

It is separate from ordinary Codex/Copilot/Claude conversations. Use it when a project wants a versioned, bounded request to run through reviewed provider bindings with normalized attempts, failures, health, usage, and cost evidence.

## When you need it

You probably do **not** need `.embraion/execution.yaml` when:

- the AI host itself performs all reasoning/tool work;
- host-default model selection is sufficient;
- the repository only needs project knowledge, policy, agents, routing, validation, and review.

Use executable bindings when the repository needs a controlled external/API lane whose execution contract is owned by the project and EmbrAIon runtime.

## The execution path

```text
execution request
    ↓
candidate deployments
    ↓
project eligibility ceilings
    ↓
execution.yaml binding
    ↓
EmbrAIon adapter
    ↓
provider/model
    ↓
normalized attempt result
    ↓
bounded fallback / handoff
```

The request remains bounded by its original data class, role, task class, source IDs, trust level, access mode, owned paths, timeout, and candidate list. Fallback may choose another predeclared eligible candidate; it does not widen those ceilings.

## Minimal binding shape

```yaml
# .embraion/execution.yaml
schemaVersion: 1

bindings:
  analysis-api:
    adapter: litellm-loopback
    selector: example/example-model
    credentialRef: env:EXAMPLE_API_KEY
    sourceIds:
      - Project
    trustLevels:
      - verified
    taskClasses:
      - substantial
    maxTimeoutSeconds: 300
    expectedProvider: example
    contextBoundary: ProjectContext/v1
```

The matching deployment is declared separately in `.embraion/deployments.yaml`.

Credentials are referenced by name (for example `env:EXAMPLE_API_KEY`). Secret values do not belong in project configuration.

## What a binding can constrain

Depending on the adapter and project, a binding can declare:

- adapter and upstream selector;
- credential reference;
- approved source IDs and trust levels;
- task classes and aliases;
- data-class compatibility aliases;
- timeout and option ceilings;
- expected provider;
- context-boundary identity;
- exact or pattern-based observed model evidence;
- version-tied usage-semantics evidence.

The schema is intentionally project-facing: concrete provider/model facts belong to the project, while the generic execution mechanism remains in Core.

## Canonical data classes and aliases

EmbrAIon Core uses exactly:

- `PUBLIC`
- `PRIVATE`
- `CONFIDENTIAL`

A mature project may have historical vocabulary that it cannot rename immediately. An execution binding can map the Core class to a project-specific capability label:

```yaml
bindings:
  legacy-api:
    adapter: litellm-loopback
    selector: example/example-model
    sourceIds: [Project]
    trustLevels: [verified]
    dataClassAliases:
      CONFIDENTIAL: PROJECT_SECRET
```

This does **not** create a fourth Core data class. The request is still `CONFIDENTIAL`; the alias is a compatibility mapping at the project execution boundary.

Use aliases only when the project really owns legacy vocabulary. New projects should normally use the canonical classes directly.

## Attempts, fallback, and health

EmbrAIon owns the bounded attempt loop for `embraion execute`.

The runtime:

1. validates the versioned request;
2. checks each candidate against project deployment capabilities and execution binding ceilings;
3. evaluates supplied health observations;
4. invokes only a declared adapter/binding;
5. normalizes failure state;
6. records an attempt without persisting raw credentials or prompt/context bytes;
7. falls back only when the normalized failure is eligible and mutation/termination evidence is safe.

Provider billing failures, availability failures, transport failures, timeouts, cancellation, and policy denial remain distinct normalized states.

The adapter should not silently substitute a different model or create an unbounded retry policy behind EmbrAIon's attempt accounting.

## Handoff vs execution

A deployment can be routable but not executable by EmbrAIon.

If a candidate has no executable binding, the runtime can return:

```text
handoff-required
```

That means the selected host/project must take over execution rather than EmbrAIon inventing an unapproved transport.

## Transport completion is not project acceptance

A completed provider call proves that the transport returned a bounded result. It does not prove that the answer is correct for the project.

Projects can still require:

- result-shape validation;
- project-specific acceptance;
- deterministic tests;
- independent review;
- human merge approval.

This separation keeps generic execution mechanics out of project-specific correctness policy.

## Run it

```bash
embraion execute < request.json
```

The full request/result schema is documented in the [CLI reference](../reference/cli.md#embraion-execute).

## LiteLLM

The current optional loopback adapter uses the `litellm` extra:

```bash
pip install "embraion[litellm]"
```

Projects pin and validate the compatible adapter/runtime combination they rely on. EmbrAIon remains provider-neutral: the concrete selectors, bindings, credentials references, source ceilings, and evidence are project-owned.

For LiteLLM, `payload.inputsByDeployment` must include a bounded input for every candidate bound to `litellm-loopback` on the request execution host, including external fallback candidates. Cross-host and unbound candidates require no external input. Unknown or non-candidate input keys fail closed. Each selected external input is checked against its approved boundary and original work-item provenance before credentials or transport are used. Core derives the adapter candidate scope internally; callers cannot supply it. Existing valid optional inputs for handoff candidates remain accepted.

The current LiteLLM adapter rejects explicit `selected.effort` and nonempty `selected.options` during preflight, before credential resolution or any provider call. These settings have no verified provider translation yet; an option allowlist alone does not establish transport support. Requests without those settings continue to use the bounded Responses transport.

## Related

- [How EmbrAIon works](../getting-started/how-it-works.md)
- [Project deployments](deployments.md)
- [Model routing](../model-routing.md)
- [Pricing & cost](pricing.md)
- [Security](../security.md)
