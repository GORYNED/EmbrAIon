"""Bounded oracle for causal judgments over pre-recorded synthetic observations.

Candidate source and historical snapshots are parsed as data, never imported or run.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from .common import framework_root


ORACLE_ID = "debug-hypothesis-v1"
_REGISTRY = "evals/evolution/debug-cases.json"
_FIXTURE = "evals/foundation/fixtures/debug-hypothesis-v1"
_CASE_IDS = frozenset({
    "debug-competing-compute-en", "debug-contradictory-cache-ru",
    "debug-repeated-cache-en", "debug-typo-control-en",
    "debug-competing-heldout-ru", "debug-typo-heldout-ru",
})
_FILES = ("source.py", "contract.json", "observations.json", "narrative.json", "attempts.json")
_MAX_SOURCE_BYTES = 4096
_MAX_JSON_BYTES = 8192
_MAX_REGISTRY_BYTES = 120_000
_MAX_AST_NODES = 100
_MARKER = "EVAL_PRIVATE_0123456789ABCDEF"
_CHECKS = (
    ("target-contract", "quality-correctness"),
    ("source-facts", "quality-correctness"),
    ("observation-consistency", "quality-correctness"),
    ("revision-freshness", "freshness"),
    ("attempt-consistency", "quality-correctness"),
    ("narrative-facts", "quality-correctness"),
)
_EXPECTED_KEYS = {"mode", "compute-step", "cache-step", "cause", "leading", "attempt-count"}


class _Unavailable(Exception):
    """Unreadable input or unsupported static evidence grammar."""


def _read(project: Path, name: str, limit: int) -> bytes:
    root = Path(project)
    if (root.is_symlink() or getattr(root, "is_junction", lambda: False)()
            or not root.is_dir()):
        raise _Unavailable("unsafe fixture root")
    path = root / name
    if (path.is_symlink() or getattr(path, "is_junction", lambda: False)()
            or not path.is_file() or not path.resolve().is_relative_to(root.resolve())
            or path.stat().st_size > limit):
        raise _Unavailable("unsafe or oversized fixture member")
    data = path.read_bytes()
    if len(data) > limit:
        raise _Unavailable("oversized fixture member")
    return data


def _json(project: Path, name: str) -> Any:
    try:
        return json.loads(_read(project, name, _MAX_JSON_BYTES).decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        raise _Unavailable("invalid fixture JSON") from None


def _same(node: ast.AST, example: str) -> bool:
    return ast.dump(node, include_attributes=False) == ast.dump(
        ast.parse(example).body[0], include_attributes=False)


def _function(node: ast.AST, name: str, args: str) -> ast.FunctionDef:
    expected = ast.parse(f"def {name}({args}):\n    pass\n").body[0]
    if (not isinstance(node, ast.FunctionDef) or node.name != name or node.decorator_list
            or node.returns is not None or node.type_comment is not None
            or getattr(node, "type_params", [])
            or ast.dump(node.args, include_attributes=False) != ast.dump(
                expected.args, include_attributes=False)):
        raise _Unavailable("unsupported function signature")
    return node


def _step(function: ast.FunctionDef) -> int:
    if len(function.body) != 1:
        raise _Unavailable("unsupported transform body")
    if _same(function.body[0], "return value + 1"):
        return 1
    if _same(function.body[0], "return value + 2"):
        return 2
    raise _Unavailable("unsupported transform")


def _source(data: bytes) -> tuple[str, int, int | None, list[str]]:
    if len(data) > _MAX_SOURCE_BYTES:
        raise _Unavailable("oversized source snapshot")
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (UnicodeError, ValueError, SyntaxError, RecursionError):
        raise _Unavailable("unsupported source snapshot") from None
    if len(list(ast.walk(tree))) > _MAX_AST_NODES:
        raise _Unavailable("source AST too large")
    if len(tree.body) == 1:
        compute = _function(tree.body[0], "compute", "value")
        return "simple", _step(compute), None, [f"source.py:{compute.body[0].lineno}"]
    if len(tree.body) != 3:
        raise _Unavailable("unsupported source module")
    compute = _function(tree.body[0], "compute", "value")
    cached = _function(tree.body[1], "cached", "value")
    runner = _function(tree.body[2], "run", "value, use_cache")
    expected = ast.parse("def run(value, use_cache):\n    if use_cache:\n        return cached(value)\n    return compute(value)\n").body[0]
    if ([ast.dump(item, include_attributes=False) for item in runner.body]
            != [ast.dump(item, include_attributes=False) for item in expected.body]):
        raise _Unavailable("unsupported branch path")
    return ("complex", _step(compute), _step(cached),
            [f"source.py:{compute.body[0].lineno}", f"source.py:{cached.body[0].lineno}",
             f"source.py:{runner.body[0].lineno}"])


def _recorded(project: Path, mode: str) -> dict[str, Any]:
    value = _json(project, "observations.json")
    keys = ({"schema-version", "source-revision", "input", "direct"} if mode == "simple"
            else {"schema-version", "source-revision", "input", "cache-off", "cache-on"})
    if (not isinstance(value, dict) or set(value) != keys
            or type(value["schema-version"]) is not int or value["schema-version"] != 1
            or type(value["input"]) is not int or value["input"] != 41
            or not isinstance(value["source-revision"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["source-revision"])
            or any(type(value[key]) is not int or value[key] not in (42, 43)
                   for key in ({"direct"} if mode == "simple" else {"cache-off", "cache-on"}))):
        raise _Unavailable("unsupported recorded observation")
    return value


def _attempts(project: Path, mode: str, current: bytes, cache_step: int | None) -> tuple[int, bool]:
    value = _json(project, "attempts.json")
    records = value.get("records") if isinstance(value, dict) and set(value) == {"records"} else None
    if not isinstance(records, list) or len(records) not in (0, 2):
        raise _Unavailable("unsupported attempt record")
    if not records:
        return 0, True
    if mode != "complex":
        raise _Unavailable("simple typo has no attempt ledger")
    snapshots: list[bytes] = []
    compute_steps: list[int] = []
    consistent = True
    for record in records:
        if (not isinstance(record, dict)
                or set(record) != {"edit-target", "source", "revision", "observed-cache-on"}
                or record["edit-target"] != "compute" or not isinstance(record["source"], str)
                or not isinstance(record["revision"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["revision"])
                or type(record["observed-cache-on"]) is not int
                or record["observed-cache-on"] not in (42, 43)):
            raise _Unavailable("unsupported attempt entry")
        try:
            snapshot = record["source"].encode("utf-8")
        except UnicodeError:
            raise _Unavailable("invalid attempt source") from None
        prior_mode, prior_compute_step, prior_cache_step, _ = _source(snapshot)
        if prior_mode != "complex":
            raise _Unavailable("unsupported attempt source shape")
        snapshots.append(snapshot)
        compute_steps.append(prior_compute_step)
        consistent &= (record["revision"] == hashlib.sha256(snapshot).hexdigest()
                       and prior_cache_step == cache_step
                       and record["observed-cache-on"] == 41 + prior_cache_step == 43)
    consistent &= (snapshots[0] != snapshots[1] and compute_steps[0] != compute_steps[1]
                   and snapshots[1] == current)
    return 2, bool(consistent)


def _facts(project: Path) -> tuple[dict[str, Any], dict[str, bool], list[str]]:
    source = _read(project, "source.py", _MAX_SOURCE_BYTES)
    mode, compute_step, cache_step, anchors = _source(source)
    contract = _json(project, "contract.json")
    observations = _recorded(project, mode)
    narrative = _json(project, "narrative.json")
    if (not isinstance(narrative, dict) or set(narrative) != {"leading", "competing"}
            or not isinstance(narrative["leading"], str)
            or not isinstance(narrative["competing"], str)):
        raise _Unavailable("unsupported narrative record")
    if mode == "simple":
        if narrative != {"leading": "none", "competing": "none"}:
            raise _Unavailable("simple typo has no hypothesis ledger")
        cause = "typo" if observations["direct"] == 43 else "none"
        observation_consistent = observations["direct"] == 41 + compute_step
        anchors.extend(("contract.json:expected", "observations.json:direct"))
    else:
        if {narrative["leading"], narrative["competing"]} != {"compute", "cache"}:
            raise _Unavailable("unsupported competing hypotheses")
        off, on = observations["cache-off"], observations["cache-on"]
        if (off, on) == (43, 42):
            cause = "compute"
        elif (off, on) == (42, 43):
            cause = "cache"
        else:
            raise _Unavailable("observations do not discriminate causes")
        observation_consistent = off == 41 + compute_step and on == 41 + cache_step
        anchors.extend(("contract.json:expected", "observations.json:cache-off",
                        "observations.json:cache-on", "narrative.json:leading", "attempts.json:records"))
    attempt_count, attempt_consistent = _attempts(project, mode, source, cache_step)
    expected_contract = {"schema-version": 1, "input": 41, "expected": 42,
                         "entry": "compute" if mode == "simple" else "run"}
    checks = {"target-contract": isinstance(contract, dict)
              and all(type(contract.get(key)) is int for key in ("schema-version", "input", "expected"))
              and contract == expected_contract,
              "observation-consistency": observation_consistent,
              "revision-freshness": observations["source-revision"] == hashlib.sha256(source).hexdigest(),
              "attempt-consistency": attempt_consistent}
    facts = {"mode": mode, "compute-step": compute_step, "cache-step": cache_step,
             "cause": cause, "leading": narrative["leading"], "attempt-count": attempt_count}
    return facts, checks, anchors


def _registry() -> tuple[dict[str, dict[str, Any]], str]:
    path = framework_root() / _REGISTRY
    try:
        data = _read(path.parent, path.name, _MAX_REGISTRY_BYTES)
        registry = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError, _Unavailable):
        raise _Unavailable("unavailable debug case registry") from None
    entries = registry.get("cases") if isinstance(registry, dict) else None
    if not isinstance(entries, list) or len(entries) != len(_CASE_IDS):
        raise _Unavailable("invalid debug case set")
    cases = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)
             and isinstance(entry.get("id"), str)}
    if set(cases) != _CASE_IDS or len(cases) != len(entries):
        raise _Unavailable("invalid debug case identities")
    try:
        for entry in cases.values():
            facts, files = entry.get("expected-facts"), entry.get("files")
            if (not isinstance(facts, dict) or set(facts) != _EXPECTED_KEYS
                    or facts["mode"] not in ("simple", "complex")
                    or type(facts["compute-step"]) is not int or facts["compute-step"] not in (1, 2)
                    or facts["cache-step"] is not None and (type(facts["cache-step"]) is not int
                        or facts["cache-step"] not in (1, 2))
                    or facts["cause"] not in ("compute", "cache", "typo")
                    or facts["leading"] not in ("compute", "cache", "none")
                    or type(facts["attempt-count"]) is not int or facts["attempt-count"] not in (0, 2)
                    or not isinstance(files, dict) or set(files) != set(_FILES)
                    or any(not isinstance(content, str) or len(content.encode("utf-8")) > _MAX_JSON_BYTES
                           for content in files.values())):
                raise _Unavailable("invalid debug case facts or files")
    except (TypeError, UnicodeError):
        raise _Unavailable("invalid debug case facts or files") from None
    return cases, hashlib.sha256(data).hexdigest()


def _check(name: str, category: str, passed: bool) -> dict[str, Any]:
    return {"id": name, "category": category, "mandatory": True,
            "status": "pass" if passed else "fail"}


def oracle_metadata(oracle_id: str) -> dict[str, Any]:
    if oracle_id != ORACLE_ID:
        raise ValueError("unknown debug oracle")
    try:
        _, digest = _registry()
        for name in _FILES:
            _read(framework_root() / _FIXTURE, name,
                  _MAX_SOURCE_BYTES if name.endswith(".py") else _MAX_JSON_BYTES)
    except (OSError, _Unavailable):
        raise ValueError("unavailable debug oracle metadata") from None
    return {"id": ORACLE_ID, "registry-digest": digest,
            "check-contracts": [{"id": name, "category": category, "mandatory": True}
                                for name, category in _CHECKS]
                               + [{"id": "runtime-observation", "category": "runtime", "mandatory": False}],
            "check-ids": [name for name, _ in _CHECKS] + ["runtime-observation"],
            "params": {"case": sorted(_CASE_IDS)}, "fixture": _FIXTURE,
            "correctness": {
                "mandatory": True,
                "proves": "Registered causal judgments and isolated contradictory source, wrong target, stale revision, altered historical observation, benign comment, and unsupported grammar controls are distinguished.",
                "does_not_prove": "Historical records were actually produced by a real run or this grammar generalizes to debugging outside the fixture.",
                "prerequisites": ["Exact registered case bytes and bounded source available", "Calibration passes"],
            },
            "coverage": {
                "mandatory": True,
                "contract-ids": ["synthetic-failure", "competing-hypotheses", "recorded-discriminator",
                                 "revision-freshness", "historical-attempt-consistency"],
                "proves": "Within a fixed integer branch grammar, pre-recorded observations distinguish compute from cache causes; a direct typo needs no hypothesis ledger.",
                "does_not_prove": "Actual runtime execution, general causal debugging, real historical attempts, external action, or internal capability activation.",
                "prerequisites": ["Synthetic observations and source snapshots are readable", "Independent registered facts are fixed"],
                "runtime_behavior": "unverified", "external_action": "unverified",
            }}


def validate_params(oracle_id: str, params: dict[str, Any]) -> dict[str, str]:
    oracle_metadata(oracle_id)
    if (not isinstance(params, dict) or set(params) != {"case"}
            or not isinstance(params["case"], str) or params["case"] not in _CASE_IDS):
        raise ValueError("debug oracle requires one registered case")
    return {"case": params["case"]}


def grade(oracle_id: str, project: Path, before: dict[str, str], params: dict[str, Any]) -> dict[str, Any]:
    case_id = validate_params(oracle_id, params)["case"]
    if (not isinstance(before, dict) or any(not isinstance(name, str) or name not in _FILES
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in before.items())):
        raise ValueError("invalid debug before digest map")
    metadata = oracle_metadata(oracle_id)
    try:
        facts, checks, _ = _facts(Path(project))
        expected = _registry()[0][case_id]["expected-facts"]
    except (OSError, _Unavailable, RecursionError):
        return {"status": "inconclusive", "checks": [], "coverage": metadata["coverage"],
                "metrics": {"mandatory_passed": 0, "mandatory_total": len(_CHECKS)}}
    results = (checks["target-contract"],
               all(facts[key] == expected[key] for key in ("mode", "compute-step", "cache-step", "cause")),
               checks["observation-consistency"], checks["revision-freshness"],
               checks["attempt-consistency"] and facts["attempt-count"] == expected["attempt-count"],
               facts["leading"] == expected["leading"])
    rows = [_check(name, category, passed) for (name, category), passed in zip(_CHECKS, results)]
    rows.append({"id": "runtime-observation", "category": "runtime", "mandatory": False,
                 "status": "unverified"})
    return {"status": "pass" if all(results) else "fail", "checks": rows,
            "coverage": metadata["coverage"],
            "metrics": {"mandatory_passed": sum(results), "mandatory_total": len(_CHECKS)}}


def expected_observation(params: dict[str, Any], fixture: Path) -> dict[str, Any]:
    """Return finite fixture judgment only after registered facts are verified."""
    case_id = validate_params(ORACLE_ID, params)["case"]
    if grade(ORACLE_ID, fixture, {}, params)["status"] != "pass":
        raise ValueError("debug source does not match registered facts")
    try:
        facts, checks, anchors = _facts(Path(fixture))
        registered = _registry()[0][case_id]["expected-facts"]
    except (OSError, _Unavailable, RecursionError):
        raise ValueError("debug evidence unavailable after grading") from None
    if facts != registered or not all(checks.values()):
        raise ValueError("debug source does not match registered facts")
    if facts["mode"] == "simple":
        findings: list[str] = []
        procedure = {"cause": "typo", "next-step": "fix-typo", "evidence": anchors}
    else:
        cause = facts["cause"]
        revise = cause != facts["leading"]
        findings = (["unsupported-leading-hypothesis"] if revise else [])
        if facts["attempt-count"] == 2:
            findings.append("repeated-failed-fix")
        procedure = {"cause": cause, "leading": facts["leading"],
                     "competing": "cache" if facts["leading"] == "compute" else "compute",
                     "narrative": "revise" if revise else "retain",
                     "discriminator": "cache-on-vs-off",
                     "attempts": "repeated-compute" if facts["attempt-count"] == 2 else "none",
                     "next-step": "fix-" + cause, "evidence": anchors}
    from .eval_observers import STREAM_OBSERVER_ID, validate_params as validate_observer_params
    gold = {"expected-result": facts["cause"] + "-cause", "expected-findings": findings,
            "expected-questions": [], "required-procedures": {"debugging": procedure},
            "permitted-procedures": ["debugging"], "security-findings": [],
            "forbidden-marker": _MARKER}
    validate_observer_params(STREAM_OBSERVER_ID, gold)
    return gold


def expected_facts(params: dict[str, Any], fixture: Path) -> dict[str, Any]:
    """Expose verified source facts to newer observers without changing v1 gold."""
    case_id = validate_params(ORACLE_ID, params)["case"]
    if grade(ORACLE_ID, fixture, {}, params)["status"] != "pass":
        raise ValueError("debug source does not match registered facts")
    try:
        facts, checks, _ = _facts(Path(fixture))
        registered = _registry()[0][case_id]["expected-facts"]
    except (OSError, _Unavailable, RecursionError):
        raise ValueError("debug evidence unavailable after grading") from None
    if facts != registered or not all(checks.values()):
        raise ValueError("debug source does not match registered facts")
    return dict(facts)


def calibration(oracle_id: str, framework: Path) -> dict[str, Any]:
    metadata = oracle_metadata(oracle_id)
    cases = _registry()[0]
    outcomes: list[dict[str, str]] = []
    try:
        scratch = Path(framework) / "build"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="embraion-debug-oracle-", dir=scratch) as temporary:
            project = Path(temporary)

            def write_case(case_id: str) -> None:
                for name, content in cases[case_id]["files"].items():
                    (project / name).write_text(content, encoding="utf-8", newline="\n")

            def observe(name: str, case_id: str, expected: str, check: str | None = None) -> None:
                result = grade(oracle_id, project, {}, {"case": case_id})
                statuses = {row["id"]: row["status"] for row in result["checks"]}
                okay = result["status"] == expected and (check is None or statuses.get(check) == "fail")
                outcomes.append({"control": name, "expected": expected, "observed": result["status"],
                                 "status": "pass" if okay else "fail"})

            for case_id in sorted(_CASE_IDS):
                write_case(case_id)
                observe(case_id, case_id, "pass")
            complex_case = "debug-competing-compute-en"
            write_case(complex_case)
            source = (project / "source.py").read_text(encoding="utf-8")
            (project / "source.py").write_text(source.replace("return value + 2", "return value + 1", 1),
                                               encoding="utf-8")
            observations = _json(project, "observations.json")
            observations["source-revision"] = hashlib.sha256((project / "source.py").read_bytes()).hexdigest()
            (project / "observations.json").write_text(json.dumps(observations), encoding="utf-8")
            observe("contradictory-source", complex_case, "fail", "observation-consistency")
            write_case(complex_case)
            contract = _json(project, "contract.json")
            contract["entry"] = "compute"
            (project / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
            observe("wrong-target", complex_case, "fail", "target-contract")
            for field, value in (("schema-version", True), ("input", 41.0), ("expected", 42.0)):
                write_case(complex_case)
                contract = _json(project, "contract.json")
                contract[field] = value
                (project / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
                observe("typed-contract-" + field, complex_case, "fail", "target-contract")
            write_case(complex_case)
            observations = _json(project, "observations.json")
            observations["source-revision"] = "0" * 64
            (project / "observations.json").write_text(json.dumps(observations), encoding="utf-8")
            observe("stale-observed-revision", complex_case, "fail", "revision-freshness")
            write_case(complex_case)
            (project / "source.py").write_text(
                'def compute(value):\n    return __import__("os").system("echo unsafe")\n', encoding="utf-8")
            observe("unsupported-grammar", complex_case, "inconclusive")
            write_case(complex_case)
            source = (project / "source.py").read_text(encoding="utf-8")
            (project / "source.py").write_text(source + "# inert explanation\n", encoding="utf-8")
            observations = _json(project, "observations.json")
            observations["source-revision"] = hashlib.sha256((project / "source.py").read_bytes()).hexdigest()
            (project / "observations.json").write_text(json.dumps(observations), encoding="utf-8")
            observe("benign-comment", complex_case, "pass")
            repeated = "debug-repeated-cache-en"
            write_case(repeated)
            attempts = _json(project, "attempts.json")
            attempts["records"][0]["observed-cache-on"] = 42
            (project / "attempts.json").write_text(json.dumps(attempts), encoding="utf-8")
            observe("contradictory-attempt", repeated, "fail", "attempt-consistency")
    except (OSError, ValueError, KeyError, TypeError, _Unavailable):
        return {"status": "inconclusive", "outcomes": outcomes, "correctness": metadata["correctness"]}
    return {"status": "pass" if outcomes and all(row["status"] == "pass" for row in outcomes) else "fail",
            "outcomes": outcomes, "correctness": metadata["correctness"]}
