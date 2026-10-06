# Ownership

Every capability has an owner before implementation.

Reusable consumer-agnostic behavior belongs upstream in the owning reusable system. Product/domain semantics, composition, and project-specific adapters remain in the consuming project.

Report reusable behavior found in a consumer as an upstream candidate. The upstream change lands first in its own pull request, and the consumer then updates its pin to it.
