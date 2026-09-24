# GitHub Copilot

The Copilot adapter projects EmbrAIon roles into GitHub Copilot custom-agent files.

Install it:

```bash
embraion install --host copilot --destination .
```

Generated agents live under:

```text
.github/agents/
```

Copilot is treated as an interactive host surface. Canonical role, privacy, access, and workflow policy remains in EmbrAIon Core rather than being redefined in each generated agent file.
