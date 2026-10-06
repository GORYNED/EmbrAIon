"""Read-only, project-configured Unity/C# organization checks."""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from .common import framework_root, project_root, read_json, read_yaml


MAX_FILES = 30000
MAX_BYTES = 1024 * 1024
GUID = re.compile(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$")
NAMESPACE_TOKENS = re.compile(r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*([;{])|[{}]")
LFS = b"version https://git-lfs.github.com/spec/v1"
BOUNDARY = {"Runtime": {"Runtime"}, "Editor": {"Runtime", "Editor"}, "Tests": {"Runtime", "Editor", "Tests"}}
FILENAME_STEM = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:-\d+(?:\.\d+)+)?$")
# Basenames whose spelling an ecosystem, a package manager, Unity, or an agent host dictates.
CANONICAL_BASENAMES = frozenset({
    "README.md", "CHANGELOG.md", "LICENSE", "LICENSE.md", "SECURITY.md", "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md", "SUPPORT.md", "GOVERNANCE.md", "CODEOWNERS", "AGENTS.md", "CLAUDE.md", "SKILL.md",
    "package.json", "package-lock.json", "packages-lock.json", "manifest.json", "link.xml",
    "ProjectVersion.txt",
})
# Host-native suffixes are meaningful only directly inside their host directory; the identifier
# before the suffix still follows the filename style.
HOST_SUFFIXES = ((".github/agents", ".agent.md"), (".github/instructions", ".instructions.md"),
                 (".github/prompts", ".prompt.md"))
# EmbrAIon's generated scoped Claude profiles use a reserved double-hyphen namespace.
SCOPED_PROFILE = re.compile(r"^\.claude/agents/embraion--[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{12}\.md$")


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f"Organization Git operation failed ({' '.join(args[:2])}): "
                           + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def _safe(path: str) -> bool:
    return bool(path and not path.startswith("/") and "\\" not in path and
                "\x00" not in path and all(part not in ("", ".", "..") for part in path.split("/")))


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def _in_roots(path: str, roots: list[str]) -> bool:
    return any(root.rstrip("/") in ("", ".") or _under(path, root) for root in roots)


def _excluded(path: str, config: dict[str, Any]) -> bool:
    from fnmatch import fnmatchcase
    return any(fnmatchcase(path, pattern) or _under(path, pattern.rstrip("/"))
               or (pattern.endswith("/**") and _under(path, pattern[:-3]))
               for pattern in config.get("exclude", []))


def _scope_overlap(path: str, config: dict[str, Any]) -> bool:
    if _excluded(path, config):
        return False
    scopes: list[str] = []
    namespace = config.get("namespaces")
    assemblies = config.get("assemblies")
    meta = config.get("unity_meta")
    if namespace and namespace.get("enabled", True):
        scopes.extend(rule["path"] for rule in namespace["rules"])
    if assemblies and assemblies.get("enabled", True):
        scopes.extend(assemblies["roots"])
    if meta and meta.get("enabled", True):
        scopes.extend(meta["roots"])
    return any(not _excluded(scope, config) and (_under(path, scope) or _under(scope, path))
               for scope in scopes)


def _symlink_in_scope(path: str, config: dict[str, Any]) -> bool:
    return _scope_overlap(path, config)


def _selected(path: str, config: dict[str, Any]) -> bool:
    if _excluded(path, config):
        return False
    if path.endswith(".cs") and config.get("namespaces") and config["namespaces"].get("enabled", True):
        return True
    if path.endswith((".asmdef", ".asmdef.meta")) and config.get("assemblies") and config["assemblies"].get("enabled", True):
        return True
    if config.get("unity_meta") and config["unity_meta"].get("enabled", True):
        if path.endswith(".meta"):
            return True
        return PurePosixPath(path).suffix in config["unity_meta"].get("require_for_extensions", [])
    return False


def _read_config(root: Path, path: Path) -> dict[str, Any] | None:
    relative = path.relative_to(root)
    if not relative.parts or ".." in relative.parts:
        raise RuntimeError("Organization configuration path escapes project root")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError("Organization configuration path contains a symbolic link")
    try:
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise RuntimeError("Invalid organization configuration file")
        data = read_yaml(path)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise RuntimeError("Invalid organization configuration YAML") from None
    schema = read_json(framework_root() / "schemas" / "organization.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(e.absolute_path))
    if errors:
        error = errors[0]
        known = {"exclude", "namespaces", "assemblies", "unity_meta", "enabled",
                 "rules", "path", "namespace", "require_declaration", "exceptions",
                 "allow_missing", "roots", "path_rules", "layer", "allowed_edges",
                 "from", "to", "enforce_platforms", "require_for_extensions",
                 "check_move_identity", "require_for_all", "check_orphans", "filenames",
                 "extensions", "allow", "suffixes", "suffix", "case_collisions"}
        at = ".".join(str(part) if isinstance(part, int) or part in known else "<key>"
                      for part in error.absolute_path) or "<root>"
        raise RuntimeError(f"Invalid .embraion/organization.yaml at {at}")
    # JSON Schema deliberately limits path syntax; this also catches duplicate path
    # rules, which are ambiguous even when they contain identical values.
    for section, key in (("namespaces", "rules"), ("assemblies", "path_rules")):
        paths = [rule["path"] for rule in data.get(section, {}).get(key, [])]
        if len(paths) != len(set(paths)):
            raise RuntimeError(f"Duplicate organization {section} path rule")
    return data


def _snapshot_tree(root: Path, commit: str, config: dict[str, Any]) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    entries = _git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\x00")
    files: dict[str, bytes] = {}
    issues: list[dict[str, str]] = []
    for entry in filter(None, entries):
        header, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8", "surrogateescape")
        if not _safe(path):
            issues.append(_finding("unsafe_path", path, "Git tree contains an unsafe path"))
            continue
        mode, kind, oid = header.decode("ascii").split()
        if mode == "120000":
            if _symlink_in_scope(path, config):
                issues.append(_finding("unsafe_path", path, "Symbolic link overlaps a configured source scope"))
            continue
        if not _selected(path, config):
            continue
        if kind != "blob":
            continue
        if len(files) >= MAX_FILES:
            raise RuntimeError(f"Organization scan exceeds {MAX_FILES} files")
        size = int(_git(root, "cat-file", "-s", oid).strip())
        if size > MAX_BYTES:
            issues.append(_finding("oversize", path, f"File exceeds {MAX_BYTES} bytes"))
            continue
        files[path] = _git(root, "cat-file", "blob", oid)
    return files, issues


def _snapshot_worktree(root: Path, config: dict[str, Any]) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    files: dict[str, bytes] = {}
    issues: list[dict[str, str]] = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        retained: list[str] = []
        for name in dirs:
            candidate = Path(directory) / name
            rel = candidate.relative_to(root).as_posix()
            if name == ".git" or (name in {".venv", "node_modules", "Library", "Temp"}
                                  and not _scope_overlap(rel, config)):
                continue
            if candidate.is_symlink():
                if _symlink_in_scope(rel, config):
                    issues.append(_finding("unsafe_path", rel, "Symbolic link overlaps a configured source scope"))
                continue
            retained.append(name)
        dirs[:] = retained
        for name in names:
            path = (Path(directory) / name)
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                if _symlink_in_scope(rel, config):
                    issues.append(_finding("unsafe_path", rel, "Symbolic link overlaps a configured source scope"))
                continue
            if not _selected(rel, config):
                continue
            if not _safe(rel):
                issues.append(_finding("unsafe_path", rel, "Unsafe path is not scanned"))
                continue
            if not path.is_file():
                continue
            if len(files) >= MAX_FILES:
                raise RuntimeError(f"Organization scan exceeds {MAX_FILES} files")
            if path.stat().st_size > MAX_BYTES:
                issues.append(_finding("oversize", rel, f"File exceeds {MAX_BYTES} bytes"))
                continue
            files[rel] = path.read_bytes()
    return files, issues


def _needs_names(config: dict[str, Any]) -> bool:
    meta = config.get("unity_meta") or {}
    names = config.get("filenames") or {}
    return bool((meta and meta.get("enabled", True) and (meta.get("require_for_all") or meta.get("check_orphans")))
                or (names and names.get("enabled", True)))


def _names_tree(root: Path, commit: str) -> set[str]:
    raw = _git(root, "ls-tree", "-rz", "--name-only", "--full-tree", commit)
    return {path for path in raw.decode("utf-8", "surrogateescape").split("\x00") if _safe(path)}


def _names_worktree(root: Path) -> set[str]:
    """Return tracked and unignored untracked files that exist in the working tree."""
    try:
        raw = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    except RuntimeError:
        names = set()
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name != ".git"]
            names.update((Path(directory) / name).relative_to(root).as_posix() for name in files)
        return {path for path in names if _safe(path)}
    return {path for path in raw.decode("utf-8", "surrogateescape").split("\x00")
            if _safe(path) and os.path.lexists(root / path)}


def _unity_ignored(path: str) -> bool:
    # Unity does not import dot-prefixed or `~`-suffixed files and folders, so they carry no .meta.
    return any(part.startswith(".") or part.endswith("~") for part in path.split("/"))


def _meta_inventory(names: set[str], config: dict[str, Any], issues: list[dict[str, str]]) -> None:
    meta = config.get("unity_meta") or {}
    if not meta or not meta.get("enabled", True):
        return
    roots = meta["roots"]
    if meta.get("require_for_all"):
        for path in sorted(names):
            if (path.endswith(".meta") or not _in_roots(path, roots) or _excluded(path, config)
                    or _unity_ignored(path) or path + ".meta" in names):
                continue
            issues.append(_finding("meta_missing", path, "Unity asset has no adjacent .meta file"))
    if meta.get("check_orphans"):
        folders = {str(parent) for path in names for parent in PurePosixPath(path).parents if str(parent) != "."}
        for path in sorted(names):
            target = path[:-5]
            if (not path.endswith(".meta") or _excluded(path, config) or _unity_ignored(path)
                    or not (_in_roots(path, roots) or path in {root.rstrip("/") + ".meta" for root in roots})):
                continue
            if target not in names and target not in folders:
                issues.append(_finding("meta_orphan", path, "Unity .meta file has no asset or folder"))


def _filenames(names: set[str], config: dict[str, Any], issues: list[dict[str, str]]) -> None:
    spec = config.get("filenames") or {}
    if not spec or not spec.get("enabled", True):
        return
    if spec.get("case_collisions", True):
        seen: dict[str, str] = {}
        for path in sorted(names):
            other = seen.setdefault(path.lower(), path)
            if other != path:
                issues.append(_finding("filename_collision", path, f"Path differs only by case from {other}", target=other))
    allowed = CANONICAL_BASENAMES | set(spec.get("allow", []))
    extensions = set(spec["extensions"])
    suffixes = list(HOST_SUFFIXES) + [(item["path"].rstrip("/"), item["suffix"]) for item in spec.get("suffixes", [])]
    for path in sorted(names):
        if not _in_roots(path, spec["roots"]) or _excluded(path, config):
            continue
        name = PurePosixPath(path).name
        parent = str(PurePosixPath(path).parent)
        if name in allowed or name.startswith(".") or SCOPED_PROFILE.match(path):
            continue
        suffix = next((s for folder, s in suffixes if parent == folder and name.endswith(s)), None)
        if suffix is not None:
            if not FILENAME_STEM.match(name[:-len(suffix)]):
                issues.append(_finding("filename_style", path, f"Identifier before {suffix} is not lowercase kebab-case"))
            continue
        extension = PurePosixPath(name).suffix
        if extension.lower() not in extensions:
            continue
        if extension != extension.lower():
            issues.append(_finding("filename_extension_case", path, "Filename extension is not lowercase"))
        elif not FILENAME_STEM.match(PurePosixPath(name).stem):
            issues.append(_finding("filename_style", path, "Filename is not lowercase kebab-case"))


def _finding(code: str, path: str, message: str, **details: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message, **details}


def _text(data: bytes, path: str, issues: list[dict[str, str]]) -> str | None:
    if data.partition(b"\n")[0].removesuffix(b"\r") == LFS:
        issues.append(_finding("lfs_pointer", path, "Git LFS pointer cannot be checked as asset data"))
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        issues.append(_finding("invalid_text", path, "File is not UTF-8 text"))
        return None


def _mask_csharp(source: str) -> str:
    """Mask comments and strings while preserving whitespace and identifier positions."""
    result = list(source)
    index = 0
    while index < len(source):
        start = index
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = len(source) if end < 0 else end
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
        elif source.startswith('"""', index):
            width = 0
            while index + width < len(source) and source[index + width] == '"':
                width += 1
            end = source.find('"' * width, index + width)
            index = len(source) if end < 0 else end + width
        elif source[index] in {'"', "'"} or (source[index] == "@" and index + 1 < len(source) and source[index+1] == '"'):
            verbatim = source[index] == "@"
            quote = '"' if verbatim else source[index]
            index += 2 if verbatim else 1
            while index < len(source):
                if verbatim and source.startswith('""', index):
                    index += 2
                elif source[index] == quote:
                    index += 1
                    break
                elif not verbatim and source[index] == "\\":
                    index += 2
                else:
                    index += 1
        else:
            index += 1
            continue
        for offset in range(start, min(index, len(source))):
            if result[offset] not in "\r\n":
                result[offset] = " "
    return "".join(result)


def _namespace_names(masked: str) -> set[str]:
    names: set[str] = set()
    scopes: list[str | None] = []
    file_namespace = ""
    for token in NAMESPACE_TOKENS.finditer(masked):
        declared, delimiter = token.group(1), token.group(2)
        if declared:
            parent = next((name for name in reversed(scopes) if name is not None), file_namespace)
            full = f"{parent}.{declared}" if parent else declared
            names.add(full)
            if delimiter == "{":
                scopes.append(full)
            else:
                file_namespace = full
        elif token.group() == "{":
            scopes.append(None)
        elif scopes:
            scopes.pop()
    return names


def _rule_for(path: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    matched = [r for r in rules if _under(path, r["path"])]
    return max(matched, key=lambda r: len(r["path"])) if matched else None


def _namespaces(files: dict[str, bytes], config: dict[str, Any], issues: list[dict[str, str]]) -> None:
    spec = config.get("namespaces", {})
    if not spec or not spec.get("enabled", True):
        return
    for path, data in files.items():
        if not path.endswith(".cs"):
            continue
        rule = _rule_for(path, spec["rules"])
        if rule is None:
            continue
        exception = _rule_for(path, rule.get("exceptions", []))
        expected = (exception or {}).get("namespace", rule["namespace"])
        required = rule.get("require_declaration", False) and not (exception or {}).get("allow_missing", False)
        source = _text(data, path, issues)
        if source is None:
            continue
        names = _namespace_names(_mask_csharp(source))
        if not names and required:
            issues.append(_finding("namespace_missing", path, "Namespace declaration required", expected=expected))
        for name in sorted(names):
            if name != expected and not name.startswith(expected + "."):
                issues.append(_finding("namespace_mismatch", path, f"Namespace {name} is outside {expected}", actual=name, expected=expected))


def _guids(files: dict[str, bytes], issues: list[dict[str, str]], roots: list[str]) -> dict[str, str]:
    identities: dict[str, str] = {}
    owners: dict[str, str] = {}
    for path, data in sorted(files.items()):
        if not path.endswith(".meta") or not any(_under(path, root) for root in roots):
            continue
        source = _text(data, path, issues)
        if source is None:
            continue
        match = GUID.search(source)
        if not match:
            issues.append(_finding("guid_missing", path, "Unity .meta file has no valid GUID"))
            continue
        value = match.group(1).lower()
        identities[path] = value
        if value in owners:
            issues.append(_finding("guid_duplicate", path, f"GUID also belongs to {owners[value]}", guid=value))
        else:
            owners[value] = path
    return identities


def _assemblies(files: dict[str, bytes], config: dict[str, Any], issues: list[dict[str, str]], identities: dict[str, str]) -> None:
    spec = config.get("assemblies", {})
    if not spec or not spec.get("enabled", True):
        return
    records: dict[str, dict[str, Any]] = {}
    by_name: dict[str, str] = {}
    by_guid: dict[str, str] = {}
    for path, data in sorted(files.items()):
        if not path.endswith(".asmdef") or not any(_under(path, root) for root in spec["roots"]):
            continue
        source = _text(data, path, issues)
        if source is None:
            continue
        try:
            item = json.loads(source)
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
                raise ValueError("missing assembly name")
            if not isinstance(item.get("references", []), list):
                raise ValueError("references must be a list")
            for field in ("includePlatforms", "excludePlatforms"):
                if not isinstance(item.get(field, []), list) or any(not isinstance(value, str) for value in item.get(field, [])):
                    raise ValueError(f"{field} must be a list of strings")
        except (ValueError, json.JSONDecodeError) as error:
            issues.append(_finding("asmdef_invalid", path, f"Invalid assembly definition: {error}"))
            continue
        name = item["name"]
        if name in by_name:
            issues.append(_finding("assembly_duplicate", path, f"Assembly name also belongs to {by_name[name]}", assembly=name))
        else:
            by_name[name] = path
        guid = identities.get(path + ".meta")
        if guid:
            by_guid[guid] = path
        rule = _rule_for(path, spec["path_rules"])
        if rule is None:
            issues.append(_finding("assembly_unclassified", path, "Assembly has no layer path rule"))
        platforms = set(item.get("includePlatforms", []))
        exclusions = set(item.get("excludePlatforms", []))
        layer = rule["layer"] if rule else None
        if spec.get("enforce_platforms", True) and layer == "Editor" and platforms != {"Editor"}:
            issues.append(_finding("assembly_platform", path, "Editor assembly must include only the Editor platform"))
        records[path] = {"name": name, "layer": layer, "references": item.get("references", []),
                         "platforms": platforms, "exclusions": exclusions}
    graph: dict[str, set[str]] = defaultdict(set)
    allowed = {(edge["from"], edge["to"]) for edge in spec.get("allowed_edges", [])}
    for path, record in records.items():
        for reference in record["references"]:
            if not isinstance(reference, str):
                issues.append(_finding("assembly_reference_invalid", path, "Assembly reference must be a string"))
                continue
            if reference.startswith("GUID:"):
                value = reference[5:].lower()
                target = by_guid.get(value)
                if target is None:
                    issues.append(_finding("assembly_reference_unresolved", path, f"Unresolved assembly GUID {value}", reference=reference))
                    continue
            else:
                target = by_name.get(reference)
                if target is None:
                    # Unity can resolve package and precompiled references outside configured roots.
                    continue
            graph[path].add(target)
            source_layer, target_layer = record["layer"], records[target]["layer"]
            if source_layer and target_layer and target_layer not in BOUNDARY[source_layer] and (record["name"], records[target]["name"]) not in allowed:
                issues.append(_finding("assembly_boundary", path, f"{source_layer} assembly {record['name']} references {target_layer} assembly {records[target]['name']}", target=target))
            if spec.get("enforce_platforms", True) and source_layer and target_layer:
                source_platforms, target_platforms = record["platforms"], records[target]["platforms"]
                source_exclusions, target_exclusions = record["exclusions"], records[target]["exclusions"]
                incompatible = ((target_platforms and (not source_platforms or not source_platforms <= target_platforms))
                                or bool(source_platforms & target_exclusions)
                                or (not source_platforms and bool(target_exclusions - source_exclusions)))
                if incompatible:
                    issues.append(_finding("assembly_platform", path, f"Assembly {record['name']} can compile on a platform unavailable to {records[target]['name']}", target=target))
    visited: set[str] = set()
    stack: set[str] = set()
    def visit(node: str) -> None:
        visited.add(node)
        stack.add(node)
        for target in sorted(graph[node]):
            if target in stack:
                issues.append(_finding("assembly_cycle", node, f"Assembly dependency cycle through {target}", target=target))
            elif target not in visited:
                visit(target)
        stack.remove(node)
    for node in sorted(records):
        if node not in visited:
            visit(node)


def _checks(files: dict[str, bytes], config: dict[str, Any], seed: list[dict[str, str]],
            names: set[str] | None = None) -> list[dict[str, str]]:
    issues = list(seed)
    if names is not None:
        _filenames(names, config, issues)
        _meta_inventory(names, config, issues)
    _namespaces(files, config, issues)
    meta = config.get("unity_meta", {})
    roots = list(set(meta.get("roots", []) + config.get("assemblies", {}).get("roots", [])))
    identities = _guids(files, issues, roots) if roots else {}
    _assemblies(files, config, issues, identities)
    if meta and meta.get("enabled", True):
        extensions = set(meta.get("require_for_extensions", []))
        inventory = names if names is not None else files
        for path in files:
            if meta.get("require_for_all") and names is not None:
                break
            if any(_under(path, root) for root in meta["roots"]) and PurePosixPath(path).suffix in extensions and path + ".meta" not in inventory:
                issues.append(_finding("meta_missing", path, "Unity asset has no adjacent .meta file"))
    return issues


def _moves(root: Path, base: str, head: str, current: dict[str, bytes], base_files: dict[str, bytes],
           config: dict[str, Any], issues: list[dict[str, str]], include_worktree: bool) -> None:
    meta = config.get("unity_meta", {})
    if not meta or not meta.get("enabled", True) or not meta.get("check_move_identity", True):
        return
    for path in sorted(base_files.keys() & current.keys()):
        if not path.endswith(".meta") or not any(_under(path, r) for r in meta["roots"]):
            continue
        old_guid = GUID.search(base_files[path].decode("utf-8", "replace"))
        new_guid = GUID.search(current[path].decode("utf-8", "replace"))
        if old_guid and new_guid and old_guid.group(1).lower() != new_guid.group(1).lower():
            issues.append(_finding("guid_changed", path, f"Unity identity changed from {old_guid.group(1)} to {new_guid.group(1)}"))
    raw = _git(root, "diff", "--find-renames", "--name-status", "-z", base, head)
    chunks = raw.split(b"\x00")
    index = 0
    while index < len(chunks) and chunks[index]:
        status = chunks[index].decode("ascii", "replace")
        if status.startswith("R") and index + 2 < len(chunks):
            old = chunks[index+1].decode("utf-8", "surrogateescape")
            new = chunks[index+2].decode("utf-8", "surrogateescape")
            index += 3
            if not _safe(old) or not _safe(new) or not any(_under(new, r) for r in meta["roots"]):
                continue
            old_meta, new_meta = base_files.get(old + ".meta"), current.get(new + ".meta")
            if old_meta is None or new_meta is None:
                continue
            old_guid, new_guid = GUID.search(old_meta.decode("utf-8", "replace")), GUID.search(new_meta.decode("utf-8", "replace"))
            if old_guid and new_guid and old_guid.group(1).lower() != new_guid.group(1).lower():
                issues.append(_finding("move_guid_changed", new, f"Moved asset changed GUID from {old_guid.group(1)} to {new_guid.group(1)}", previous_path=old))
        else:
            index += 2
    if include_worktree:
        # Git's rename detector compares tracked content with HEAD; untracked moves
        # cannot be attributed reliably and are intentionally not called preserved.
        tracked = _git(root, "diff", "--find-renames", "--name-status", "-z", head)
        chunks = tracked.split(b"\x00")
        index = 0
        head_files, _ = _snapshot_tree(root, head, config)
        while index < len(chunks) and chunks[index]:
            status = chunks[index].decode("ascii", "replace")
            if status.startswith("R") and index + 2 < len(chunks):
                old = chunks[index+1].decode("utf-8", "surrogateescape")
                new = chunks[index+2].decode("utf-8", "surrogateescape")
                index += 3
                if not _safe(old) or not _safe(new):
                    continue
                a, b = head_files.get(old + ".meta"), current.get(new + ".meta")
                if a and b:
                    am, bm = GUID.search(a.decode("utf-8", "replace")), GUID.search(b.decode("utf-8", "replace"))
                    if am and bm and am.group(1).lower() != bm.group(1).lower():
                        issues.append(_finding("move_guid_changed", new, f"Moved asset changed GUID from {am.group(1)} to {bm.group(1)}", previous_path=old))
            else:
                index += 2


def check_organization(project: Path | None = None, *, base_ref: str | None = None,
                       head_ref: str = "HEAD", include_worktree: bool = False,
                       config_path: Path | None = None, require_config: bool = False) -> dict[str, Any]:
    """Check configured rules; incremental mode fails only for new findings.

    A requested Git ref that cannot resolve is an error. No files are modified.
    """
    root = project_root(project)
    if base_ref is None and head_ref != "HEAD":
        raise RuntimeError("head_ref requires base_ref")
    base = _git(root, "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}").decode().strip() if base_ref is not None else None
    head = _git(root, "rev-parse", "--verify", "--end-of-options", f"{head_ref}^{{commit}}").decode().strip() if base_ref is not None else None
    path = config_path or root / ".embraion" / "organization.yaml"
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if not path.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Organization configuration path escapes project root")
    config = _read_config(root, path)
    if config is None:
        if require_config:
            return {"status": "failed", "passed": False, "reason": "No .embraion/organization.yaml",
                    "findings": [], "counts": {"new": 0, "preexisting": 0}}
        return {"status": "skipped", "passed": True, "reason": "No .embraion/organization.yaml", "findings": [], "counts": {"new": 0, "preexisting": 0}}
    if base_ref is None:
        files, seed = _snapshot_worktree(root, config)
        names = _names_worktree(root) if _needs_names(config) else None
        findings = [{**item, "status": "new"} for item in _checks(files, config, seed, names)]
        return {"status": "failed" if findings else "passed", "passed": not findings,
                "mode": "full", "base_commit": None, "head_commit": None,
                "findings": findings, "counts": {"new": len(findings), "preexisting": 0}}
    assert base is not None and head is not None
    base_files, base_seed = _snapshot_tree(root, base, config)
    current, seed = _snapshot_worktree(root, config) if include_worktree else _snapshot_tree(root, head, config)
    wants_names = _needs_names(config)
    base_names = _names_tree(root, base) if wants_names else None
    current_names = None
    if wants_names:
        current_names = _names_worktree(root) if include_worktree else _names_tree(root, head)
    before = _checks(base_files, config, base_seed, base_names)
    after = _checks(current, config, seed, current_names)
    _moves(root, base, head, current, base_files, config, after, include_worktree)
    def key(item: dict[str, str]) -> tuple[str, str, str, str]:
        return (item["code"], item["path"], item.get("actual", ""), item.get("target", ""))
    baseline = {key(item) for item in before}
    findings = [{**item, "status": "preexisting" if key(item) in baseline else "new"} for item in after]
    new_count = sum(item["status"] == "new" for item in findings)
    return {"status": "failed" if new_count else "passed", "passed": new_count == 0,
            "mode": "incremental", "base_commit": base, "head_commit": head,
            "include_worktree": include_worktree, "findings": findings,
            "counts": {"new": new_count, "preexisting": len(findings) - new_count}}
