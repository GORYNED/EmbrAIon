# GitHub Copilot

The Copilot adapter projects EmbrAIon roles and skills into GitHub Copilot custom-agent files.

Install it:

```bash
embraion install --host copilot --destination .
```

Generated agents live under:

```text
.github/agents/
```

Copilot remains the authority for its available models and default/automatic selection. EmbrAIon does not maintain a Copilot model catalog.

Optional project routing overrides may pass arbitrary Copilot-understood selectors/options. Core privacy, access, ownership, validation, and review policy remains independent from model identity.
