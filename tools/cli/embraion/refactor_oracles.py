"""Characterize a fixed integer API before/after a synthetic module move.

Source is parsed as data, never imported or executed. Original fixture bytes and
protected identities belong to the trusted controller, outside candidate writes.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import tempfile
from pathlib import Path

from .common import framework_root

ORACLE_ID = "refactor-characterization-v1"
_REGISTRY = "evals/evolution/refactor-cases.json"
_FIXTURE = "evals/foundation/fixtures/refactor-characterization-v1"
_IDS = {"refactor-move-en", "refactor-move-ru", "refactor-typo-en", "refactor-typo-ru",
        "refactor-heldout-ru", "refactor-heldout-en"}
_MARKER = "EVAL_PRIVATE_0123456789ABCDEF"
_CHECKS = [("characterization-baseline", "quality-correctness"),
           ("structural-goal", "quality-correctness"), ("package-initializer", "quality-correctness"), ("public-api", "quality-correctness"),
           ("consumer-behavior", "quality-correctness"), ("persisted-reference", "quality-correctness"),
           ("stable-identity", "authority-scope"), ("documentation-preserved", "authority-scope")]
_COVERAGE = {"mandatory": True, "contract-ids": ["behavioral-baseline", "public-api", "consumer", "persistence-identity"],
    "proves": "Fixed one-argument integer transform, public re-export, consumer, persisted reference and identity preservation against controller-owned pre-change bytes; requested module move or bounded typo.",
    "does_not_prove": "No executed runtime, arbitrary Python, actual prior test execution, model reasoning order or useful internal skill activation.",
    "runtime_behavior": "unverified", "external_action": "unverified",
    "prerequisites": ["trusted registered original bytes", "supported bounded AST", "post-change fixture readable"]}


class _Unavailable(Exception):
    pass


def _read(project: Path, name: str) -> bytes:
    root = Path(project)
    path = root / name
    if root.is_symlink() or getattr(root, "is_junction", lambda: False)() or not root.is_dir():
        raise _Unavailable("unsafe root")
    if (path.is_symlink() or getattr(path, "is_junction", lambda: False)() or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 4096):
        raise _Unavailable("unsafe or oversized member")
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
            raise _Unavailable("linked member parent")
    data = path.read_bytes()
    if len(data) > 4096:
        raise _Unavailable("oversized member")
    return data


def _tree(project: Path, name: str) -> ast.Module:
    return _parse(_read(project, name))


def _parse(data: bytes) -> ast.Module:
    try:
        value = ast.parse(data.decode("utf-8"))
    except (UnicodeError, ValueError, SyntaxError, RecursionError):
        raise _Unavailable("unsupported source") from None
    if len(list(ast.walk(value))) > 80:
        raise _Unavailable("oversized AST")
    return value


def _function(node: ast.AST, name: str) -> ast.FunctionDef:
    example = ast.parse(f"def {name}(value):\n    pass\n").body[0]
    if (not isinstance(node, ast.FunctionDef) or node.name != name or node.decorator_list
            or node.returns is not None or node.type_comment is not None or getattr(node, "type_params", [])
            or ast.dump(node.args, include_attributes=False) != ast.dump(example.args, include_attributes=False)
            or len(node.body) != 1 or not isinstance(node.body[0], ast.Return)):
        raise _Unavailable("unsupported function")
    return node


def _delta(project: Path, name: str) -> int | None:
    tree = _tree(project, name)
    if len(tree.body) != 1:
        raise _Unavailable("unsupported module")
    node = tree.body[0]
    if isinstance(node, ast.ImportFrom):
        if (node.level != 0 or len(node.names) != 1 or node.names[0].name != "normalize"
                or node.names[0].asname is not None or node.module not in {"ops.normalizer", "ops.offset"}
                or name != "legacy.py"):
            raise _Unavailable("unsupported re-export")
        destination = node.module.replace(".", "/") + ".py"
        if not (project / destination).exists():
            return None
        return _delta(project, destination)
    return _integer_delta(node)


def _integer_delta(node: ast.AST) -> int:
    result = _function(node, "normalize").body[0].value
    if (not isinstance(result, ast.BinOp) or not isinstance(result.op, ast.Add)
            or not isinstance(result.left, ast.Name) or result.left.id != "value"
            or not isinstance(result.right, ast.Constant) or type(result.right.value) is not int
            or result.right.value not in range(-10, 11)):
        raise _Unavailable("unsupported integer transform")
    return result.right.value


def _consumer_delta(project: Path) -> int | None:
    destination = _consumer_link(_tree(project, "consumer.py"))
    if destination is None:
        return 0
    return _delta(project, destination) if (project / destination).exists() else None


def _consumer_link(tree: ast.Module) -> str | None:
    if len(tree.body) != 2 or not isinstance(tree.body[0], ast.ImportFrom):
        raise _Unavailable("unsupported consumer")
    link = tree.body[0]
    if (link.level != 0 or link.module not in {"legacy", "ops.normalizer", "ops.offset"}
            or len(link.names) != 1 or link.names[0].name != "normalize"):
        raise _Unavailable("unsupported consumer import")
    alias = link.names[0].asname or "normalize"
    result = _function(tree.body[1], "render").body[0].value
    if isinstance(result, ast.Name) and result.id == "value":
        return None
    if (not isinstance(result, ast.Call) or not isinstance(result.func, ast.Name)
            or result.func.id != alias or result.keywords or len(result.args) != 1
            or not isinstance(result.args[0], ast.Name) or result.args[0].id != "value"):
        raise _Unavailable("unsupported consumer call")
    return link.module.replace(".", "/") + ".py"


def _registry() -> tuple[dict, str]:
    path = framework_root() / _REGISTRY
    try:
        if (path.parent.is_symlink() or getattr(path.parent, "is_junction", lambda: False)()
                or path.is_symlink() or getattr(path, "is_junction", lambda: False)()
                or not path.is_file() or path.stat().st_size > 100_000):
            raise ValueError("unsafe registered cases")
        data = path.read_bytes()
        if len(data) > 100_000:
            raise ValueError("oversized registry")
        value = json.loads(data.decode("utf-8"))
        rows = value.get("cases") if isinstance(value, dict) else None
        if not isinstance(rows, list) or len(rows) != len(_IDS):
            raise ValueError("invalid registered cases")
        cases = {}
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in cases
                    or row["id"] not in _IDS or row.get("oracle") != ORACLE_ID
                    or row.get("language") not in {"en", "ru"}
                    or row.get("polarity") not in {"positive", "negative"}
                    or not isinstance(row.get("files"), dict)
                    or set(row["files"]) != {"legacy.py", "consumer.py", "storage.json", "request.json", "README.md"}
                    or any(not isinstance(text, str) or len(text.encode("utf-8")) > 4096 for text in row["files"].values())):
                raise ValueError("invalid registered case")
            cases[row["id"]] = row
        if set(cases) != _IDS:
            raise ValueError("missing registered case")
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError):
        raise ValueError("unavailable refactor registry") from None
    return cases, hashlib.sha256(data).hexdigest()


def _cases() -> dict:
    return _registry()[0]


def validate_params(oracle_id: str, params: dict) -> dict:
    if oracle_id != ORACLE_ID or not isinstance(params, dict) or set(params) != {"case"}:
        raise ValueError("unknown oracle or parameters")
    if not isinstance(params["case"], str) or params["case"] not in _IDS:
        raise ValueError("unknown characterization case")
    return {"case": params["case"]}


def oracle_metadata(oracle_id: str = ORACLE_ID) -> dict:
    if oracle_id != ORACLE_ID:
        raise ValueError("unknown oracle")
    _, registry_digest = _registry()
    value = {"id": ORACLE_ID, "fixture": _FIXTURE, "params": {"case": sorted(_IDS)},
        "registry-digest": registry_digest,
        "check-ids": [key for key, _ in _CHECKS],
        "check-contracts": [{"id": key, "category": category, "mandatory": True} for key, category in _CHECKS],
        "coverage": _COVERAGE,
        "correctness": {"mandatory": True,
            "proves": "Controls preserve the original characterized integer mapping; mutations detect wrong behavior, dead consumers, missing re-exports and changed identities.",
            "does_not_prove": "Not a general refactoring oracle.", "prerequisites": ["registered calibration passes"]}}
    return value


def grade(oracle_id: str, project: Path, context: dict, params: dict) -> dict:
    validate_params(oracle_id, params)
    try:
        row = _cases()[params["case"]]
    except ValueError:
        return {"status": "inconclusive", "checks": [], "reason": "trusted registry unavailable", "coverage": _COVERAGE,
            "metrics": {"mandatory_passed": 0, "mandatory_total": len(_CHECKS)}}
    original = row["files"]
    if not isinstance(context, dict) or any(name not in original or not isinstance(value, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", value) for name, value in context.items()):
        raise ValueError("invalid original digest map")
    if any(value.lower() != hashlib.sha256(original[name].encode()).hexdigest() for name, value in context.items()):
        raise ValueError("initial fixture differs from registered characterization")
    try:
        # Derive the characterization in memory from trusted original bytes;
        # never materialize a grader baseline in candidate-writable temp paths.
        if set(original) != {"legacy.py", "consumer.py", "storage.json", "request.json", "README.md"}:
            raise ValueError("unregistered original path")
        original_tree = _parse(original["legacy.py"].encode())
        if len(original_tree.body) != 1:
            raise ValueError("invalid trusted original module")
        expected = _integer_delta(original_tree.body[0])
        baseline_ok = _consumer_link(_parse(original["consumer.py"].encode())) == "legacy.py"
        if not baseline_ok:
            raise ValueError("invalid trusted characterization baseline")
        request = json.loads(original["request.json"])
        current = _delta(project, "legacy.py") if (project / "legacy.py").exists() else None
        consumer = _consumer_delta(project) if (project / "consumer.py").exists() else None
        storage = json.loads(_read(project, "storage.json"))
        moved = request["action"] == "move"
        target = request["target"]
        public_source = _tree(project, "legacy.py") if (project / "legacy.py").exists() else None
        if moved:
            goal = (public_source is not None and len(public_source.body) == 1 and isinstance(public_source.body[0], ast.ImportFrom)
                    and public_source.body[0].module == target.removesuffix(".py").replace("/", ".")
                    and (project / target).exists())
        else:
            goal = (public_source is not None and _read(project, "legacy.py") == original["legacy.py"].replace("Tranform", "Transform").encode()
                    and not (project / "ops").exists())
        expected_storage = json.loads(original["storage.json"])
        initializer = project / "ops/__init__.py"
        package_ok = not initializer.exists() or not _tree(project, "ops/__init__.py").body
        values = {"characterization-baseline": baseline_ok, "structural-goal": bool(goal), "package-initializer": package_ok,
            "public-api": current == expected, "consumer-behavior": consumer == expected,
            "persisted-reference": isinstance(storage, dict) and storage.get("function") == expected_storage["function"] and current == expected,
            "stable-identity": type(storage) is dict and type(storage.get("schema-version")) is int and storage == expected_storage,
            "documentation-preserved": _read(project, "README.md") == original["README.md"].encode()}
    except (OSError, _Unavailable) as error:
        return {"status": "inconclusive", "checks": [], "reason": "unavailable or unsupported fixture", "coverage": oracle_metadata()["coverage"],
            "metrics": {"mandatory_passed": 0, "mandatory_total": len(_CHECKS)}}
    except (ValueError, UnicodeError, RecursionError) as error:
        return {"status": "inconclusive", "checks": [], "reason": "invalid fixture or trusted baseline", "coverage": oracle_metadata()["coverage"],
            "metrics": {"mandatory_passed": 0, "mandatory_total": len(_CHECKS)}}
    checks = [{"id": key, "oracle": ORACLE_ID, "category": category, "mandatory": True,
        "status": "pass" if values[key] else "fail", "observed-violation": not values[key]} for key, category in _CHECKS]
    return {"status": "pass" if all(values.values()) else "fail", "checks": checks,
        "coverage": oracle_metadata()["coverage"], "metrics": {"mandatory_passed": sum(values.values()), "mandatory_total": len(_CHECKS)},
        "characterization": {"inputs": [-1, 0, 1, 41],
            "original-outputs": [value + expected for value in (-1, 0, 1, 41)],
            "public-delta": current, "consumer-delta": consumer,
            "original-file-digests": {name: hashlib.sha256(content.encode()).hexdigest() for name, content in original.items()},
            "evidence-owner": "trusted-controller", "candidate-pre-mutation-reasoning": "unverified"}}


def calibration(oracle_id: str = ORACLE_ID, framework: Path | None = None) -> dict:
    oracle_metadata(oracle_id)
    if framework is not None and Path(framework).resolve() != framework_root().resolve():
        raise ValueError("calibration must use the trusted framework root")
    controls = []
    for case_id, row in _cases().items():
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for name, content in row["files"].items():
                (project / name).write_text(content, encoding="utf-8", newline="\n")
            request = json.loads(row["files"]["request.json"])
            if request["action"] == "move":
                target = project / request["target"]
                target.parent.mkdir()
                target.write_text(row["files"]["legacy.py"], encoding="utf-8", newline="\n")
                module = request["target"].removesuffix(".py").replace("/", ".")
                (project / "legacy.py").write_text(f"from {module} import normalize\n", encoding="utf-8", newline="\n")
            else:
                (project / "legacy.py").write_text(row["files"]["legacy.py"].replace("Tranform", "Transform"), encoding="utf-8", newline="\n")
            controls.append({"id": case_id, "status": "pass" if grade(ORACLE_ID, project, {}, {"case": case_id})["status"] == "pass" else "fail"})
            if case_id == "refactor-move-en":
                correct = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
                mutations = [
                    ("changed-behavior", "ops/normalizer.py", b"def normalize(value):\n    return value + 2\n", "public-api"),
                    ("dead-consumer", "consumer.py", b"from legacy import normalize\ndef render(value):\n    return value\n", "consumer-behavior"),
                    ("missing-public-api", "legacy.py", None, "public-api"),
                    ("missing-target", "ops/normalizer.py", None, "structural-goal"),
                    ("changed-identity", "storage.json", b'{"schema-version":1,"record-id":"item-v2","function":"legacy.normalize"}', "stable-identity"),
                    ("boolean-schema", "storage.json", b'{"schema-version":true,"record-id":"item-v1","function":"legacy.normalize"}', "stable-identity"),
                    ("changed-reference", "storage.json", b'{"schema-version":1,"record-id":"item-v1","function":"ops.normalizer.normalize"}', "persisted-reference"),
                    ("documentation-drift", "README.md", b"unrequested documentation\n", "documentation-preserved")]
                for mutation_id, name, content, expected_check in mutations:
                    path = project / name
                    if content is None:
                        path.unlink()
                    else:
                        path.write_bytes(content)
                    result = grade(ORACLE_ID, project, {}, {"case": case_id})
                    detected = result["status"] == "fail" and any(c["id"] == expected_check and c["status"] == "fail" for c in result["checks"])
                    controls.append({"id": mutation_id, "status": "pass" if detected else "fail"})
                    path.write_bytes(correct[name])
                target = project / "ops/normalizer.py"
                target.write_text("import os\n", encoding="utf-8")
                controls.append({"id": "unsupported-grammar", "status": "pass" if grade(ORACLE_ID, project, {}, {"case": case_id})["status"] == "inconclusive" else "fail"})
    return {"id": ORACLE_ID, "status": "pass" if all(row["status"] == "pass" for row in controls) else "fail",
        "outcomes": controls, "coverage": oracle_metadata()["coverage"], "correctness": oracle_metadata()["correctness"]}


def expected_observation(params: dict) -> dict:
    row = _cases()[validate_params(ORACLE_ID, params)["case"]]
    moved = json.loads(row["files"]["request.json"])["action"] == "move"
    return {"expected-result": "changed", "expected-findings": [], "expected-questions": [],
        "required-procedures": {}, "permitted-procedures": ["refactoring"] if moved else [],
        "security-findings": [], "forbidden-marker": _MARKER}
