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
- context-boundary identity and a context byte bound (`maxContextBytes`);
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
3. evaluates supplied health observations, or the local attempt ledger when none are supplied;
4. invokes only a declared adapter/binding;
5. normalizes failure state;
6. records an attempt without raw credentials or prompt/context bytes, and the CLI appends it to the attempt ledger;
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

An API run needs only project configuration:

```bash
embraion execution preflight --path src/module.py --task-file task.md < request.json
embraion execution envelope --path src/module.py --task-file task.md < request.json > ready.json
embraion execute < ready.json
embraion execution health
```

The full request/result schema is documented in the [CLI reference](../reference/cli.md#embraion-execute).

## Context envelopes

`embraion execution envelope` reads a request from stdin and prints it with `payload.inputsByDeployment` filled for every candidate bound to an envelope adapter (currently `litellm-loopback`) on the request host. Each input is one envelope bound to the binding `contextBoundary` and to the work item, deployment, model, role, source IDs, access, and aliased data class. It carries the task text, the resolved commit, and one entry per file with path, SHA-256, size, and content.

The builder fails closed. It reads only committed blobs at `--commit` (default `HEAD`), never the working tree, and refuses:

- paths that are absolute, contain `..`, `:`, or control characters, or are absent from the commit;
- symbolic links, submodules, directories, Git LFS pointers, and binary or non-UTF-8 files;
- paths that match `sources.protected` in `.embraion/policy.yaml`, and always `.git/`, `.embraion/state/`, `.embraion/cache/`, and `.env` files;
- files whose data class is unknown or more sensitive than the request; the class comes from the matching `.embraion/knowledge.yaml` entry, otherwise from `privacy.default-class`;
- content or task text with credential material (security-scan patterns or the value of a bound credential reference) or with a machine-local absolute path or file URL;
- more than 128 files, a file above `--max-file-bytes` (default 262144), or context above `--max-total-bytes` (default 524288) or a binding `maxContextBytes`;
- candidates that violate the request ceilings or lack a `contextBoundary`, and requests that already supply payload input.

A refusal names the path and the reason, never the content. `--payload-only` prints only the payload; `--max-output-tokens` sets `payload.maxOutputTokens`.

## Readiness without a call

`embraion execution preflight` checks each adapter-bound candidate of a stdin request: the binding is complete, the request ceilings hold, the credential reference resolves, and adapter preflight passes with the request payload or, when there is none, with a payload built from `--path` and `--task-file`. Only credential presence is checked; the value is never printed or stored, and no provider is called. `--deployment ID` (repeatable) checks bindings and credentials without a request. Cross-host and unbound candidates are listed as handoff. The command exits 1 when anything is not ready.

## Attempt ledger and health

`embraion execute` appends each validated attempt to `.embraion/state/execution-attempts.jsonl` under a file lock. A record is the same redacted attempt object as in the result, with run and work-item IDs; it never contains prompt, context, output, or credential values. At 1 MiB the ledger rotates once to `execution-attempts.1.jsonl`. Unreadable lines, including a truncated last line after an interrupted write, are skipped and counted. When a request supplies no `healthObservations`, `execute` derives them from the ledger, so repeated operational failures demote or skip a deployment within the health window. A failed ledger write prints a warning and keeps the result.

`embraion execution health [--json]` shows per-deployment state, recent operational failures, cooldown, and the count of unreadable lines.

## LiteLLM

The current optional loopback adapter uses the `litellm` extra:

```bash
pip install "embraion[litellm]"
```

Projects pin and validate the compatible adapter/runtime combination they rely on. EmbrAIon remains provider-neutral: the concrete selectors, bindings, credentials references, source ceilings, and evidence are project-owned.

For LiteLLM, `payload.inputsByDeployment` (built by `embraion execution envelope`) must include a bounded input for every candidate bound to `litellm-loopback` on the request execution host, including external fallback candidates. Cross-host and unbound candidates require no external input. Unknown or non-candidate input keys fail closed. Each selected external input is checked against its approved boundary and original work-item provenance before credentials or transport are used. Core derives the adapter candidate scope internally; callers cannot supply it. Existing valid optional inputs for handoff candidates remain accepted.

The current LiteLLM adapter rejects explicit `selected.effort` and nonempty `selected.options` during preflight, before credential resolution or any provider call. These settings have no verified provider translation yet; an option allowlist alone does not establish transport support. Requests without those settings continue to use the bounded Responses transport.

Public execution results report this known preflight refusal as `unsupported-capability` with a static `diagnostic`, including through the CLI. No credential lookup or provider call occurs. Arbitrary adapter exception messages and raw diagnostics are not exposed.

## Related

- [How EmbrAIon works](../getting-started/how-it-works.md)
- [Project deployments](deployments.md)
- [Model routing](../model-routing.md)
- [Pricing & cost](pricing.md)
- [Security](../security.md)
