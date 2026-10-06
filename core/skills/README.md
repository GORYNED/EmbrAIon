# Skills

Skills are reusable procedures loaded only when relevant to the task.

Each skill lives in its own directory and uses the standard filename `SKILL.md`. Supporting references, scripts, or assets may be added beside it when the skill genuinely needs them.

```text
skills/
├── planning/SKILL.md
├── implementation/SKILL.md
├── code-organization/SKILL.md
├── research/SKILL.md
├── review/SKILL.md
├── validation/SKILL.md
├── debugging/SKILL.md
├── handling-review-findings/SKILL.md
├── verification/SKILL.md
└── routing-configuration/SKILL.md
```

A skill describes **how** to perform a class of work. It does not own agent identity or a canonical model catalog. Host adapters project skills into native locations, but Core does not assume that a host automatically inherits root/session skills into every subagent. Per-subagent skill delivery is only a framework guarantee when the target host explicitly supports it and the adapter configures and validates it.

The `routing-configuration` skill directs every installed AI host to keep all manually maintained concrete routing, deployment capability, billing, pricing/SKU, and execution-binding facts in `.embraion/**` when a Product Owner requests routing changes in ordinary language.

<sub>Last updated: 2026-10-06 02:15 UTC</sub>
