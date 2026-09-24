# LiteLLM

LiteLLM is a transport adapter, not a model catalog owner.

It may implement provider-neutral loopback transport, request normalization, provider evidence capture, and cost/usage reconciliation. EmbrAIon does not assign canonical model identity to LiteLLM or to provider adapter files. Model availability and selectors remain owned by the execution host/runtime or by explicit consuming-project overrides.

Provider/transport evidence may be recorded when execution exposes it, but that evidence does not become a framework model registry.

<sub>Last updated: 2026-09-24 13:45 UTC</sub>
