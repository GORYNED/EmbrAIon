# How EmbrAIon Works

EmbrAIon gives an AI client a durable engineering contract for a repository. It does not replace the AI client and it does not intercept every prompt.

The host still receives your request directly:

```text
you
 ↓
Codex / GitHub Copilot / Claude Code
 ↓
host-native EmbrAIon projections
 +
project-owned .embraion/ settings
 ↓
engineering work
 ↓
validation → review → evidence → human merge
```

The important distinction is between **projected guidance** and **deterministic framework execution**.

## Projected vs deterministic surfaces

| Surface | What it does | Who actually performs the work? |
| --- | --- | --- |
| Generated agents / skills | Teach the host reusable roles, procedures, and project integration rules | The AI host |
| `embraion route` | Deterministically resolves host-default or project routing policy | EmbrAIon CLI |
| `embraion dispatch` | Creates a bounded plan with role, access, data class, and owned paths | EmbrAIon CLI |
| Host-native Codex/Copilot/Claude work | Reasons, edits, searches, and uses host tools | The AI host |
| `embraion execute` | Runs a bounded provider-neutral execution request through an approved binding | EmbrAIon runtime |
| `embraion validation run` | Runs real project-declared validation commands and records evidence | EmbrAIon CLI + project commands |
| `embraion enforcement check` | Applies deterministic protected-path / validation / review gates | EmbrAIon CLI |
| GitHub enforcement workflow | Runs the configured merge-time gate in CI | GitHub Actions |

A generated agent file can instruct a host, but it cannot magically override the host's own security model. Conversely, `validation`, `execute`, and `enforcement` are executable framework surfaces rather than prompt guidance.

## Two execution lanes

Most projects use the **host-native lane**:

```text
normal user request
   ↓
AI host
   ↓
project knowledge / policy / roles / optional routing
   ↓
host reasoning + tools
```

The project can optionally use the **provider execution lane**:

```text
versioned execution request
   ↓
embraion execute
   ↓
project deployment + execution binding
   ↓
adapter (for example litellm-loopback)
   ↓
approved provider/model
   ↓
normalized result / attempts / usage / cost evidence
```

The second lane is useful when a repository wants deterministic provider bindings, bounded fallback, normalized failure/health behavior, or cost evidence outside the host-native conversation.

It is optional. A project can use EmbrAIon successfully without `execution.yaml` or `pricing.yaml`.

## Deployments vs routing vs execution vs pricing

These four concepts answer different questions:

| Concept | Question | Canonical project file |
| --- | --- | --- |
| **Deployment** | **What** reusable concrete execution choice exists? | `.embraion/deployments.yaml` |
| **Routing** | **When** should a route or role select it? | `.embraion/routing.yaml` |
| **Execution binding** | **How** may that deployment be invoked safely? | `.embraion/execution.yaml` |
| **Pricing** | **How** is provider cost interpreted and refreshed? | `.embraion/pricing.yaml` + validated snapshot |

Example:

```text
deployment:
  "analysis-api" = a reviewed provider/model choice

routing:
  substantial → analysis-api

execution:
  analysis-api → litellm-loopback
                 selector + credential reference
                 source/trust/task ceilings

pricing:
  analysis-api → official source + SKU mapping
                 → validated local snapshot
```

A project may use only the first two for host-native routing. The execution and pricing files are required only when the project opts into those runtime capabilities.

## What the project configures

The project should describe facts and preferences that are specific to the repository:

- project identity and exact framework pin;
- architecture and source-of-truth knowledge;
- protected/generated/external paths;
- privacy, review, and enforcement policy;
- concrete deployments and optional routing preferences;
- project-specific specialists;
- commands that prove changes work;
- optional execution bindings, credential references, and pricing sources.

The project should **not** reimplement generic fallback, health, role definitions, validation mechanics, or host projection logic. Those are EmbrAIon Core responsibilities.

## What happens when you ask the AI to configure EmbrAIon

You can say:

> Configure routing so bounded work stays inexpensive and complex architecture uses our stronger reviewed deployment.

The host should translate that intent to the canonical project files. It should not add an unrelated routing matrix to `AGENTS.md` or a generated agent file.

Likewise:

> Mark the vendor SDK protected.

maps to project policy, and:

> Add integration tests to affected validation.

maps to project validation.

The user does not need to memorize the YAML layout. The purpose of the layout is to give the AI and the repository **one authority per concern**.

## What routing does not mean

Writing a route override does not mean EmbrAIon transparently hijacks the host UI and switches every model selection.

For host-native work, EmbrAIon resolves the project contract and the host remains authoritative for its actual model availability and execution.

For provider-neutral execution through `embraion execute`, the framework can deterministically enforce the declared candidate/binding ceilings because it owns that execution path.

## Next

- [Configure the project](../configuration/index.md)
- [Project deployments](../configuration/deployments.md)
- [Execution & providers](../configuration/execution.md)
- [Pricing & cost](../configuration/pricing.md)
- [Model routing](../model-routing.md)
