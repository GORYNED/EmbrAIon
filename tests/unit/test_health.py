from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from embraion.health import evaluate_health


class HealthTests(unittest.TestCase):
    def test_window_thresholds_and_cooldown(self) -> None:
        now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
        failures = [{"at": (now - timedelta(minutes=minute)).isoformat(), "status": "failed", "failure": "timeout"}
                    for minute in (5, 4, 3)]
        self.assertEqual("unknown", evaluate_health([], at=now)["state"])
        self.assertEqual("degraded", evaluate_health(failures[:2], at=now)["state"])
        result = evaluate_health(failures, at=now)
        self.assertEqual("unavailable", result["state"])
        self.assertIsNotNone(result["cooldownUntilUtc"])
        self.assertEqual("unknown", evaluate_health(failures, at=now + timedelta(minutes=31))["state"])

    def test_policy_denial_does_not_affect_host_health(self) -> None:
        now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
        observations = [{"at": now.isoformat(), "status": "failed", "failure": "policy-denied"} for _ in range(4)]
        self.assertEqual("healthy", evaluate_health(observations, at=now)["state"])
