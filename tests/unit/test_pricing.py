from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from embraion.adapters.provider_pricing import fetch_and_parse
from embraion.pricing import calculate_cost, pricing_status, read_snapshot, refresh_pricing, verify_pricing_fixtures


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
        self.assertEqual("4.15", calculate_cost("openai-api", usage, project=self.project,
                                                usage_semantics={"input": "inclusive", "output": "disjoint"})["amount"])
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
        missing_cached = calculate_cost("openai-api", {"inputTokens": 10, "cachedInputTokens": 1,
                                                       "outputTokens": 0, "reasoningTokens": 0},
                                        project=self.project, batch=True, usage_semantics="inclusive")
        self.assertEqual("snapshot-computed", missing_cached["state"])
        self.assertEqual("0.00001", missing_cached["amount"])
        self.assertEqual("unknown-pricing", calculate_cost("openai-api", {"inputTokens": 10, "cachedInputTokens": 1,
                                                               "outputTokens": 0, "reasoningTokens": 0},
            project=self.project, batch=True, usage_semantics="disjoint")["state"])

    def test_inclusive_output_uses_ordinary_rate_when_reasoning_is_not_separate(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        path = self.project / ".embraion" / "pricing.snapshot.json"
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        row = next(item for item in snapshot["entries"] if item["deployment"] == "openai-api")
        del row["rates"]["reasoning"]
        from embraion.pricing import _digest
        snapshot["digest"] = _digest(snapshot["entries"])
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        usage = {"inputTokens": 0, "cachedInputTokens": 0, "outputTokens": 100, "reasoningTokens": 25}
        result = calculate_cost("openai-api", usage, project=self.project,
                                usage_semantics={"input": "inclusive", "output": "inclusive"})
        self.assertEqual("snapshot-computed", result["state"])
        self.assertEqual("0.0004", result["amount"])
        self.assertEqual("unknown-pricing", calculate_cost("openai-api", usage, project=self.project,
            usage_semantics={"input": "inclusive", "output": "disjoint"})["state"])

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

    def test_pathological_source_pattern_times_out(self) -> None:
        source = config()["sources"]["openai"]
        source["skus"]["openai-api"]["patterns"] = {"input": r"(a+)+(?P<rate>0)"}
        with self.assertRaisesRegex(RuntimeError, "timed-out"):
            fetch_and_parse("openai", source, b"a" * 10_000)

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

    def write_fixtures(self, fixtures: list[dict]) -> Path:
        path = self.project / "pricing-fixtures.yaml"
        path.write_text(yaml.safe_dump({"schemaVersion": 1, "fixtures": fixtures}), encoding="utf-8")
        return path

    def test_pricing_fixtures_compare_exact_decimals(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        usage = {"inputTokens": 1_000_000, "cachedInputTokens": 250_000,
                 "outputTokens": 500_000, "reasoningTokens": 100_000}
        fixtures = [
            {"id": "inclusive", "deployment": "openai-api", "usage": usage, "usageSemantics": "inclusive",
             "expect": {"state": "snapshot-computed", "amount": "3.750", "currency": "USD"}},
            {"id": "mixed", "deployment": "openai-api", "usage": usage,
             "usageSemantics": {"input": "inclusive", "output": "disjoint"},
             "expect": {"state": "snapshot-computed", "amount": "4.15"}},
            {"id": "unproven-semantics", "deployment": "openai-api", "usage": usage,
             "expect": {"state": "unknown-provider", "amount": None}},
            {"id": "subscription", "deployment": "openai-api", "usage": None, "billing": "subscription",
             "expect": {"state": "subscription-quota", "amount": None, "currency": None}},
        ]
        report = verify_pricing_fixtures(self.write_fixtures(fixtures), self.project)
        self.assertTrue(report["passed"], report)
        fixtures[0]["expect"]["amount"] = "3.7500001"
        fixtures[2]["expect"] = {"state": "snapshot-computed", "amount": "0"}
        report = verify_pricing_fixtures(self.write_fixtures(fixtures), self.project)
        self.assertFalse(report["passed"])
        self.assertEqual([["amount"], [], ["state", "amount"], []],
                         [item["mismatches"] for item in report["fixtures"]])

    def test_pricing_fixtures_reject_floats_and_duplicate_ids(self) -> None:
        refresh_pricing(self.project, fetcher=fixture_fetch)
        fixture = {"id": "one", "deployment": "openai-api", "usage": None,
                   "expect": {"state": "unknown-provider", "amount": 0.1}}
        with self.assertRaisesRegex(RuntimeError, "pricing-fixtures"):
            verify_pricing_fixtures(self.write_fixtures([fixture]), self.project)
        fixture["expect"]["amount"] = None
        with self.assertRaisesRegex(RuntimeError, "unique"):
            verify_pricing_fixtures(self.write_fixtures([fixture, dict(fixture)]), self.project)

    def test_pricing_verify_command_exit_code(self) -> None:
        import io
        import os
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from embraion.cli import main
        refresh_pricing(self.project, fetcher=fixture_fetch)
        path = self.write_fixtures([{"id": "wrong", "deployment": "openai-api", "usage": None,
                                     "expect": {"state": "snapshot-computed", "amount": "1"}}])
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            code = main(["pricing", "verify", "--fixtures", str(path)])
        self.assertEqual(1, code)
        self.assertIn("wrong: FAIL (state, amount)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
