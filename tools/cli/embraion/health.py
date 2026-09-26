"""Time-controlled operational health derived from attempt observations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


OPERATIONAL_FAILURES = frozenset({"rate-limited", "quota-exhausted", "timeout", "transport", "provider-unavailable", "provider-error"})


def evaluate_health(observations: list[dict[str, Any]], *, at: datetime | None = None,
                    window_minutes: int = 30, degraded_failures: int = 2,
                    unavailable_failures: int = 3, cooldown_minutes: int = 15) -> dict[str, Any]:
    if min(window_minutes, degraded_failures, unavailable_failures, cooldown_minutes) < 1 or degraded_failures > unavailable_failures:
        raise RuntimeError("Invalid health policy thresholds.")
    now = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)
    recent: list[dict[str, Any]] = []
    for item in observations:
        observed_at = datetime.fromisoformat(item["at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if cutoff <= observed_at <= now:
            recent.append({**item, "_at": observed_at})
    recent.sort(key=lambda item: item["_at"])
    failures = [item for item in recent if item.get("failure") in OPERATIONAL_FAILURES]
    success = [item for item in recent if item.get("status") == "completed"]
    if not recent:
        state = "unknown"
    elif success and (not failures or success[-1]["_at"] > failures[-1]["_at"]):
        state = "healthy"
    elif len(failures) >= unavailable_failures:
        state = "unavailable"
    elif len(failures) >= degraded_failures:
        state = "degraded"
    else:
        state = "healthy"
    cooldown = (failures[-1]["_at"] + timedelta(minutes=cooldown_minutes)).isoformat().replace("+00:00", "Z") if state == "unavailable" else None
    return {"state": state, "observedUtc": recent[-1]["_at"].isoformat().replace("+00:00", "Z") if recent else None,
            "operationalFailures": len(failures), "cooldownUntilUtc": cooldown}
