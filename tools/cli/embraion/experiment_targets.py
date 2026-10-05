"""Prepare registered evolution scenarios; case facts and gold live in evals/."""
from __future__ import annotations

from pathlib import Path

from .common import framework_root, read_json, write_json
from .eval_observers import STREAM_OBSERVER_ID, validate_params
from .eval_oracles import oracle_metadata
from .experiment_evals import _copy, _files, capture_snapshot
from .skill_evals import _safe_relative

TARGETS = frozenset({"scope-action"})


def prepare_target_baseline(source: Path, output: Path, *, target: str, host: str = "codex",
                            regenerate: bool = False) -> dict:
    if target not in TARGETS or output.exists():
        raise ValueError("unknown target or existing target output")
    registry = read_json(framework_root() / "evals/evolution/targets.json")
    plan = registry["targets"][target]
    manifest = capture_snapshot(source, output / "snapshot", output / "snapshot.json",
                                host=host, regenerate=regenerate)
    cases = []
    for entry in plan["cases"]:
        oracle_id = entry["oracle"]
        fixture_source = framework_root() / oracle_metadata(oracle_id)["fixture"]
        fixture = output / (entry["id"] + "-fixture")
        _copy(fixture_source, fixture, _files(fixture_source))
        for name, content in entry["files"].items():
            destination = fixture / _safe_relative(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
        validate_params(STREAM_OBSERVER_ID, entry["gold"])
        cases.append({"id": entry["id"], "language": entry["language"], "polarity": entry["polarity"],
            "risk": plan["risk"], "fixture": fixture.name, "prompt": entry["prompt"] + "\n" + registry["protocol"][entry["language"]],
            "allowed-paths": entry["allowed-paths"],
            "corpus-id": "framework-upgrade-scope-expansion",
            "oracles": [{"id": oracle_id, "params": {}, "mandatory": True}],
            "observer": {"id": STREAM_OBSERVER_ID, "params": entry["gold"], "mandatory": True}})
    suite = {"schema-version": 2, "id": target + "-target-baseline", "baseline": "baseline", "seed": 41,
        "execution": plan["execution"], "metric-rubric": "finite-stream-metrics-v1",
        "variants": [{"id": "baseline", "snapshot": "snapshot", "manifest": "snapshot.json",
                      "manifest-digest": manifest["digest"], "changes": []}], "cases": cases}
    write_json(output / "suite.json", suite)
    return {"status": "prepared", "suite": str(output / "suite.json"), "target": target,
            "manifest-digest": manifest["digest"], "behavioral-evidence": "not-run"}
