# Configure EmbrAIon for Your Project

After `embraion init`, your repository owns a small configuration surface under `.embraion/`.

!!! tip "In plain English"
    You do not need to configure everything. For a first useful setup, answer three questions: **What should the AI know? What should it respect? What proves the change works?**

## Start with these three files

| First question | Start here |
| --- | --- |
| What should the AI know about this project? | `.embraion/knowledge.yaml` |
| Which source/path/privacy rules must it respect? | `.embraion/policy.yaml` |
| Which commands prove a change works? | `.embraion/validation.yaml` |

Everything else can stay at its safe default until the project actually needs it.

### What a minimal result can look like

After conversational setup, the useful diff can be very small:

```yaml
# .embraion/knowledge.yaml
slots:
  architecture:
    path: docs/architecture.md
```

```yaml
# .embraion/policy.yaml
sources:
  protected:
    - vendor/**
```

```yaml
# .embraion/validation.yaml
profiles:
  affected:
    - python -m pytest
```

You can edit these files directly, but the intended workflow is often simpler:

> Register our architecture document, protect `vendor/**`, and make `python -m pytest` the affected validation command.

!!! tip "Or just tell your AI"
    > Review this repository and configure the minimum useful EmbrAIon project contract: bind the existing architecture/source-of-truth knowledge, classify important source paths, and add real validation commands. Leave model routing on host-default unless there is a clear project requirement.

## Choose your depth

- **Simple configuration:** knowledge + policy + validation → install your host projection → start working.
- **Full engineering configuration:** add project agents, deployments, routing, provider execution, pricing, and enforcement only when needed.

[Engineering Model Deep Dive](../reference/engineering-model.md)

## Configuration map: question → file

| Question | Canonical file |
| --- | --- |
| What project is this and which EmbrAIon release does it use? | `project.yaml` |
| What facts and architecture should the AI know? | `knowledge.yaml` |
| Which paths are canonical, protected, generated, or external? | `policy.yaml` |
| What privacy/review/enforcement rules apply? | `policy.yaml` |
| Which concrete execution/model choices does this project reuse? | `deployments.yaml` |
| Should this project override the AI client's model selection? | `routing.yaml` |
| Which commands prove a change works? | `validation.yaml` |
| Does this project need domain-specific AI specialists? | `agents.yaml` |
| Does this project use provider-neutral executable bindings? | optional `execution.yaml` |
| Does this project maintain reviewed provider pricing sources? | optional `pricing.yaml` |

![Project configuration map](../assets/diagrams/en/04-configuration-map.svg){ loading=lazy }

## The ownership rule

**EmbrAIon Core owns reusable mechanisms.**

**The repository owns project facts and preferences.**

Generated host files are projections of that canonical contract rather than a second place to maintain project policy.

## Conversational examples

You can ask the AI already working in the repository:

> Register our architecture document as the architecture source of truth.

> Mark `vendor/**` protected and generated build outputs as generated.

> Add the integration test command to affected validation.

> Keep model selection on host-default.

> Add a read-only domain specialist only if existing Core roles are not sufficient.

The point is not that humans must memorize YAML. The project contract gives the AI one correct place to write each kind of setting.

## Recommended order

1. **Identity** — confirm `project.yaml`.
2. **Knowledge** — register project truth.
3. **Policy** — classify source paths and privacy/review defaults.
4. **Validation** — add real commands.
5. **Host projection** — install the host(s) you use.
6. **Agents** — only project-specific specialists.
7. **Deployments / routing** — only when explicit selection is useful.
8. **Execution / pricing** — only for the provider-neutral runtime.
9. **Enforcement** — after policy and validation are trustworthy.

## Inspect what changed

```bash
embraion doctor
embraion policy show
embraion validation list
embraion status
```

For routing:

```bash
embraion route --host codex --route-class complex --data PRIVATE
```

For generated host files:

```bash
embraion projection diff --host codex --destination .
```

## Continue by concern

- [Project files](project-files.md)
- [Project knowledge](knowledge.md)
- [Policy & protected paths](policy.md)
- [Validation configuration](validation.md)
- [Project agents](agents.md)
- [Project deployments](deployments.md)
- [Model routing](../model-routing.md)
- [Execution & providers](execution.md)
- [Pricing & cost](pricing.md)
- [Conversational configuration](ai-hosts.md)
