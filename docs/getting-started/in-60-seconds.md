# EmbrAIon in 60 Seconds

!!! tip "In plain English"
    You keep the rules for AI work **with the repository**. Your AI client reads generated host-native instructions, while EmbrAIon keeps project knowledge, safety boundaries, validation, and routing in one reusable project contract.

## What you get

1. **Project knowledge** — point the AI at the architecture and source-of-truth documents that matter.
2. **Project policy** — classify canonical, protected, generated, and external paths.
3. **Validation** — define real commands that prove a change works.
4. **Host projections** — generate native agent/skill files understood by Codex, Copilot, or Claude Code.
5. **Optional routing** — classify work by complexity/risk and keep host-default model selection unless the project intentionally overrides it.
6. **Optional enforcement** — make protected-path, validation, and review requirements deterministic at delivery/merge time.

## The normal experience

Configure the repository once, then work normally:

> Add retry behavior when the connection drops.

You do **not** have to start every task with a framework prompt.

## The smallest useful setup

For most repositories, focus on three things first:

| What | File |
| --- | --- |
| What should the AI know? | `.embraion/knowledge.yaml` |
| What should it respect? | `.embraion/policy.yaml` |
| How do we prove the change works? | `.embraion/validation.yaml` |

Everything else can stay at its safe default until you need it.

## Two paths from here

- **Simple path:** sandbox → install → knowledge/policy/validation → normal AI tasks.
- **Engineer path:** ownership → projections → routing → execution → evidence/enforcement.

## One important distinction

Generated agent/skill files are **instructions delivered to the AI host**.

Commands such as:

```bash
embraion validation run affected
embraion enforcement check --base-ref origin/main
```

are **real executable checks**.

## Next

[Try it safely in the sandbox](playground.md).
