# Providers

Provider adapters own direct API model facts and provider-specific execution metadata.

```text
providers/
├── openai/
├── google/
├── anthropic/
├── deepseek/
└── litellm/
```

Each provider's `models.yaml` records the current model deployment facts known to EmbrAIon. Project-specific credentials and source classifications remain in the consuming project overlay.

LiteLLM is a transport adapter and does not own canonical model identity or routing policy.

<sub>Last updated: 2026-09-23 18:11 UTC</sub>
