from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import framework_root, framework_version, project_root, read_json, read_yaml, state_root, write_json


def _get(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data

    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)

    return value


def evaluate_case(case: dict[str, Any], record: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []

    for check in case.get("checks", []):
        kind = check.get("type")

        if kind == "field-empty":
            value = _get(record, check["field"])
            if value:
                failures.append(f"{check['field']} must be empty")

        elif kind == "contains":
            value = _get(record, check["field"]) or []
            if check.get("value") not in value:
                failures.append(
                    f"{check['field']} must contain {check.get('value')}"
                )

        elif kind == "equals":
            value = _get(record, check["field"])
            if value != check.get("value"):
                failures.append(
                    f"{check['field']} expected {check.get('value')!r}, got {value!r}"
                )

        elif kind == "changed-paths-within":
            changed = _get(record, check.get("field", "changed-paths")) or []
            patterns = _get(record, check.get("patterns-field", "owned-paths")) or []

            for changed_path in changed:
                if not any(
                    fnmatch.fnmatch(changed_path, pattern)
                    for pattern in patterns
                ):
                    failures.append(
                        f"changed path outside owned scope: {changed_path}"
                    )

        else:
            failures.append(f"unsupported check type: {kind}")

    return not failures, failures


def run_case(case_id: str, record_path: Path, output: Path | None = None) -> dict[str, Any]:
    root = framework_root()
    case_path = root / "evals/cases" / f"{case_id}.yaml"

    if not case_path.exists():
        raise RuntimeError(f"Unknown eval case: {case_id}")

    case = read_yaml(case_path) or {}
    record = read_json(record_path)
    passed, failures = evaluate_case(case, record)

    report = {
        "schema-version": 1,
        "case": case_id,
        "passed": passed,
        "failures": failures,
        "framework-version": framework_version(root),
        "record": str(record_path),
        "completed-utc": datetime.now(timezone.utc).isoformat(),
    }

    destination = output or (
        state_root(project_root()) / "evals" / f"{case_id}.json"
    )
    write_json(destination, report)

    return report


def _load_reports(directory: Path) -> list[dict[str, Any]]:
    reports = []

    for path in directory.glob("*.json"):
        try:
            item = read_json(path)
            if "passed" in item:
                reports.append(item)
        except Exception:
            continue

    return reports


def aggregate(directory: Path) -> dict[str, Any]:
    reports = _load_reports(directory)
    total = len(reports)
    passed = sum(1 for report in reports if report.get("passed"))

    return {
        "cases": total,
        "passed": passed,
        "pass-rate": passed / total if total else 0.0,
    }


def create_baseline(reports: Path, output: Path) -> dict[str, Any]:
    baseline = {
        "schema-version": 1,
        "framework-version": framework_version(framework_root()),
        "captured-utc": datetime.now(timezone.utc).isoformat(),
        **aggregate(reports),
    }
    write_json(output, baseline)
    return baseline


def compare(baseline_path: Path, reports: Path) -> dict[str, Any]:
    baseline = read_json(baseline_path)
    current = aggregate(reports)

    return {
        "baseline": baseline,
        "current": current,
        "pass-rate-delta": (
            current["pass-rate"] - float(baseline.get("pass-rate", 0.0))
        ),
    }
