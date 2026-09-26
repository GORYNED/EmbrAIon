"""Validated offline pricing snapshots and deterministic cost calculation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .adapters.provider_pricing import fetch_and_parse, validate_official_url
from .common import framework_root, project_root, read_json, read_yaml


def _validate(data: Any, schema_name: str) -> None:
    schema = read_json(framework_root() / "schemas" / schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda item: str(list(item.absolute_path)))
    if errors:
        first = errors[0]
        location = ".".join(map(str, first.absolute_path)) or "<root>"
        raise RuntimeError(f"Invalid {schema_name} at {location}: {first.message}")


def read_pricing_config(project: Path | None = None) -> dict[str, Any]:
    path = project_root(project) / ".embraion" / "pricing.yaml"
    if not path.is_file():
        raise RuntimeError("No project pricing sources configured.")
    config = read_yaml(path)
    _validate(config, "pricing-config.schema.json")
    for source in config["sources"].values():
        validate_official_url(str(source["url"]), str(source["adapter"]))
    identities = [name for item in config["sources"].values() for name in item["skus"]]
    if len(identities) != len(set(identities)):
        raise RuntimeError("A deployment may have only one pricing source.")
    return config


def _digest(entries: list[dict[str, Any]]) -> str:
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    _validate(snapshot, "pricing-snapshot.schema.json")
    if snapshot["digest"] != _digest(snapshot["entries"]):
        raise RuntimeError("Pricing snapshot digest mismatch.")
    identities = [(row["deployment"], row["sku"]) for row in snapshot["entries"]]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Pricing snapshot has duplicate deployment/SKU entries.")
    for row in snapshot["entries"]:
        if "effectiveDate" in row and "validThrough" in row and row["effectiveDate"] > row["validThrough"]:
            raise RuntimeError("Pricing validity dates are reversed.")
        if "schedule" in row:
            if "batch" in row or "discounts" in row:
                raise RuntimeError("Scheduled pricing cannot also declare batch or discount rates.")
            ranges = row["schedule"]["peakUtcHours"]
            if any(start >= end for start, end in ranges):
                raise RuntimeError("Pricing UTC schedule has an invalid hour range.")
            hours = [hour for start, end in ranges for hour in range(start, end)]
            if len(hours) != len(set(hours)):
                raise RuntimeError("Pricing UTC schedule has overlapping hours.")
        for rates in (row["rates"], row.get("batch") or {},
                      *((row.get("discounts") or {}).values()),
                      *([row["schedule"][name] for name in ("peak", "offPeak")] if "schedule" in row else [])):
            for raw in rates.values():
                try:
                    value = Decimal(raw)
                except (InvalidOperation, TypeError) as error:
                    raise RuntimeError("Pricing rate is not a decimal string.") from error
                if not value.is_finite() or value < 0:
                    raise RuntimeError("Pricing rate is invalid.")


def read_snapshot(project: Path | None = None) -> dict[str, Any] | None:
    path = project_root(project) / ".embraion" / "pricing.snapshot.json"
    if not path.is_file():
        return None
    try:
        snapshot = read_json(path)
        _validate_snapshot(snapshot)
    except (ValueError, TypeError, KeyError) as error:
        raise RuntimeError("Existing pricing snapshot is invalid.") from error
    return snapshot


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor, name = tempfile.mkstemp(prefix=".pricing-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _entry_stale(entry: dict[str, Any], freshness_days: int, at: datetime) -> str | None:
    if _timestamp(entry["verifiedUtc"]) + timedelta(days=freshness_days) < at:
        return "age"
    today = at.date()
    if "effectiveDate" in entry and today < date.fromisoformat(entry["effectiveDate"]):
        return "not-effective"
    if "validThrough" in entry and today > date.fromisoformat(entry["validThrough"]):
        return "expired"
    return None


def pricing_status(project: Path | None = None, *, at: datetime | None = None) -> dict[str, Any]:
    root = project_root(project)
    config = read_pricing_config(root)
    now = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    error: str | None = None
    try:
        snapshot = read_snapshot(root)
    except RuntimeError as failure:
        snapshot = None
        error = str(failure)
    lookup = {row["deployment"]: row for row in snapshot["entries"]} if snapshot else {}
    sources = []
    for source_id, source in config["sources"].items():
        reasons: list[str] = []
        entries = []
        for deployment, sku in source["skus"].items():
            row = lookup.get(deployment)
            if (row is None or row["sku"] != sku["sku"] or row["sourceId"] != source_id or
                    row["sourceUrl"] != source["url"] or row["currency"] != source["currency"]):
                reasons.append(f"missing-or-mismatched:{deployment}")
            else:
                entries.append(row)
                stale = _entry_stale(row, source["freshnessDays"], now)
                if stale:
                    reasons.append(f"{stale}:{deployment}")
        sources.append({"id": source_id, "url": source["url"], "stale": bool(reasons),
                        "reasons": reasons, "entries": entries})
    outcome_path = root / ".embraion" / "state" / "pricing-refresh.json"
    try:
        outcome = read_json(outcome_path) if outcome_path.is_file() else None
    except (OSError, ValueError, TypeError):
        outcome = {"status": "unavailable"}
    expected = {(identifier, deployment, sku["sku"])
                for identifier, source in config["sources"].items()
                for deployment, sku in source["skus"].items()}
    orphan_entries = [row["deployment"] for row in snapshot["entries"]
                      if (row["sourceId"], row["deployment"], row["sku"]) not in expected] if snapshot else []
    return {"valid": snapshot is not None, "error": error, "digest": snapshot["digest"] if snapshot else None,
            "verifiedUtc": snapshot["verifiedUtc"] if snapshot else None,
            "stale": bool(orphan_entries) or any(item["stale"] for item in sources), "sources": sources,
            "orphanEntries": orphan_entries,
            "lastRefresh": outcome}


def _diff(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    old = {(row["deployment"], row["sku"]): row for row in before}
    new = {(row["deployment"], row["sku"]): row for row in after}
    changes = []
    for identity in sorted(old.keys() | new.keys()):
        previous, current = old.get(identity), new.get(identity)
        if previous is None:
            kind = "added"
        elif current is None:
            kind = "removed"
        elif any(previous.get(key) != current.get(key) for key in ("rates", "batch", "discounts", "schedule", "effectiveDate", "validThrough", "maxInputTokens", "currency", "unitTokens")):
            kind = "changed"
        else:
            continue
        changes.append({"deployment": identity[0], "sku": identity[1], "kind": kind,
                        "before": {key: previous.get(key) for key in ("rates", "batch", "discounts", "schedule", "effectiveDate", "validThrough", "maxInputTokens", "currency", "unitTokens")} if previous else None,
                        "after": {key: current.get(key) for key in ("rates", "batch", "discounts", "schedule", "effectiveDate", "validThrough", "maxInputTokens", "currency", "unitTokens")} if current else None})
    return changes


def refresh_pricing(project: Path | None = None, *, source_id: str | None = None,
                    fetcher: Any = fetch_and_parse) -> dict[str, Any]:
    root = project_root(project)
    config = read_pricing_config(root)
    if source_id is not None and source_id not in config["sources"]:
        raise RuntimeError("Unknown or unapproved pricing source ID.")
    selected = [source_id] if source_id else list(config["sources"])
    outcome_path = root / ".embraion" / "state" / "pricing-refresh.json"
    try:
        try:
            previous = read_snapshot(root)
        except RuntimeError:
            if source_id is not None:
                raise
            # A complete approved-source refresh can recover a corrupt snapshot.
            # No partial refresh may retain entries from invalid data.
            previous = None
        retained = [row for row in previous["entries"] if row["sourceId"] in config["sources"] and row["sourceId"] not in selected] if previous else []
        fetched: list[dict[str, Any]] = []
        for identifier in selected:
            source = config["sources"][identifier]
            candidate = fetcher(identifier, source)
            if len(candidate) != len(source["skus"]):
                raise RuntimeError("Pricing source did not cover all configured SKUs.")
            fetched.extend(candidate)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        entries = sorted([*retained, *fetched], key=lambda item: (item["deployment"], item["sku"]))
        candidate_snapshot = {"schemaVersion": 1, "verifiedUtc": now, "digest": _digest(entries), "entries": entries}
        _validate_snapshot(candidate_snapshot)
        for row in fetched:
            source = config["sources"][row["sourceId"]]
            expected = source["skus"].get(row["deployment"])
            if (expected is None or expected["sku"] != row["sku"] or row["sourceUrl"] != source["url"] or
                    row["currency"] != source["currency"]):
                raise RuntimeError("Fetched pricing identity/provenance does not match configuration.")
        changes = _diff(previous["entries"] if previous else [], entries)
        _atomic_json(root / ".embraion" / "pricing.snapshot.json", candidate_snapshot)
        result = {"status": "succeeded", "at": now, "sources": selected, "digest": candidate_snapshot["digest"], "changes": changes}
        try:
            _atomic_json(outcome_path, {key: value for key, value in result.items() if key != "changes"})
        except OSError:
            # The outcome journal is advisory. A committed snapshot is a successful refresh.
            pass
        return result
    except Exception as failure:
        # This separate state file may change; the last valid snapshot never does.
        try:
            _atomic_json(outcome_path, {"status": "failed", "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                        "sources": selected, "reason": type(failure).__name__})
        except OSError:
            pass
        raise


def calculate_cost(deployment: str, usage: dict[str, Any] | None, *, project: Path | None = None,
                   at: datetime | None = None, billing: str = "api", provider_exact: str | None = None,
                   adapter_cost: str | None = None, batch: bool = False,
                   discount: str | None = None, usage_semantics: str | dict[str, str] | None = None,
                   reported_currency: str | None = None) -> dict[str, Any]:
    if billing == "subscription":
        return {"state": "subscription-quota", "amount": None, "currency": None, "provenance": None}
    for state, raw in (("provider-exact", provider_exact), ("adapter-normalized", adapter_cost)):
        if raw is not None:
            try:
                value = Decimal(raw)
            except (InvalidOperation, TypeError, ValueError):
                return {"state": "unknown-provider", "amount": None, "currency": None, "provenance": None}
            if not value.is_finite() or value < 0:
                return {"state": "unknown-provider", "amount": None, "currency": None, "provenance": None}
            if reported_currency is not None and (not isinstance(reported_currency, str) or re.fullmatch(r"[A-Z]{3}", reported_currency) is None):
                return {"state": "unknown-provider", "amount": None, "currency": None, "provenance": None}
            return {"state": state, "amount": str(value), "currency": reported_currency, "provenance": state}
    try:
        snapshot = read_snapshot(project)
        config = read_pricing_config(project)
    except RuntimeError:
        return {"state": "unknown-pricing", "amount": None, "currency": None, "provenance": None}
    if snapshot is None:
        return {"state": "unknown-pricing", "amount": None, "currency": None, "provenance": None}
    matches = [row for row in snapshot["entries"] if row["deployment"] == deployment]
    if len(matches) != 1:
        return {"state": "unknown-pricing", "amount": None, "currency": None, "provenance": snapshot["digest"]}
    row = matches[0]
    source = config["sources"].get(row["sourceId"])
    if (source is None or source["url"] != row["sourceUrl"] or source["currency"] != row["currency"] or
            source["skus"].get(deployment, {}).get("sku") != row["sku"]):
        return {"state": "unknown-pricing", "amount": None, "currency": None, "provenance": snapshot["digest"]}
    current = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if _entry_stale(row, source["freshnessDays"], current):
        return {"state": "unknown-stale-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    if usage is None:
        return {"state": "unknown-provider", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    if isinstance(usage_semantics, str) and usage_semantics in {"inclusive", "disjoint"}:
        semantics = {"input": usage_semantics, "output": usage_semantics}
    elif (isinstance(usage_semantics, dict) and set(usage_semantics) == {"input", "output"} and
          all(isinstance(value, str) and value in {"inclusive", "disjoint"} for value in usage_semantics.values())):
        semantics = usage_semantics
    else:
        return {"state": "unknown-provider", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    if "maxInputTokens" in row and isinstance(usage.get("inputTokens"), int) and usage["inputTokens"] > row["maxInputTokens"]:
        return {"state": "unknown-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    rates = row["rates"]
    if "schedule" in row and (batch or discount):
        return {"state": "unknown-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    if "schedule" in row:
        schedule = row["schedule"]
        peak = current.weekday() < 5 and any(start <= current.hour < end for start, end in schedule["peakUtcHours"])
        if peak and schedule["kind"] == "utc-weekday-with-holidays" and schedule.get("holidaysUnverified", True):
            return {"state": "unknown-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
        rates = schedule["peak" if peak else "offPeak"]
    if batch:
        rates = row.get("batch")
    if discount:
        rates = (row.get("discounts") or {}).get(discount)
    if rates is None:
        return {"state": "unknown-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    try:
        input_total = Decimal(str(usage["inputTokens"]))
        output_total = Decimal(str(usage["outputTokens"]))
        cached = Decimal(str(usage.get("cachedInputTokens", 0)))
        reasoning = Decimal(str(usage.get("reasoningTokens", 0)))
        if ("cachedInput" in rates and "cachedInputTokens" not in usage) or ("reasoning" in rates and "reasoningTokens" not in usage):
            raise ValueError("Ambiguous usage categories")
        if (cached and "cachedInput" not in rates) or (reasoning and "reasoning" not in rates):
            return {"state": "unknown-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
        counts = {"input": input_total - cached if "cachedInput" in rates and semantics["input"] == "inclusive" else input_total,
                  "cachedInput": cached if "cachedInput" in rates else Decimal(0),
                  "output": output_total - reasoning if "reasoning" in rates and semantics["output"] == "inclusive" else output_total,
                  "reasoning": reasoning if "reasoning" in rates else Decimal(0)}
        if any(value < 0 or not value.is_finite() for value in counts.values()):
            raise ValueError("Overlapping usage totals are invalid")
        total = Decimal(0)
        for category, count in counts.items():
            if count:
                if category not in rates:
                    return {"state": "unknown-pricing", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
                total += count * Decimal(rates[category]) / Decimal(row["unitTokens"])
    except (KeyError, ValueError, InvalidOperation, TypeError):
        return {"state": "unknown-provider", "amount": None, "currency": row["currency"], "provenance": snapshot["digest"]}
    return {"state": "snapshot-computed", "amount": str(total), "currency": row["currency"], "provenance": snapshot["digest"]}
