"""Closed provider-neutral failure classes for execution attempts."""

from __future__ import annotations


FAILURES = frozenset({
    "authentication", "authorization", "policy-denied", "invalid-request",
    "unsupported-capability", "context-limit", "rate-limited", "quota-exhausted",
    "timeout", "transport", "provider-unavailable", "provider-error", "cancelled", "unknown",
})
SAFE_FALLBACK = frozenset({
    "rate-limited", "quota-exhausted", "timeout", "transport",
    "provider-unavailable", "provider-error",
})


def normalize_failure(value: str | None = None, *, http_status: int | None = None) -> str:
    if value in FAILURES:
        return value
    return {
        400: "invalid-request", 401: "authentication", 403: "authorization",
        408: "timeout", 413: "context-limit", 429: "rate-limited",
        500: "provider-error", 502: "provider-unavailable",
        503: "provider-unavailable", 504: "timeout",
    }.get(http_status, "unknown")


def may_fallback(failure: str, *, termination_confirmed: bool,
                 mutation_confirmed: bool) -> bool:
    return failure in SAFE_FALLBACK and termination_confirmed and mutation_confirmed
