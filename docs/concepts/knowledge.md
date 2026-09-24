# Project Knowledge

Project knowledge is the factual context that should remain with a consuming repository.

Examples include:

- product architecture;
- domain terminology;
- supported hardware;
- compatibility constraints;
- source-of-truth locations;
- project-specific validation commands;
- decisions that should survive across AI sessions.

## Why it is separate from Core

Core should remain reusable. Product-specific facts in Core would couple unrelated projects to one application's assumptions.

Instead:

```text
EmbrAIon Core       project repository
-------------       ------------------
roles               product facts
skills              domain rules
routing             architecture
hard gates          compatibility
```

The project manifest maps knowledge IDs to files:

```yaml
knowledge:
  project: knowledge/project.md
  architecture: knowledge/architecture.md
```

EmbrAIon validation verifies that declared knowledge files resolve.

## Practical rule

If a fact is true because of the product, customer, domain, device, or repository, it normally belongs in project knowledge. If it should be true for every EmbrAIon consumer, it may belong in Core.
