# Claude Code

The Claude Code adapter projects EmbrAIon roles and skills into Claude Code agent files.

Install it:

```bash
embraion install --host claude-code --destination .
```

Generated files live under:

```text
.claude/agents/
```

Claude Code remains the authority for its available models and default selection. EmbrAIon does not maintain a Claude Code model catalog.

Optional project routing overrides may pass arbitrary Claude Code-understood selectors/options. Core privacy, access, ownership, validation, and review policy remains independent from model identity.
