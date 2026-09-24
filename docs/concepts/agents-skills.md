# Agents & Skills

EmbrAIon deliberately separates responsibility from procedure.

## Agents are roles

Core uses job-like roles:

| Role | Responsibility |
| --- | --- |
| Lead | Own task framing, delegation, integration, and completion |
| Worker | Implement bounded changes inside explicit ownership |
| Reviewer | Independently inspect correctness, risk, and regressions |
| Architect | Analyze boundaries, dependencies, and structural change |
| Analyst | Investigate evidence and turn it into actionable findings |
| Validator | Verify deterministic contracts and validation evidence |
| Researcher | Gather external or repository evidence without mutating product code |
| Steward | Maintain framework consistency and controlled evolution |

Project-specific domain specialists belong in the consuming project, not in generic Core.

## Skills are procedures

A skill describes how to perform a repeatable engineering activity. Roles can use multiple skills, and the same skill can serve multiple roles.

This prevents agent definitions from becoming giant collections of unrelated instructions.

A configuration-oriented skill can also teach the active AI host how to maintain project-owned EmbrAIon configuration without hardcoding vendor data into Core. For example, `routing-configuration` tells the AI to keep model names out of EmbrAIon Core and place optional project model overrides in `.embraion/routing.yaml` under `overrides`.

## Composition

A task is not solved by selecting a persona alone. EmbrAIon composes:

```text
responsibility
    +
procedure
    +
project facts
    +
routing/access constraints
    +
validation
```

That structure makes behavior easier to review, reuse, and evolve.
