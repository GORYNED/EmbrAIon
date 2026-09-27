# Why EmbrAIon?

EmbrAIon is an **AI-First Engineering System** for software repositories.

!!! tip "In plain English"
    If your AI rules are starting to live in too many prompts, files, settings, CI scripts, and people's memory, EmbrAIon gives those rules one repository-owned home.

## If this sounds familiar...

- every new chat needs the same long “remember our architecture” prompt;
- Codex and Copilot know slightly different project rules;
- an AI occasionally touches a path it should not;
- “run the right tests” depends on somebody remembering which tests;
- model choices are repeated manually from task to task;
- a fresh session forgets decisions that should be project-wide.

### Before

```text
prompt
AGENTS.md
copilot instructions
host settings
CI scripts
developer memory
        ↓
different partial versions of the same rules
```

### After

```text
                 .embraion/
                    ↓
      one project-owned engineering contract
                    ↓
       Codex / Copilot / Claude Code
                    +
       validation / review / evidence
```

## Why not just use `AGENTS.md` or host-native instructions?

You can — and EmbrAIon can coexist with them.

A native instruction file is mainly guidance delivered to one host surface. EmbrAIon adds repository-owned configuration and deterministic tools around those instructions.

| Concern | Native instructions | EmbrAIon |
| --- | --- | --- |
| Tell an AI how to behave | Yes | Yes, through host projections |
| Share one contract across supported hosts | Usually manual | Project contract is canonical |
| Project knowledge selection | Host-specific | Project knowledge registry |
| Protected/generated/external source classes | Usually prose | Explicit project policy |
| Reusable task/risk routing | Usually host-specific | Stable route classes |
| Run project validation | Separate | Executable validation profiles |
| Record review/validation evidence | Separate/ad hoc | Structured evidence |
| Enforce protected paths / validation / review | Not by text alone | Optional deterministic enforcement |

## Practical examples

### “Do not modify vendor or fragile metadata”

**Before:** repeat it in prompts.

**With EmbrAIon:** classify the paths in project policy; host projections carry the guidance, and validation/enforcement can reject a delivery that changed a protected path.

!!! note "Important"
    A text instruction cannot physically override every AI host's filesystem permissions. Hard blocking comes from host controls or executable validation/enforcement.

### “Use UI Toolkit, not legacy UI APIs”

**Before:** repeat the architecture rule in prompts.

**With EmbrAIon:**

```text
knowledge → records UI Toolkit as project architecture
host projection → delivers the rule
validation → detects forbidden legacy APIs
enforcement → can require validation before merge
```

Knowledge explains the rule. Validation proves the result follows it.

### “Use stronger models only for harder work”

Classify work by stable task/risk classes, then keep host-default selection or define explicit project overrides.

### “Switch between Codex, Copilot, and Claude Code”

Keep the project contract canonical and project relevant roles/skills into each host's native format.

## The mental model

> **EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.**

- **Core** owns reusable mechanisms.
- **The project** owns facts and settings.
- **The AI host** owns the conversation, reasoning, and host capabilities.

## What EmbrAIon is not

- not a replacement for Codex, Copilot, or Claude Code;
- not a proxy that must receive every prompt;
- not a runtime dependency of the finished application;
- not a global model catalog;
- not a claim that text instructions alone are hard security controls.

## Next

- [EmbrAIon in 60 Seconds](in-60-seconds.md)
- [Five-Minute Sandbox](playground.md)
- [Installation](installation.md)
