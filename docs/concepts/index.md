# Core Concepts

EmbrAIon separates reusable engineering policy from project-specific facts.

The central composition model is:

```text
Role + Skill + Project Knowledge + Routing + Validation
```

A **Role** answers who is responsible. A **Skill** describes a repeatable procedure. **Project knowledge** provides local truth. **Routing** selects an eligible execution path. **Validation** produces evidence that the result respects the relevant contracts.

## Canonical Core

Core owns reusable concepts that should behave consistently across projects:

- rules and hard gates;
- job-like agent roles;
- reusable skills;
- workflows;
- provider-neutral route classes;
- shared knowledge.

## Project overlay

A consuming repository adds what is specific to that project:

- project identity;
- pinned framework version;
- product/domain knowledge;
- local capabilities;
- stricter local rules where required.

## Host adapters

Adapters translate Core concepts into the files and selectors understood by a specific host. Generated host configuration is disposable; Core remains canonical.

Continue with [Agents & skills](agents-skills.md), [Project knowledge](knowledge.md), or [Project overlay](../project-overlay.md).
