# Configure EmbrAIon for Your Project

After `embraion init` and installing your host projection, ask:

> Configure EmbrAIon for this project.

Lead uses the canonical Core [Project Bootstrap](bootstrap.md) skill: inspect the repository, bind existing sources of truth, preserve safety policy, and discover real validation commands. You do not need to know every YAML file manually. [Configure by asking](configure-by-asking.md) maps each kind of request to the file it fills and the check that proves it. Routing and custom agents stay optional.

For explicit model tuning, use the full request on the Bootstrap page. Manual editing remains available; the table below is an ownership reference.

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
| Which external software or host features are declared? | optional `external-capabilities.yaml` |
| Which MCP servers should the project's host configuration contain? | optional `integrations.yaml` |
| Which files should trigger knowledge review when changed? | optional `knowledge-maintenance.yaml` |
| Which incremental code structure limits apply? | optional `organization.yaml` |
| Which architectural changes need a decision record? | optional `decisions.yaml` |

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
- [External capabilities](capabilities.md)
- [Code organization](organization.md)
- [Architecture decision records](decisions.md)
- [Knowledge maintenance](../guides/knowledge-maintenance.md)
