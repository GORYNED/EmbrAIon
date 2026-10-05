"""Prepare registered evolution scenarios; case facts and gold live in evals/."""
from __future__ import annotations

from pathlib import Path

from .common import framework_root, read_json, write_json
from .eval_observers import (CHECKPOINT_DECISION_STREAM_OBSERVER_ID, DEBUG_DECISION_STREAM_OBSERVER_ID, DECISION_STREAM_OBSERVER_ID,
                             STREAM_OBSERVER_ID, validate_params)
from .eval_oracles import oracle_metadata
from .experiment_evals import _copy, _files, capture_snapshot, identity
from .skill_evals import _safe_relative

TARGET_FILES = {
    "scope-action": "evals/evolution/targets.json",
    "review-axes": "evals/evolution/review-cases.json",
    "security-flow": "evals/evolution/security-cases.json",
    "goal-flow": "evals/evolution/goal-cases.json",
    "research-choice": "evals/evolution/research-cases.json",
    "research-decision": "evals/evolution/research-decision-cases.json",
    "debug-hypothesis": "evals/evolution/debug-cases.json",
    "debug-decision": "evals/evolution/debug-decision-cases.json",
    "refactor-characterization": "evals/evolution/refactor-cases.json",
    "checkpoint-decision": "evals/evolution/checkpoint-cases.json",
}
TARGETS = frozenset(TARGET_FILES)


def prepare_target_baseline(source: Path, output: Path, *, target: str, host: str = "codex",
                            regenerate: bool = False) -> dict:
    if target not in TARGETS or output.exists():
        raise ValueError("unknown target or existing target output")
    registry = read_json(framework_root() / TARGET_FILES[target])
    plan = registry["targets"][target] if "targets" in registry else registry
    protocol = plan.get("protocol", registry["protocol"])
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
        oracle_params = {"case": entry["source-case"] if target in ("research-decision", "debug-decision") else entry["id"]} if target in ("security-flow", "goal-flow", "research-choice", "research-decision", "debug-hypothesis", "debug-decision", "refactor-characterization", "checkpoint-decision") else {}
        observer_id = (CHECKPOINT_DECISION_STREAM_OBSERVER_ID if target == "checkpoint-decision" else
                       DECISION_STREAM_OBSERVER_ID if target == "research-decision" else
                       DEBUG_DECISION_STREAM_OBSERVER_ID if target == "debug-decision" else STREAM_OBSERVER_ID)
        if target == "checkpoint-decision":
            from .checkpoint_oracles import expected_observation
            gold = expected_observation(oracle_params, fixture)
        elif target == "security-flow":
            from .security_oracles import expected_observation
            gold = expected_observation(oracle_params, fixture)
        elif target == "goal-flow":
            from .goal_oracles import expected_observation
            gold = expected_observation(oracle_params, fixture)
        elif target == "research-choice":
            from .research_oracles import expected_observation
            gold = expected_observation(oracle_params, fixture)
        elif target == "research-decision":
            from .research_oracles import expected_observation
            source_gold = expected_observation(oracle_params, fixture)
            source_facts = source_gold["required-procedures"]["research"]
            gold = {"expected-decision": source_gold["expected-result"],
                    "expected-findings": source_gold["expected-findings"],
                    "expected-facts": {"capability": source_facts["capability"],
                                       "signature": source_facts["signature"],
                                       "consumer": source_facts["consumer"],
                                       "editable": source_facts["editability"] == "editable"},
                    "expected-evidence": list(dict.fromkeys(source_facts["evidence"])),
                    "forbidden-marker": source_gold["forbidden-marker"]}
        elif target == "debug-hypothesis":
            from .debug_oracles import expected_observation
            gold = expected_observation(oracle_params, fixture)
        elif target == "debug-decision":
            from .debug_oracles import expected_facts, expected_observation
            source_gold = expected_observation(oracle_params, fixture)
            facts = expected_facts(oracle_params, fixture)
            source_facts = source_gold["required-procedures"]["debugging"]
            gold = {"expected-cause": source_facts["cause"],
                    "expected-findings": source_gold["expected-findings"],
                    "expected-facts": facts,
                    "expected-evidence": list(dict.fromkeys(source_facts["evidence"])),
                    "forbidden-marker": source_gold["forbidden-marker"]}
        elif target == "refactor-characterization":
            from .refactor_oracles import expected_observation
            gold = expected_observation(oracle_params)
        else:
            gold = entry["gold"]
        validate_params(observer_id, gold)
        cases.append({"id": entry["id"], "language": entry["language"], "polarity": entry["polarity"],
            "risk": entry.get("risk", plan["risk"]), "fixture": fixture.name, "prompt": entry["prompt"] + "\n" + protocol[entry["language"]],
            "allowed-paths": entry["allowed-paths"],
            **({"corpus-id": "framework-upgrade-scope-expansion"} if target == "scope-action" else {}),
            "oracles": [{"id": oracle_id, "params": oracle_params, "mandatory": True,
                         "metadata-digest": identity(oracle_metadata(oracle_id))}],
            "observer": {"id": observer_id, "params": gold, "mandatory": True}})
    suite = {"schema-version": 2, "id": target + "-target-baseline", "baseline": "baseline", "seed": 41,
        "execution": plan["execution"], "metric-rubric": ("checkpoint-decision-stream-metrics-v1" if target == "checkpoint-decision"
                                                       else "decision-stream-metrics-v1" if target == "research-decision"
                                                       else "debug-decision-stream-metrics-v1" if target == "debug-decision"
                                                       else "finite-stream-metrics-v1"),
        "variants": [{"id": "baseline", "snapshot": "snapshot", "manifest": "snapshot.json",
                      "manifest-digest": manifest["digest"], "changes": []}], "cases": cases}
    write_json(output / "suite.json", suite)
    return {"status": "prepared", "suite": str(output / "suite.json"), "target": target,
            "manifest-digest": manifest["digest"], "behavioral-evidence": "not-run"}
