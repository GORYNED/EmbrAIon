"""Audit manually maintained consumer files for concrete routing authority."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

from .common import project_root, read_yaml
from .policy import read_deployments_config, read_routing_config
from .project import HOST_COMPONENTS, projection_plan


_FACT_KEYS = (
    "provider", "model", "deployment", "effort", "fallback", "fallbacks",
    "capabilities", "billing", "sku", "selector", "credentialRef",
    "expectedProvider", "expectedResponseModel", "expectedResponseModels",
    "expectedResponseModelPattern", "taskClassAliases",
)
_ASSIGNMENT = re.compile(
    r"(?<![\w.-])(?P<key>['\"]?(?:" + "|".join(_FACT_KEYS) +
    r")['\"]?)\s*(?P<operator>[:=])\s*"
)
_QUOTED = re.compile(r"(?P<quote>['\"])(?P<value>(?:\\.|(?!\1).)*)\1")
_BARE = re.compile(r"[A-Za-z0-9_./:@+-]+")
_NON_VALUES = {"null", "none", "true", "false", "str", "string", "object", "array", "number", "integer", "bool", "boolean"}
_CAPABILITY_FIELDS = re.compile(r"['\"]?(?:data-classes|access-modes|roles|task-classes)['\"]?\s*:")
_BILLING_FIELDS = re.compile(r"['\"]?(?:mode|plan)['\"]?\s*:")
_ANY_ASSIGNMENT = re.compile(r"(?<![\w.-])['\"]?[\w.-]+['\"]?\s*[:=]\s*")
_TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ps1", ".psm1", ".py", ".sh"}
_SKIP_DIRECTORIES = {".git", ".embraion", "__pycache__", "Library", "node_modules", ".venv", "venv", "bin", "obj"}


def _without_comment(line: str, suffix: str) -> str:
    if suffix == ".json":
        return line
    quote = ""
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif quote and character == "\\":
            escaped = True
        elif character == quote:
            quote = ""
        elif not quote and character in "'\"":
            quote = character
        elif not quote and character == "#":
            return line[:index]
        elif not quote and line[index:index + 2] == "//" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _manual_files(root: Path) -> Iterable[Path]:
    try:
        repository = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except FileNotFoundError as error:
        if (root / ".git").exists():
            raise RuntimeError("Git is required to audit repository routing authority") from error
        repository = None
    if repository is not None and repository.returncode == 0 and repository.stdout.strip() == "true":
        try:
            listed = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                capture_output=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("Could not enumerate non-ignored repository files") from error
        if listed.returncode != 0:
            raise RuntimeError("Could not enumerate non-ignored repository files")
        for relative in sorted(set(listed.stdout.split(b"\0"))):
            if relative:
                yield root / os.fsdecode(relative)
        return
    for directory, child_directories, filenames in os.walk(root):
        child_directories[:] = sorted(name for name in child_directories
                                      if name not in _SKIP_DIRECTORIES)
        for name in sorted(filenames):
            yield Path(directory) / name


def _concrete_markers(project: Path) -> set[str]:
    deployments = read_deployments_config(project)
    routing = read_routing_config(project)
    markers = set(deployments["deployments"]) | set(deployments.get("providers") or {})
    markers.update(str(item["model"]) for item in deployments["deployments"].values())
    markers.update(str(item["billing"]["plan"]) for item in deployments["deployments"].values()
                   if (item.get("billing") or {}).get("plan"))
    markers.update((routing.get("candidate-groups") or {}).keys())
    for name in ("execution.yaml", "pricing.yaml"):
        path = project / ".embraion" / name
        if not path.is_file():
            continue
        data = read_yaml(path) or {}
        if name == "execution.yaml":
            for binding in (data.get("bindings") or {}).values():
                for key in ("selector", "credentialRef", "expectedProvider",
                            "expectedResponseModelPattern"):
                    if binding.get(key):
                        markers.add(str(binding[key]))
                markers.update(str(value) for value in binding.get("expectedResponseModels") or [])
        else:
            for source in (data.get("sources") or {}).values():
                for sku_id, sku in (source.get("skus") or {}).items():
                    markers.add(str(sku_id))
                    if sku.get("sku"):
                        markers.add(str(sku["sku"]))
    return {value for value in markers if value}


def _literal(value: str, operator: str, *, allow_bare: bool = True) -> str | None:
    """Accept assigned scalar literals, not schema objects or runtime expressions."""
    quoted = _QUOTED.match(value)
    if quoted:
        scalar = quoted.group("value")
        tail = value[quoted.end():].lstrip()
    else:
        if operator == "=" or not allow_bare:
            return None
        bare = _BARE.match(value)
        if not bare:
            return None
        scalar = bare.group()
        tail = value[bare.end():].lstrip()
    if tail and tail[0] not in ",]}#;":
        return None
    if not scalar or scalar.lower() in _NON_VALUES or scalar.startswith(("$", "<", "{")):
        return None
    return scalar


def _is_concrete_assignment(line: str, suffix: str, markers: set[str]) -> bool:
    stripped = line.lstrip()
    if not stripped or stripped.startswith(("#", "//", "*", ">")):
        return False
    for match in _ASSIGNMENT.finditer(line):
        key = match.group("key").strip("'\"")
        value = line[match.end():].lstrip()
        if key in {"capabilities", "billing"}:
            field = _CAPABILITY_FIELDS if key == "capabilities" else _BILLING_FIELDS
            if value.startswith("{"):
                for nested in field.finditer(value):
                    nested_value = value[nested.end():].lstrip()
                    if key == "capabilities" and nested_value.startswith("["):
                        if re.search(r"['\"]?[\w-]+['\"]?", nested_value[1:].split("]", 1)[0]):
                            return True
                    elif _literal(nested_value, ":") is not None:
                        return True
            continue
        if key in {"fallbacks", "expectedResponseModels", "taskClassAliases"}:
            if value.startswith("["):
                entries = value[1:].split("]", 1)[0].strip()
                if entries and (entries[0] in "'\"{" or
                                (suffix in {".yaml", ".yml", ".md", ".txt"} and
                                 entries.split(",", 1)[0].strip().lower() not in _NON_VALUES)):
                    return True
            continue
        literal = _literal(value, match.group("operator"),
                           allow_bare=suffix in {".yaml", ".yml", ".md", ".txt"})
        if literal is not None:
            return True
        if match.group("operator") == ":" and _literal(value, ":") in markers:
            return True
    # A concrete canonical ID assigned under a project-specific key is authority too.
    for match in _ANY_ASSIGNMENT.finditer(line):
        if _literal(line[match.end():].lstrip(), match.group().rstrip()[-1],
                    allow_bare=suffix in {".yaml", ".yml", ".md", ".txt"}) in markers:
            return True
    return False


def _is_concrete_line(line: str, suffix: str, markers: set[str], in_fence: bool) -> bool:
    line = _without_comment(line, suffix)
    stripped = line.strip()
    if not stripped:
        return False
    if suffix in {".md", ".txt"} and not in_fence:
        # Prose may mention a past choice; a standalone canonical ID is still a duplicate.
        if stripped.strip("`'\"") in markers:
            return True
        if not re.match(r"^(?:-\s*)?(?:\{|['\"])?(?:" + "|".join(_FACT_KEYS) + r")[\s'\"]*[:=]", stripped):
            return False
    return _is_concrete_assignment(line, suffix, markers)


def _verified_projection_files(root: Path) -> set[str]:
    verified: set[str] = set()
    for host in HOST_COMPONENTS:
        try:
            components = None
            if host == "claude-code":
                config = root / ".embraion/claude-native.yaml"
                if config.exists() or config.is_symlink():
                    components = ["agents", "skills", "scoped-agents"]
            plan = projection_plan(host, root, components=components)
            # The plan compares each target with freshly generated canonical bytes
            # and checks path boundaries. A local ownership ledger is not needed
            # for the narrow audit exemption, including in a fresh checkout.
            verified.update(plan.get("unchanged") or [])
        except (RuntimeError, OSError, ValueError, AttributeError, TypeError):
            continue
    return verified


def audit_routing_authority(project: Path | None = None, *,
                            paths: Iterable[Path] | None = None) -> list[dict[str, str]]:
    """Report concrete facts; generated projections are exempt only when verified."""
    root = project_root(project)
    markers = _concrete_markers(root)
    verified = _verified_projection_files(root)
    files = paths if paths is not None else _manual_files(root)
    findings: list[dict[str, str]] = []
    for path in files:
        # Explicit paths may use a filesystem alias (for example /var on macOS)
        # while project_root has already resolved to the canonical spelling.
        path = Path(path).resolve()
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative.startswith((".embraion/", ".git/")) or relative in verified:
            continue
        if any(part in _SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        contents = path.read_text(encoding="utf-8", errors="ignore")
        in_fence = False
        for number, line in enumerate(contents.splitlines(), 1):
            if path.suffix.lower() == ".md" and line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if _is_concrete_line(line, path.suffix.lower(), markers, in_fence):
                findings.append({"path": relative, "line": str(number),
                                 "reason": "duplicate concrete routing fact"})
    return findings
