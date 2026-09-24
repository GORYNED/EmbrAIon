# Providers

Provider integrations are optional execution/transport surfaces.

EmbrAIon intentionally does not ship a canonical catalog of provider models, prices, or current model availability. Those facts change independently from the framework and may differ by account, plan, region, host, or runtime.

A consuming project may supply provider/host selectors through its routing overrides, while Core continues to enforce model-independent privacy, access, ownership, validation, review, and evidence policy. Transport adapters such as `litellm/` may define transport mechanics without becoming model authorities.

<sub>Last updated: 2026-09-24 04:40 UTC</sub>
