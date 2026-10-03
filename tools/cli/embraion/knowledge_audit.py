"""Explicit, local knowledge baselines and read-only source drift audits."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .checkpoints import _hash, _safe_file
from .common import framework_root, project_root, read_json, write_json

def _config(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = _safe_file(root, ".embraion/knowledge-maintenance.yaml")
    if not path.exists():
        return None, None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = read_json(framework_root() / "schemas/knowledge-audit.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(data))
    if errors:
        raise RuntimeError("Invalid knowledge-maintenance.yaml: " + "; ".join(error.message for error in errors))
    ids = [item["id"] for item in data["documents"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate knowledge document ID.")
    return data, _hash(path)


def _baseline_path(root: Path) -> Path:
    return _safe_file(root, ".embraion/state/knowledge-audit/baseline.json", state=True)


def _observations(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    for entry in config["documents"]:
        files = [entry["path"], *entry["sources"]]
        hashes: dict[str, str | None] = {}
        for relative in files:
            path = _safe_file(root, relative)
            hashes[relative] = _hash(path)
        observations.append({
            "id": entry["id"], "path": entry["path"], "sources": entry["sources"],
            "hashes": hashes,
            "observed-version": entry.get("observed-version"),
            "external-version-known": "observed-version" in entry,
        })
    return observations


def snapshot_knowledge(*, project: Path | None = None) -> dict[str, Any]:
    """Write a baseline only when explicitly invoked, with hashes and paths only."""
    root = project_root(project)
    config, config_hash = _config(root)
    if config is None:
        raise RuntimeError("Missing .embraion/knowledge-maintenance.yaml.")
    observations = _observations(root, config)
    missing = sorted({path for item in observations for path, digest in item["hashes"].items() if digest is None})
    if missing:
        raise RuntimeError("Cannot snapshot missing knowledge source or document: " + ", ".join(missing))
    baseline = {
        "schema-version": 1, "config-hash": config_hash,
        "documents": observations,
        "created-utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(_baseline_path(root), baseline)
    return baseline


def audit_knowledge(*, project: Path | None = None) -> dict[str, Any]:
    """Compare declared source/document hashes; never rewrite documents."""
    root = project_root(project)
    config, config_hash = _config(root)
    if config is None:
        return {"status": "unconfigured", "documents": [], "reasons": ["configuration-missing"]}
    baseline_path = _baseline_path(root)
    baseline = read_json(baseline_path) if baseline_path.is_file() else None
    previous = {item["id"]: item for item in baseline.get("documents", [])} if baseline else {}
    results = []
    for item in _observations(root, config):
        prior = previous.get(item["id"])
        missing = [path for path, digest in item["hashes"].items() if digest is None]
        changed = []
        if prior:
            old_hashes = prior.get("hashes", {})
            changed = [path for path, digest in item["hashes"].items()
                       if digest is not None and old_hashes.get(path) != digest]
        reasons = []
        if missing:
            reasons.append("file-missing")
        if not prior:
            reasons.append("baseline-missing")
        elif changed or prior.get("path") != item["path"] or prior.get("sources") != item["sources"] or prior.get("observed-version") != item["observed-version"]:
            reasons.append("source-or-document-changed")
        results.append({
            "id": item["id"], "path": item["path"],
            "status": "missing" if missing else ("needs-review" if reasons else "current"),
            "reasons": reasons, "missing-paths": missing, "changed-paths": changed,
            "external-version-known": item["external-version-known"],
        })
    if baseline and baseline.get("config-hash") != config_hash:
        # Even a metadata change can invalidate the old interpretation.
        for result in results:
            if result["status"] == "current":
                result["status"] = "needs-review"
                result["reasons"].append("configuration-changed")
    return {
        "status": "missing" if any(item["status"] == "missing" for item in results)
                  else ("needs-review" if any(item["status"] == "needs-review" for item in results) else "current"),
        "baseline-present": baseline is not None,
        "documents": results,
    }
