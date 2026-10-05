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
    "consumer-evidence": "evals/evolution/consumer-cases.json",
}
TARGETS = frozenset(TARGET_FILES)
RESPONSE_CONTRACTS = {
    "scope-action": "artifact-response-v1",
    "consumer-evidence": "artifact-response-v1",
    "refactor-characterization": "artifact-response-v1",
    "research-decision": "research-response-v1",
    "debug-decision": "debug-response-v1",
    "checkpoint-decision": "checkpoint-response-v1",
    "security-flow": "security-response-v1",
}


def _structured_protocol(language: str, allowed: list[str], target: str) -> str:
    # Public output syntax only. Expected decisions, facts, findings and anchors
    # remain controller-owned observer parameters, never schema/prompt inputs.
    paths = ", ".join(allowed) or "none"
    vocabularies = {
        "scope-action": "result: updated | unchanged | hold; findings: applicable existing input defects only.",
        "consumer-evidence": "result: changed | unchanged | hold; finding IDs: consumer-disconnected (remaining implementation defect, not a corrected test gap).",
        "refactor-characterization": "result: changed | hold; finding IDs: behavior-changed, public-api-lost, consumer-broken, identity-loss.",
        "research-decision": "finding IDs: partial-capability, incompatible-api, missing-capability. Decision actions: adopt (reuse unchanged), extend (improve a compatible capability), build (new owned module/adapter); these names do not select an answer. Evidence uses existing.py:N for function definition and return (or existing.py:absent), consumer.py:N for return, request.json:required, inventory.json:declared-signature, ownership.json:existing-editable.",
        "debug-decision": "finding IDs: unsupported-leading-hypothesis, repeated-failed-fix. Evidence uses source.py:N for relevant compute/cached returns and run branch, contract.json:expected, observations.json:direct, observations.json:cache-off, observations.json:cache-on, narrative.json:leading, attempts.json:records. Recorded observations and attempts are supplied synthetic evidence, not proof of actual executions or historical provenance.",
        "checkpoint-decision": "finding IDs: stale-candidate-evidence, canceled-prior-approval. Evidence uses candidate.json:source, environment.json:fingerprint, checkpoint.json:absent, checkpoint.json:candidate-sha256, checkpoint.json:environment-sha256, checkpoint.json:request-id, checkpoint.json:verification, request.json:allowed-action, request.json:canceled-approval-ids, approval.json:request-id, approval.json:candidate-id, approval.json:status.",
        "security-flow": "result: hold | bounded-negative | no-activation. Finding IDs: cross-owner-document-read. Public assessment encodings: asset=document-body; entry=service.py:read_document; trust-boundary=actor-id-vs-record-owner-id; reachable-operation=other-owner-body-return | owner-guarded-body-return; existing-control=auth-guard-only | auth-and-owner-guard; mitigation=owner-deny-before-body-return | preserve-owner-deny-before-return; residual-risk=runtime-and-other-grammar-unverified; priority=high | none; preconditions=authenticated-cross-owner-document-id | authenticated-owner-document-id. Evidence uses contract.json:boundary and actual service.py:N anchors for function, lookup, body return and owner guard when present, in that order. This vocabulary specifies syntax only; choose answers from the reachable source paths.",
    }
    vocabulary = "\nPublic output vocabulary (not a selected answer): " + vocabularies[target]
    if language == "ru":
        return (f"Разрешены безопасное локальное чтение и изменения только этих путей: {paths}. "
                "Не исполняй Python или тесты примера, не устанавливай зависимости, не используй сеть и не публикуй. "
                "Прочитай релевантные source и контракт; выбери выводы по фактическому содержимому. "
                "Финальный JSON должен соответствовать зарегистрированной схеме ответа. "
                "Используй короткие locale-neutral ID и source anchors, без прозы внутри значений. "
                "Ранние сообщения необязательны; допустимы только {\"progress\":\"reading\"}, "
                "{\"progress\":\"checking\"} или {\"progress\":\"comparing\"}. "
                "Поле procedures следует схеме; оно не доказывает внутреннюю активацию. "
                "Отчёт и статическая проверка не подтверждают runtime или внешние действия.") + vocabulary
    return (f"Safe local reads and writes only to these paths are permitted: {paths}. "
            "Do not execute fixture Python or tests, install dependencies, use the network or publish. "
            "Read the relevant source and contract; select conclusions from their actual contents. "
            "The final JSON must match the registered response schema. "
            "Use short locale-neutral IDs and source anchors, without prose inside values. "
            "Earlier messages are optional and must be exactly {\"progress\":\"reading\"}, "
            "{\"progress\":\"checking\"} or {\"progress\":\"comparing\"}. "
            "The procedures field follows the schema; it does not establish internal activation. "
            "The report and static checks do not establish runtime behavior or external actions.") + vocabulary


def prepare_target_baseline(source: Path, output: Path, *, target: str, host: str = "codex",
                            regenerate: bool = False, structured_output: bool = False) -> dict:
    if target not in TARGETS or output.exists():
        raise ValueError("unknown target or existing target output")
    if structured_output and target not in RESPONSE_CONTRACTS:
        raise ValueError("target has no registered response contract")
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
        oracle_params = {"case": entry["source-case"] if target in ("research-decision", "debug-decision") else entry["id"]} if target in ("security-flow", "goal-flow", "research-choice", "research-decision", "debug-hypothesis", "debug-decision", "refactor-characterization", "checkpoint-decision", "consumer-evidence") else {}
        observer_id = (CHECKPOINT_DECISION_STREAM_OBSERVER_ID if target == "checkpoint-decision" else
                       DECISION_STREAM_OBSERVER_ID if target == "research-decision" else
                       DEBUG_DECISION_STREAM_OBSERVER_ID if target == "debug-decision" else STREAM_OBSERVER_ID)
        if target == "consumer-evidence":
            from .consumer_oracles import expected_observation
            gold = expected_observation(oracle_params, fixture)
        elif target == "checkpoint-decision":
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
            "risk": entry.get("risk", plan["risk"]), "fixture": fixture.name,
            "prompt": entry["prompt"] + "\n" + (_structured_protocol(entry["language"], entry["allowed-paths"], target)
                       if structured_output else protocol[entry["language"]]),
            **({"response-contract": RESPONSE_CONTRACTS[target]} if structured_output else {}),
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
