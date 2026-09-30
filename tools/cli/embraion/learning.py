from __future__ import annotations

from copy import deepcopy

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
                **({"id": target_id} if target_id is not None else {}),
            },
        }

    before = deepcopy(item)
    evidence = item["evidence"]
    _migrate_evidence(evidence)
    runs = evidence.setdefault("run-ids", [])
    evals = evidence.setdefault("eval-ids", [])
    if run_id and run_id not in runs:
        runs.append(run_id)
    if eval_id:
        if eval_id not in evals:
            evals.append(eval_id)
        associated = evidence["eval-runs"].setdefault(eval_id, [])
        if run_id and run_id not in associated:
            associated.append(run_id)
    _recount(item)
    if item["state"] in {"observed", "accumulating"}:
        item["state"] = "accumulating" if evidence["count"] > 1 else "observed"
    elif item["state"] in {"proposed", "approved"} and not _proposal_ready(item):
        # New correlation can disprove previously assumed independence.
        item["state"] = "accumulating" if evidence["count"] > 1 else "observed"
    if item == before:
        return item
    item["updated-utc"] = datetime.now(timezone.utc).isoformat()
    write_json(path, item)
    return item


def _migrate_evidence(evidence: dict[str, Any]) -> None:
    if "eval-runs" not in evidence:
        # Earlier records cannot distinguish eval-only evidence from evals
        # attached to known runs. Do not infer independence from their counter.
        evidence["eval-runs"] = {
            value: list(evidence.get("run-ids") or [])
            for value in evidence.get("eval-ids") or []
        }


def _recount(item: dict[str, Any]) -> None:
    evidence = item["evidence"]
    _migrate_evidence(evidence)
    identities = [f"run:{value}" for value in evidence.get("run-ids") or []]
    identities += [f"eval:{value}" for value in evidence.get("eval-ids") or []
                   if not evidence["eval-runs"].get(value)]
    evidence["observation-ids"] = list(dict.fromkeys(identities)) or ["unattributed"]
    count = len(evidence["observation-ids"])
    evidence["count"] = count
    item["confidence"] = min(0.95, 0.5 + 0.1 * max(0, count - 1))
    # Accept legacy optional null targets, but write the canonical omission.
    if item.get("proposed-target", {}).get("id", "") is None:
        item["proposed-target"].pop("id", None)


def _proposal_ready(item: dict[str, Any]) -> bool:
    policy = read_yaml(framework_root() / "tools/learning/policy.yaml") or {}
    defaults = policy.get("defaults", {})
    return (item["evidence"]["count"] >= int(defaults.get("minimum-independent-evidence", 3))
            and float(item.get("confidence", 0)) >= float(defaults.get("minimum-confidence", 0.75)))


def transition(candidate_id: str, action: str) -> dict[str, Any]:
    path = candidate_path(candidate_id)

    if not path.exists():
        raise RuntimeError(f"Unknown learning candidate: {candidate_id}")

    item = read_json(path)

    _recount(item)
    if action in {"propose", "approve", "promote"} and not _proposal_ready(item):
        raise RuntimeError("Insufficient independent evidence or confidence for proposal.")

    if action == "propose":
        if item.get("state") not in {"observed", "accumulating", "proposed"}:
            raise RuntimeError("Only observed or accumulating candidates can be proposed.")
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
