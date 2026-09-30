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

    # A run is one independent confirmation, regardless of repeated eval labels.
    # Eval-only observations use their eval ID. Unattributed repeats count once.
    identities = evidence.setdefault("observation-ids", _legacy_identities(evidence))
    identity = f"run:{run_id}" if run_id else f"eval:{eval_id}" if eval_id else "unattributed"
    before = (list(identities), list(evidence.get("run-ids", [])), list(evidence.get("eval-ids", [])),
              evidence.get("count"), item.get("confidence"))
    if identity not in identities:
        identities.append(identity)
    if run_id and run_id not in evidence.setdefault("run-ids", []):
        evidence["run-ids"].append(run_id)
    if eval_id and eval_id not in evidence.setdefault("eval-ids", []):
        evidence["eval-ids"].append(eval_id)
    _recount(item)
    after = (identities, evidence.get("run-ids", []), evidence.get("eval-ids", []),
             evidence["count"], item["confidence"])
    if before == after:
        return item
    if item["state"] in {"observed", "accumulating"}:
        item["state"] = "accumulating" if evidence["count"] > 1 else "observed"
    item["updated-utc"] = datetime.now(timezone.utc).isoformat()

    write_json(path, item)
    return item


def _legacy_identities(evidence: dict[str, Any]) -> list[str]:
    # Legacy counters cannot prove independence or associate evals with runs.
    runs = evidence.get("run-ids") or []
    evals = evidence.get("eval-ids") or []
    return list(dict.fromkeys([f"run:{value}" for value in runs] if runs else
                             [f"eval:{value}" for value in evals])) or (
        ["unattributed"] if evidence.get("count", 0) else [])


def _recount(item: dict[str, Any]) -> None:
    evidence = item["evidence"]
    identities = evidence.setdefault("observation-ids", _legacy_identities(evidence))
    count = len(set(identities))
    evidence["count"] = count
    item["confidence"] = min(0.95, 0.5 + 0.1 * max(0, count - 1))


def transition(candidate_id: str, action: str) -> dict[str, Any]:
    path = candidate_path(candidate_id)

    if not path.exists():
        raise RuntimeError(f"Unknown learning candidate: {candidate_id}")

    item = read_json(path)

    if action == "propose":
        _recount(item)
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
