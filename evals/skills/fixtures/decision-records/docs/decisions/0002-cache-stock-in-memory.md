# 0002: Cache stock counts in memory

- Status: Rejected
- Date: 2026-03-04
- Supersedes: None
- Superseded by: None

## Context

Stock lookups wait on the warehouse API, which answers in about a second.

## Decision

Rejected: the warehouse is the only source of truth, and a stale count would oversell items.

## Consequences

Every stock lookup still calls the warehouse API.

## Alternatives considered

- A short-lived cache with explicit invalidation: rejected for the same staleness risk.
