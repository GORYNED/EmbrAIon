"""Read-only, evidence-bound bootstrap planning and conservative application.

Semantic inspection, document authoring, routing and command execution belong to
the Core skill. This helper never runs repository commands or installs tooling.
"""
from __future__ import annotations

import copy
import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .common import framework_root, read_json, read_yaml, write_yaml
from .policy import path_matches
from .security import redact_text

_WRITABLE = ("knowledge", "policy", "validation")
_PROJECT_SCHEMAS = {
    "project": "project", "knowledge": "knowledge", "policy": "policy",
    "validation": "validation", "agents": "agents", "routing": "routing",
    "deployments": "deployments", "execution": "execution-config",
    "pricing": "pricing-config",
}
_DOCS = {
    "constitution": ("AGENTS.md", "CONSTITUTION.md", "docs/constitution.md"),
    "architecture": ("ARCHITECTURE.md", "docs/architecture.md"),
    "source-authority": ("docs/source-authority.md",),
    "compatibility": ("docs/compatibility.md",),
    "persistence": ("docs/persistence.md",),
    "engineering-workflow": ("CONTRIBUTING.md", "docs/engineering-workflow.md"),
    "specification": ("SPECIFICATION.md", "docs/specification.md"),
}
_SKIP = {".git", ".venv", "node_modules", "__pycache__", ".embraion", "build", "dist", "site"}
_OPTION_NAME = re.compile(r"--([A-Za-z0-9_-]+)")
_SENSITIVE_OPTION = re.compile(r"(?i)(?:^|[-_])(?:api[-_]?key|apikey|key|token|password|secret|credentials?|auth|authorization|bearer)(?:$|[-_])")
_CREDENTIAL_VALUE = re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|credentials?)\s*[:=]\s*(?!\$|env:|<|REDACTED|CHANGEME)[^\s]+")


def _credential_bearing(text: str) -> bool:
    return (any(_SENSITIVE_OPTION.search(match.group(1)) for match in _OPTION_NAME.finditer(text))
            or bool(_CREDENTIAL_VALUE.search(text)) or redact_text(text) != text)


def _configuration_has_credentials(value: Any) -> bool:
    if isinstance(value, str):
        return _credential_bearing(value)
    if isinstance(value, dict):
        for key, child in value.items():
            if (_SENSITIVE_OPTION.search(str(key)) and isinstance(child, str)
                    and not child.startswith(("env:", "$", "<"))):
                return True
            if _configuration_has_credentials(child):
                return True
    if isinstance(value, list):
        return any(_configuration_has_credentials(child) for child in value)
    return False


def _safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if (not parts or PurePosixPath(relative).is_absolute() or "\\" in relative
            or any(part in {".", ".."} or ":" in part for part in parts)
            or str(PurePosixPath(relative)) != relative):
        raise RuntimeError(f"Unsafe bootstrap path: {relative}")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise RuntimeError(f"Linked bootstrap path: {relative}")
    if not current.resolve().is_relative_to(root):
        raise RuntimeError(f"Bootstrap path escapes project: {relative}")
    return current


