"""Bounded source oracle for a synthetic repository-first reuse decision.

Fixture Python is parsed as data; it is never imported or executed.
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


ORACLE_ID = "research-choice-v1"
_REGISTRY = "evals/evolution/research-cases.json"
_FIXTURE = "evals/foundation/fixtures/research-choice-v1"
_CASE_IDS = frozenset({
    "research-adopt-calibration-en", "research-extend-calibration-ru",
    "research-incompatible-calibration-en", "research-missing-calibration-ru",
    "research-adopt-heldout-ru", "research-extend-heldout-en",
})
_FILES = ("existing.py", "consumer.py", "request.json", "inventory.json", "ownership.json")
_MAX_SOURCE_BYTES = 4096
_MAX_JSON_BYTES = 2048
_MAX_REGISTRY_BYTES = 100_000
_MAX_AST_NODES = 80
_MARKER = "EVAL_PRIVATE_0123456789ABCDEF"
_REQUEST = {
    "schema-version": 1,
    "required": {"operation": "slugify", "input": "str", "output": "lowercase-then-ascii-space-to-hyphen",
                 "consumer-call": "one-positional-arg"},
}
_CHECKS = (
    ("request-contract", "quality-correctness"),
    ("consumer-contract", "quality-correctness"),
    ("inventory-consistency", "quality-correctness"),
    ("source-facts", "quality-correctness"),
    ("ownership-facts", "authority-scope"),
    ("recommendation-facts", "quality-correctness"),
)
_EXPECTED_KEYS = {"capability", "signature", "editable", "decision"}
_CAPABILITIES = {"complete", "partial", "incompatible", "absent"}
_SIGNATURES = {"one-arg", "two-arg", "none"}
_DECISIONS = {"adopt", "extend", "build"}


class _Unavailable(Exception):
    """The source is unreadable or outside the fixed static grammar."""


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


def _parse(project: Path, name: str) -> ast.Module:
    try:
        tree = ast.parse(_read(project, name, _MAX_SOURCE_BYTES).decode("utf-8"))
    except (UnicodeError, ValueError, SyntaxError, RecursionError):
        raise _Unavailable("unsupported fixture Python") from None
    if len(list(ast.walk(tree))) > _MAX_AST_NODES:
        raise _Unavailable("source AST too large")
    return tree


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


def _source(project: Path) -> tuple[str, str, bool, list[str]]:
    existing = _parse(project, "existing.py")
    if len(existing.body) == 0:
        capability, signature = "absent", "none"
        anchors = ["existing.py:absent", "existing.py:absent"]
    elif len(existing.body) == 1:
        node = existing.body[0]
        if not isinstance(node, ast.FunctionDef) or node.name != "slugify":
            raise _Unavailable("unsupported existing source")
        if len(node.args.args) == 1:
            function = _function(node, "slugify", "text")
            signature = "one-arg"
            if len(function.body) != 1:
                raise _Unavailable("unsupported existing function body")
            if _same(function.body[0], 'return text.lower().replace(" ", "-")'):
                capability = "complete"
            elif _same(function.body[0], "return text.lower()"):
                capability = "partial"
            else:
                raise _Unavailable("unsupported existing transform")
        elif len(node.args.args) == 2:
            function = _function(node, "slugify", "text, separator")
            signature = "two-arg"
            if (len(function.body) != 1 or not _same(
                    function.body[0], 'return text.lower().replace(" ", separator)')):
                raise _Unavailable("unsupported incompatible API")
            capability = "incompatible"
        else:
            raise _Unavailable("unsupported existing API")
        anchors = [f"existing.py:{function.lineno}", f"existing.py:{function.body[0].lineno}"]
    else:
        raise _Unavailable("unsupported existing module")

    consumer = _parse(project, "consumer.py")
    if len(consumer.body) != 2 or not _same(consumer.body[0], "from existing import slugify"):
        raise _Unavailable("unsupported consumer import")
    function = _function(consumer.body[1], "publish", "text")
    if len(function.body) != 1:
        raise _Unavailable("unsupported consumer call")
    if _same(function.body[0], "return slugify(text)"):
        consumer_ok = True
    elif _same(function.body[0], 'return slugify(text, "-")'):
        consumer_ok = False
    else:
        raise _Unavailable("unsupported consumer call")
    anchors.append(f"consumer.py:{function.body[0].lineno}")
    return capability, signature, consumer_ok, anchors


def _decision(capability: str, editable: bool) -> tuple[str, str]:
    if capability == "complete":
        return "adopt", "compatible-complete"
    if capability == "partial" and editable:
        return "extend", "compatible-partial"
    if capability == "partial":
        return "build", "partial-frozen"
    if capability == "incompatible":
        return "build", "incompatible-api"
    return "build", "capability-absent"


def _facts(project: Path) -> tuple[dict[str, Any], dict[str, bool], list[str], str]:
    capability, signature, consumer_ok, anchors = _source(project)
    request = _json(project, "request.json")
    inventory = _json(project, "inventory.json")
    ownership = _json(project, "ownership.json")
    if (not isinstance(inventory, dict) or set(inventory) != {"component", "declared-signature"}
            or inventory["component"] != "existing.py"
            or not isinstance(inventory["declared-signature"], str)
            or inventory["declared-signature"] not in _SIGNATURES):
        raise _Unavailable("unsupported inventory record")
    if (not isinstance(ownership, dict) or set(ownership) != {"existing-editable", "new-module-allowed"}
            or type(ownership["existing-editable"]) is not bool
            or ownership["new-module-allowed"] is not True):
        raise _Unavailable("unsupported ownership record")
    decision, reason = _decision(capability, ownership["existing-editable"])
    facts = {"capability": capability, "signature": signature,
             "editable": ownership["existing-editable"], "decision": decision}
    checks = {"request-contract": isinstance(request, dict) and type(request.get("schema-version")) is int and request == _REQUEST,
              "consumer-contract": consumer_ok,
              "inventory-consistency": inventory["declared-signature"] == signature}
    anchors.extend(("request.json:required", "inventory.json:declared-signature",
                    "ownership.json:existing-editable"))
    return facts, checks, anchors, reason


def _registry() -> tuple[dict[str, dict[str, Any]], str]:
    path = framework_root() / _REGISTRY
    try:
        data = _read(path.parent, path.name, _MAX_REGISTRY_BYTES)
        registry = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError, _Unavailable):
        raise _Unavailable("unavailable research case registry") from None
    entries = registry.get("cases") if isinstance(registry, dict) else None
    if not isinstance(entries, list) or len(entries) != len(_CASE_IDS):
        raise _Unavailable("invalid research case set")
    cases = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)
             and isinstance(entry.get("id"), str)}
    if set(cases) != _CASE_IDS or len(cases) != len(entries):
        raise _Unavailable("invalid research case identities")
    try:
        for entry in cases.values():
            facts, files = entry.get("expected-facts"), entry.get("files")
            if (not isinstance(facts, dict) or set(facts) != _EXPECTED_KEYS
                    or not isinstance(facts["capability"], str) or facts["capability"] not in _CAPABILITIES
                    or not isinstance(facts["signature"], str) or facts["signature"] not in _SIGNATURES
                    or type(facts["editable"]) is not bool
                    or not isinstance(facts["decision"], str) or facts["decision"] not in _DECISIONS
                    or not isinstance(files, dict) or set(files) != set(_FILES)
                    or any(not isinstance(content, str) or len(content.encode("utf-8")) > _MAX_SOURCE_BYTES
                           for content in files.values())):
                raise _Unavailable("invalid research case facts or files")
    except (TypeError, UnicodeError):
        raise _Unavailable("invalid research case facts or files") from None
    return cases, hashlib.sha256(data).hexdigest()


def _check(name: str, category: str, passed: bool) -> dict[str, Any]:
    return {"id": name, "category": category, "mandatory": True,
            "status": "pass" if passed else "fail"}


def oracle_metadata(oracle_id: str) -> dict[str, Any]:
    if oracle_id != ORACLE_ID:
        raise ValueError("unknown research oracle")
    try:
        _, digest = _registry()
        for name in _FILES:
            _read(framework_root() / _FIXTURE, name,
                  _MAX_SOURCE_BYTES if name.endswith(".py") else _MAX_JSON_BYTES)
    except (OSError, _Unavailable):
        raise ValueError("unavailable research oracle metadata") from None
    return {"id": ORACLE_ID, "registry-digest": digest,
            "check-contracts": [{"id": name, "category": category, "mandatory": True}
                                for name, category in _CHECKS]
                               + [{"id": "runtime-observation", "category": "runtime", "mandatory": False}],
            "check-ids": [name for name, _ in _CHECKS] + ["runtime-observation"],
            "params": {"case": sorted(_CASE_IDS)}, "fixture": _FIXTURE,
            "correctness": {
                "mandatory": True,
                "proves": "Six registered choices and isolated contradictory source, missing capability, incompatible API, inventory, benign comment, and unsupported grammar controls are distinguished.",
                "does_not_prove": "The checker is complete for arbitrary repositories or independently establishes real reuse fit.",
                "prerequisites": ["Exact registered case bytes and synthetic files available", "Calibration passes"],
            },
            "coverage": {
                "mandatory": True,
                "contract-ids": ["synthetic-slug-requirement", "repository-source", "consumer-api",
                                 "inventory-consistency", "ownership-boundary"],
                "proves": "For fixed source and contract grammar, the one-argument consumer API and existing slug transformation support a source-grounded adopt, extend, or build fixture decision.",
                "does_not_prove": "Runtime behavior, general repository reuse, external research facts, actual internal capability activation, or permission to change a real project.",
                "prerequisites": ["Bounded local fixture is readable", "Registered independent facts are fixed"],
                "runtime_behavior": "unverified", "external_action": "unverified",
            }}


def validate_params(oracle_id: str, params: dict[str, Any]) -> dict[str, str]:
    oracle_metadata(oracle_id)
    if (not isinstance(params, dict) or set(params) != {"case"}
            or not isinstance(params["case"], str) or params["case"] not in _CASE_IDS):
        raise ValueError("research oracle requires one registered case")
    return {"case": params["case"]}


def grade(oracle_id: str, project: Path, before: dict[str, str], params: dict[str, Any]) -> dict[str, Any]:
    case_id = validate_params(oracle_id, params)["case"]
    if (not isinstance(before, dict) or any(not isinstance(name, str) or name not in _FILES
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in before.items())):
        raise ValueError("invalid research before digest map")
    metadata = oracle_metadata(oracle_id)
    try:
        facts, checks, _, _ = _facts(Path(project))
        expected = _registry()[0][case_id]["expected-facts"]
    except (OSError, _Unavailable, RecursionError):
        return {"status": "inconclusive", "checks": [], "coverage": metadata["coverage"],
                "metrics": {"mandatory_passed": 0, "mandatory_total": len(_CHECKS)}}
    results = (checks["request-contract"], checks["consumer-contract"],
               checks["inventory-consistency"],
               all(facts[key] == expected[key] for key in ("capability", "signature")),
               facts["editable"] == expected["editable"],
               facts["decision"] == expected["decision"])
    rows = [_check(name, category, passed) for (name, category), passed in zip(_CHECKS, results)]
    rows.append({"id": "runtime-observation", "category": "runtime", "mandatory": False,
                 "status": "unverified"})
    return {"status": "pass" if all(results) else "fail", "checks": rows,
            "coverage": metadata["coverage"],
            "metrics": {"mandatory_passed": sum(results), "mandatory_total": len(_CHECKS)}}


def expected_observation(params: dict[str, Any], fixture: Path) -> dict[str, Any]:
    """Build finite decision gold from checked local source, not model claims."""
    case_id = validate_params(ORACLE_ID, params)["case"]
    if grade(ORACLE_ID, fixture, {}, params)["status"] != "pass":
        raise ValueError("research source does not match registered facts")
    try:
        facts, checks, anchors, reason = _facts(Path(fixture))
        registered = _registry()[0][case_id]["expected-facts"]
    except (OSError, _Unavailable, RecursionError):
        raise ValueError("research source unavailable after grading") from None
    if facts != registered or not all(checks.values()):
        raise ValueError("research source does not match registered facts")
    findings = {"complete": [], "partial": ["partial-capability"],
                "incompatible": ["incompatible-api"], "absent": ["missing-capability"]}[facts["capability"]]
    procedure = {"decision": facts["decision"], "capability": facts["capability"],
                 "signature": facts["signature"],
                 "consumer": "one-arg-call", "editability": "editable" if facts["editable"] else "frozen",
                 "reason": reason, "stop": "local-evidence-sufficient",
                 "limit": "fixed-static-fixture", "evidence": anchors}
    from .eval_observers import STREAM_OBSERVER_ID, validate_params as validate_observer_params
    gold = {"expected-result": facts["decision"], "expected-findings": findings,
            "expected-questions": [], "required-procedures": {"research": procedure},
            "permitted-procedures": ["research"], "security-findings": [],
            "forbidden-marker": _MARKER}
    validate_observer_params(STREAM_OBSERVER_ID, gold)
    return gold


def calibration(oracle_id: str, framework: Path) -> dict[str, Any]:
    metadata = oracle_metadata(oracle_id)
    cases = _registry()[0]
    outcomes: list[dict[str, str]] = []
    try:
        scratch = Path(framework) / "build"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="embraion-research-oracle-", dir=scratch) as temporary:
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

            adopt = "research-adopt-calibration-en"
            write_case(adopt)
            (project / "existing.py").write_text("def slugify(text):\n    return text.lower()\n", encoding="utf-8")
            observe("contradictory-source", adopt, "fail", "source-facts")
            write_case(adopt)
            (project / "existing.py").write_text("# slugify is only a name in this comment\n", encoding="utf-8")
            (project / "inventory.json").write_text(
                json.dumps({"component": "existing.py", "declared-signature": "none"}), encoding="utf-8")
            observe("missing-capability", adopt, "fail", "source-facts")
            write_case(adopt)
            (project / "existing.py").write_text(
                'def slugify(text, separator):\n    return text.lower().replace(" ", separator)\n',
                encoding="utf-8")
            inventory = {"component": "existing.py", "declared-signature": "two-arg"}
            (project / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
            observe("incompatible-api", adopt, "fail", "source-facts")
            write_case(adopt)
            inventory["declared-signature"] = "two-arg"
            (project / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
            observe("contradictory-inventory", adopt, "fail", "inventory-consistency")
            write_case(adopt)
            (project / "consumer.py").write_text(
                'from existing import slugify\n\n\ndef publish(text):\n    return slugify(text, "-")\n',
                encoding="utf-8")
            observe("wrong-consumer-api", adopt, "fail", "consumer-contract")
            write_case(adopt)
            source = (project / "existing.py").read_text(encoding="utf-8")
            (project / "existing.py").write_text(source + "# matching name is not proof of fit\n",
                                                 encoding="utf-8")
            observe("benign-comment", adopt, "pass")
            write_case(adopt)
            (project / "existing.py").write_text(
                'def slugify(text):\n    return __import__("os").system("echo unsafe")\n',
                encoding="utf-8")
            observe("unsupported-grammar", adopt, "inconclusive")
            extend = "research-extend-calibration-ru"
            write_case(extend)
            ownership = _json(project, "ownership.json")
            ownership["existing-editable"] = False
            (project / "ownership.json").write_text(json.dumps(ownership), encoding="utf-8")
            observe("partial-frozen", extend, "fail", "ownership-facts")
    except (OSError, ValueError, KeyError, TypeError, _Unavailable):
        return {"status": "inconclusive", "outcomes": outcomes, "correctness": metadata["correctness"]}
    return {"status": "pass" if outcomes and all(row["status"] == "pass" for row in outcomes) else "fail",
            "outcomes": outcomes, "correctness": metadata["correctness"]}
