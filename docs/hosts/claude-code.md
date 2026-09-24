# Claude Code

The Claude Code adapter projects EmbrAIon roles into Claude Code agent files.

Install it:

```bash
embraion install --host claude-code --destination .
```

Generated files live under:

```text
.claude/agents/
```

The adapter owns Claude Code-specific model selection and host mechanics. Core continues to own reusable role, privacy, access, and workflow policy.

Provider eligibility still depends on the route and data classification. A host being installed does not make every data class eligible for every provider.