def _hash(path: Path) -> str:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise RuntimeError(f"Bootstrap evidence exceeds 4 MiB inspection bound: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(name: str, value: Any) -> None:
    schema = read_json(framework_root() / "schemas" / f"{name}.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise RuntimeError(f"Invalid bootstrap {name}: schema validation failed ({errors[0].validator}).")


def _read_yaml(path: Path) -> Any:
    try:
        return read_yaml(path)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise RuntimeError(f"Cannot inspect bootstrap YAML: {path.name}") from error


def _inventory(root: Path) -> tuple[list[str], list[str]]:
    result = []
    limitations = []

    def unreadable(error: OSError) -> None:
        raise RuntimeError("Bootstrap inventory is incomplete: unreadable repository directory.") from error

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        base = Path(directory)
        for name in dirs:
            target = base / name
            relative = target.relative_to(root).as_posix()
            if name in _SKIP:
                limitations.append(f"Excluded discovery directory: {relative}; concern absence is not established.")
            elif target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
                limitations.append(f"Linked directory cannot serve as bootstrap evidence: {relative}.")
        dirs[:] = sorted(d for d in dirs if d not in _SKIP and not (base / d).is_symlink()
                         and not (hasattr(base / d, "is_junction") and (base / d).is_junction()))
        for name in sorted(files):
            relative = (base / name).relative_to(root).as_posix()
            # Ignore linked source files; they cannot be evidence or mutation targets.
            if not (base / name).is_symlink():
                _safe_path(root, relative)
                result.append(relative)
                if len(result) > 25000:
                    raise RuntimeError("Bootstrap inventory exceeds 25000 files; narrow repository discovery before proceeding.")
            else:
                limitations.append(f"Linked file cannot serve as bootstrap evidence: {relative}.")
    return sorted(result), limitations


def plan_bootstrap(project: Path) -> dict[str, Any]:
    root = project.resolve()
    if not _safe_path(root, ".embraion/project.yaml").is_file():
        raise RuntimeError("Bootstrap requires an initialized project; run embraion init first.")
    snapshots: dict[str, str] = {}
    configs: dict[str, Any] = {}
    # Snapshot every canonical config, including those we never write.
    config_root = _safe_path(root, ".embraion")
    def config_unreadable(error: OSError) -> None:
        raise RuntimeError("Bootstrap cannot inspect all manual project configuration.") from error

    for directory, dirs, files in os.walk(config_root, followlinks=False, onerror=config_unreadable):
        dirs[:] = sorted(d for d in dirs if d not in {"state", "cache"})
        for name in dirs:
            _safe_path(root, (Path(directory) / name).relative_to(root).as_posix())
        for name in sorted(files):
            relative = (Path(directory) / name).relative_to(root).as_posix()
            snapshots[relative] = _hash(_safe_path(root, relative))
    for path in sorted(config_root.glob("*.yaml")):
        relative = path.relative_to(root).as_posix()
        path = _safe_path(root, relative)
        snapshots[relative] = _hash(path)
        name = path.stem
        value = _read_yaml(path)
        if name in _PROJECT_SCHEMAS:
            _validate(_PROJECT_SCHEMAS[name], value)
        configs[name] = value
        if _configuration_has_credentials(value):
            raise RuntimeError("Bootstrap configuration contains possible inline credentials; use environment references before producing a plan.")
    pricing_snapshot = config_root / "pricing.snapshot.json"
    if pricing_snapshot.is_file():
        _validate("pricing-snapshot", read_json(_safe_path(root, ".embraion/pricing.snapshot.json")))
    for name in _WRITABLE:
        if name not in configs:
            raise RuntimeError(f"Missing .embraion/{name}.yaml; normalize the project first.")
    inventory, discovery_limitations = _inventory(root)
    evidence: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    limitations = discovery_limitations + ["Document names suggest authority; review their contents before applying.",
                  "No repository commands were executed; profile success remains unverified.",
                  "Routing, deployments, agents, privacy, review and enforcement are preserved."]

    def record(path: str, kind: str, **fields: Any) -> None:
        snapshots[path] = _hash(_safe_path(root, path))
        evidence.append({"path": path, "kind": kind, **fields})

    knowledge = copy.deepcopy(configs["knowledge"])
    slots = knowledge.setdefault("slots", {})
    for slot, names in _DOCS.items():
        matches = [name for name in names if name in inventory]
        for name in matches:
            record(name, "contract-candidate", slot=slot)
        excluded = [name for name in matches if any(path_matches(name, configs["policy"]["sources"][category]) for category in ("generated", "external"))]
        if excluded:
            limitations.append(f"{slot} source ownership requires review; generated/external candidates are not bound.")
            continue
        if not slots.get(slot) and len(matches) == 1:
            slots[slot] = matches[0]
        elif len(matches) > 1:
            limitations.append(f"Ambiguous {slot} sources: {', '.join(matches)}; no binding changed.")
    commands: dict[str, list[str]] = {"fast": [], "affected": [], "full": []}
    if "package.json" in inventory:
        record("package.json", "manifest")
        try:
            package = read_json(root / "package.json")
        except (ValueError, UnicodeError) as error:
            raise RuntimeError(f"Cannot inspect package.json: {error}") from error
        if not isinstance(package, dict):
            raise RuntimeError("Cannot inspect package.json: expected an object.")
        # Wrapper commands refer only to scripts that actually exist. Their bodies
        # remain subject to semantic review; no lifecycle/install is run here.
        scripts = package.get("scripts", {})
        if isinstance(scripts, dict):
            for name in ("lint", "typecheck", "test", "build"):
                if not isinstance(scripts.get(name), str) or not scripts[name].strip():
                    continue
                if _credential_bearing(scripts[name]):
                    limitations.append(f"Credential-bearing package script {name} omitted; use environment references and review its safety.")
                    continue
                if any(p in inventory for p in ("pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb")):
                    limitations.append(f"Package manager needs review for script {name}; no npm command added.")
                    continue
                command = f"npm run {name}"
                record("package.json", "command-candidate", command=command, **{"context-review": True})
                commands["full"].append(command)
                if name != "build":
                    commands["affected"].append(command)
                if name in {"lint", "typecheck"}:
                    commands["fast"].append(command)
    for relative in inventory:
        filename = Path(relative).name
        if relative.startswith(".github/workflows/") and filename.endswith((".yml", ".yaml")):
            record(relative, "ci-workflow")
            workflow = _read_yaml(root / relative) or {}
            if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs", {}), dict):
                limitations.append(f"Unrecognized workflow structure in {relative}; no commands inferred.")
                continue
            for job_name, job in (workflow.get("jobs", {}) or {}).items():
                if not isinstance(job, dict):
                    continue
                for step_index, step in enumerate(job.get("steps", []) or [], start=1):
                    if not isinstance(step, dict) or not isinstance(step.get("run"), str):
                        continue
                    record(relative, "command-candidate", **{"context-review": True, "job": str(job_name), "step": step_index})
                    command = step["run"].strip()
                    if _credential_bearing(command):
                        limitations.append(f"Credential-bearing CI command omitted in {relative}; use environment references and review its safety.")
                        continue
                    plain_context = not any(key in job for key in ("if", "strategy", "container", "defaults", "env", "services")) and not any(key in step for key in ("if", "working-directory", "env", "shell")) and not any(key in workflow for key in ("defaults", "env"))
                    # A small allowlist admits literal, context-free check commands.
                    # Interpolation, shell composition, installs and arbitrary tools
                    # remain evidence for the skill rather than executable guesses.
                    known = re.fullmatch(r"(?:python(?:3)? -m pytest|pytest|python(?:3)? -m unittest discover|python(?:3)? -m ruff check|ruff check)(?: [A-Za-z0-9_./=-]+)*", command)
                    if plain_context and known:
                        record(relative, "command-candidate", command=command, **{"context-review": True, "job": str(job_name), "step": step_index})
                        commands["full"].append(command)
                        commands["affected"].append(command)
                        if "ruff check" in command or "unittest discover -s tests/unit" in command:
                            commands["fast"].append(command)
                    # CI context is never copied blindly into a local executable profile.
                    limitations.append(f"CI command in {relative} needs local context review; inspect its source.")
        elif filename in {"Makefile", "Taskfile.yml", "Taskfile.yaml", "justfile", "pyproject.toml", "tox.ini", "setup.cfg"} or filename.endswith((".csproj", ".sln", ".md")):
            record(relative, "workflow-source")
    validation = copy.deepcopy(configs["validation"])
    for profile, discovered in commands.items():
        existing = validation["profiles"].get(profile)
        if existing == [] or existing is None:
            validation["profiles"][profile] = list(dict.fromkeys(discovered))
        elif isinstance(existing, dict) and existing.get("commands") == [] and not existing.get("parameters"):
            existing["commands"] = list(dict.fromkeys(discovered))
    policy = copy.deepcopy(configs["policy"])
    # Existing ownership decisions are authoritative. Only conventional discovered
    # documents can augment an empty canonical list; generated/vendor classification
    # requires inspection by the skill and is never inferred from a directory name.
    if not policy["sources"]["canonical"] and not any(policy["sources"][key] for key in ("protected", "generated", "external")):
        policy["sources"]["canonical"] = sorted({item["path"] for item in evidence if item["kind"] == "contract-candidate"})
    for name, candidate in (("knowledge", knowledge), ("policy", policy), ("validation", validation)):
        _validate(name, candidate)
        if candidate != configs[name]:
            changes.append({"path": f".embraion/{name}.yaml", "value": candidate})
    plan = {"schema-version": 1, "root": str(root), "inventory": inventory,
            "snapshots": snapshots, "evidence": evidence, "changes": changes,
            "limitations": list(dict.fromkeys(limitations)), "requires-review": True}
    _validate("bootstrap", plan)
    return plan


def apply_bootstrap(project: Path, plan: dict[str, Any]) -> dict[str, Any]:
    _validate("bootstrap", plan)
    root = project.resolve()
    if plan["root"] != str(root):
        raise RuntimeError("Bootstrap plan belongs to a different project root.")
    for relative, expected in plan["snapshots"].items():
        path = _safe_path(root, relative)
        if not path.is_file() or _hash(path) != expected:
            raise RuntimeError(f"Stale bootstrap evidence: {relative}")
    for change in plan["changes"]:
        _safe_path(root, change["path"])
        if change["path"] not in {f".embraion/{name}.yaml" for name in _WRITABLE}:
            raise RuntimeError("Bootstrap cannot mutate this config.")
    # Recompute rather than trusting editable proposed YAML. This also validates
    # all current/candidate schemas before the first mutation and catches new files.
    if plan != plan_bootstrap(root):
        raise RuntimeError("Bootstrap plan is stale or modified; generate and review a fresh plan.")
    for change in plan["changes"]:
        write_yaml(_safe_path(root, change["path"]), change["value"])
    return {"updated": [change["path"] for change in plan["changes"]],
            "limitations": plan["limitations"], "validation-executed": False}
