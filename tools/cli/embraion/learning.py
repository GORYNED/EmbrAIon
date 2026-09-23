from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import (
    framework_root,
    project_root,
    read_json,
    read_yaml,
    state_root,
    write_json,
)


def candidate_path(candidate_id: str) -> Path:
    return state_root(project_root()) / "learning" / f"{candidate_id}.json"


def observe(
    candidate_id: str,
    kind: str,
    target_type: str,
    target_id: str | None,
    summary: str,
    run_id: str | None = None,
    eval_id: str | None = None,
) -> dict[str, Any]:
    path = candidate_path(candidate_id)

    if path.exists():
        item = read_json(path)
    else:
        item = {
            "schema-version": 1,
            "id": candidate_id,
            "state": "observed",
            "kind": kind,
            "confidence": 0.5,
            "summary": summary,
            "evidence": {
                "count": 0,
                "run-ids": [],
                "eval-ids": [],
            },
            "proposed-target": {
                "type": target_type,
                "id": target_id,
            },
        }

    evidence = item.setdefault(
        "evidence",
        {
            "count": 0,
            "run-ids": [],
            "eval-ids": [],
        },
    )

    evidence["count"] = int(evidence.get("count", 0)) + 1

    if run_id and run_id not in evidence.setdefault("run-ids", []):
        evidence["run-ids"].append(run_id)

    if eval_id and eval_id not in evidence.setdefault("eval-ids", []):
        evidence["eval-ids"].append(eval_id)

    count = evidence["count"]
    item["confidence"] = min(0.95, 0.5 + 0.1 * max(0, count - 1))
    item["state"] = "accumulating" if count > 1 else "observed"
    item["updated-utc"] = datetime.now(timezone.utc).isoformat()

    write_json(path, item)
    return item


def transition(candidate_id: str, action: str) -> dict[str, Any]:
    path = candidate_path(candidate_id)

    if not path.exists():
        raise RuntimeError(f"Unknown learning candidate: {candidate_id}")

    item = read_json(path)

    if action == "propose":
        policy = read_yaml(framework_root() / "tools/learning/policy.yaml") or {}
        defaults = policy.get("defaults", {})

        minimum_evidence = int(defaults.get("minimum-independent-evidence", 3))
        minimum_confidence = float(defaults.get("minimum-confidence", 0.75))

        if item["evidence"]["count"] < minimum_evidence:
            raise RuntimeError("Insufficient independent evidence for proposal.")

        if float(item.get("confidence", 0)) < minimum_confidence:
            raise RuntimeError("Confidence is below promotion policy threshold.")

        item["state"] = "proposed"

    elif action == "approve":
        if item.get("state") != "proposed":
            raise RuntimeError("Only proposed candidates can be approved.")
        item["state"] = "approved"

    elif action == "reject":
        item["state"] = "rejected"

    elif action == "promote":
        if item.get("state") != "approved":
            raise RuntimeError("Only approved candidates can be promoted.")

        item["state"] = "promoted"
        item["promotion-note"] = (
            "Core remains unchanged; implement this promotion through "
            "the ordinary engineering workflow."
        )

    else:
        raise RuntimeError(f"Unsupported learning transition: {action}")

    item["updated-utc"] = datetime.now(timezone.utc).isoformat()
    write_json(path, item)

    return item
