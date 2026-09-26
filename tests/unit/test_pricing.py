from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from embraion.adapters.provider_pricing import fetch_and_parse
from embraion.pricing import calculate_cost, pricing_status, read_snapshot, refresh_pricing


OFFICIAL = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing",
}


def config() -> dict:
    return {"schemaVersion": 1, "sources": {
        name: {"url": url, "adapter": name, "currency": "USD", "freshnessDays": 30,
               "skus": {f"{name}-api": {"sku": f"{name}-sku", "patterns": {
                   "input": rf"{name} input=(?P<rate>[0-9.]+)",
                   "cachedInput": rf"{name} cached=(?P<rate>[0-9.]+)",
                   "output": rf"{name} output=(?P<rate>[0-9.]+)",
                   "reasoning": rf"{name} reasoning=(?P<rate>[0-9.]+)"}}}}
        for name, url in OFFICIAL.items()}}


def fixture_fetch(source_id: str, source: dict, rate: str = "2") -> list[dict]:
    body = f"{source_id} input={rate}; {source_id} cached=1; {source_id} output=4; {source_id} reasoning=4".encode()
    return fetch_and_parse(source_id, source, body)


class PricingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        folder = self.project / ".embraion"
        folder.mkdir()
        (folder / "pricing.yaml").write_text(yaml.safe_dump(config()), encoding="utf-8")

    def test_each_official_adapter_refreshes_and_offline_calculation_is_deterministic(self) -> None:
        result = refresh_pricing(self.project, fetcher=fixture_fetch)
        self.assertEqual(4, len(result["changes"]))
        self.assertFalse(pricing_status(self.project)["stale"])
        snapshot = read_snapshot(self.project)
        self.assertEqual(4, len(snapshot["entries"]))
        usage = {"inputTokens": 1_000_000, "cachedInputTokens": 250_000,
                 "outputTokens": 500_000, "reasoningTokens": 100_000}
        first = calculate_cost("openai-api", usage, project=self.project, usage_semantics="inclusive")
        self.assertEqual("snapshot-computed", first["state"])
        self.assertEqual("3.75", first["amount"])
        self.assertEqual(first, calculate_cost("openai-api", usage, project=self.project, usage_semantics="inclusive"))
        self.assertEqual("4.65", calculate_cost("openai-api", usage, project=self.project, usage_semantics="disjoint")["amount"])
        self.assertEqual("unknown-provider", calculate_cost("openai-api", usage, project=self.project)["state"])

    def test_malformed_and_network_failure_keep_last_good_bytes(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        path = self.project / ".embraion" / "pricing.snapshot.json"
        previous = path.read_bytes()
        def malformed(source_id: str, source: dict) -> list[dict]:
            return fetch_and_parse(source_id, source, b"page structure changed")
        with self.assertRaises(RuntimeError):
            refresh_pricing(self.project, fetcher=malformed)
        self.assertEqual(previous, path.read_bytes())
        def offline(source_id: str, source: dict) -> list[dict]:
            raise TimeoutError("network failure")
        with self.assertRaises(TimeoutError):
            refresh_pricing(self.project, source_id="openai", fetcher=offline)
        self.assertEqual(previous, path.read_bytes())
        self.assertEqual("failed", pricing_status(self.project)["lastRefresh"]["status"])

    def test_rate_change_diff_and_stale_detection(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        changed = refresh_pricing(self.project, source_id="openai",
                                  fetcher=lambda source_id, source: fixture_fetch(source_id, source, "3"))
        self.assertEqual(["changed"], [row["kind"] for row in changed["changes"]])
        future = datetime.now(timezone.utc) + timedelta(days=31)
        self.assertTrue(pricing_status(self.project, at=future)["stale"])
        cost = calculate_cost("openai-api", {"inputTokens": 10, "cachedInputTokens": 0,
                                                "outputTokens": 0, "reasoningTokens": 0},
                              project=self.project, at=future)
        self.assertEqual("unknown-stale-pricing", cost["state"])

    def test_batch_or_limit_change_is_reported(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        def changed(source_id: str, source: dict) -> list[dict]:
            rows = fixture_fetch(source_id, source)
            rows[0]["batch"] = {"input": "1"}
            rows[0]["maxInputTokens"] = 272000
            return rows
        result = refresh_pricing(self.project, source_id="openai", fetcher=changed)
        self.assertEqual("changed", result["changes"][0]["kind"])
        self.assertEqual({"input": "1"}, result["changes"][0]["after"]["batch"])
        self.assertEqual(272000, result["changes"][0]["after"]["maxInputTokens"])

    def test_removed_source_is_reported_and_pruned_by_full_refresh(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        configuration = config()
        del configuration["sources"]["deepseek"]
        (self.project / ".embraion" / "pricing.yaml").write_text(
            yaml.safe_dump(configuration), encoding="utf-8")
        self.assertEqual(["deepseek-api"], pricing_status(self.project)["orphanEntries"])
        self.assertTrue(pricing_status(self.project)["stale"])
        result = refresh_pricing(self.project, fetcher=fixture_fetch)
        self.assertIn("removed", [change["kind"] for change in result["changes"]])
        self.assertFalse(pricing_status(self.project)["stale"])

    def test_unknown_price_and_usage_are_not_zero(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        self.assertEqual("unknown-pricing", calculate_cost("unmapped", {}, project=self.project)["state"])
        self.assertEqual("unknown-provider", calculate_cost("openai-api", None, project=self.project)["state"])
        self.assertEqual("unknown-provider", calculate_cost("openai-api", {"inputTokens": 10}, project=self.project)["state"])
        exact = calculate_cost("openai-api", None, project=self.project, provider_exact="0.5", reported_currency="EUR")
        self.assertEqual("provider-exact", exact["state"])
        self.assertEqual("EUR", exact["currency"])
        self.assertEqual("unknown-provider", calculate_cost("openai-api", None, project=self.project, provider_exact="invalid")["state"])

    def test_unapproved_url_is_rejected(self) -> None:
        source = config()["sources"]["openai"]
        source["url"] = "https://localhost/private"
        with self.assertRaises(RuntimeError):
            fetch_and_parse("openai", source, b"openai input=1")

    def test_schedule_and_batch_require_identified_category(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        path = self.project / ".embraion" / "pricing.snapshot.json"
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        row = next(row for row in snapshot["entries"] if row["deployment"] == "openai-api")
        row["schedule"] = {"kind": "utc-weekday", "peakUtcHours": [[10, 11]],
                           "peak": {"input": "4"}, "offPeak": {"input": "2"}}
        from embraion.pricing import _digest
        snapshot["digest"] = _digest(snapshot["entries"])
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        usage = {"inputTokens": 1_000_000, "cachedInputTokens": 0, "outputTokens": 0, "reasoningTokens": 0}
        peak = datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc)
        # The synthetic snapshot is dated at test execution time; keep freshness independent of wall clock.
        self.assertEqual("4", calculate_cost("openai-api", usage, project=self.project, at=peak, usage_semantics="inclusive")["amount"])
        self.assertEqual("unknown-pricing", calculate_cost("openai-api", usage, project=self.project, at=peak, batch=True, usage_semantics="inclusive")["state"])
        row["batch"] = {"input": "1"}
        snapshot["digest"] = _digest(snapshot["entries"])
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            read_snapshot(self.project)


if __name__ == "__main__":
    unittest.main()
