from __future__ import annotations

from fnmatch import fnmatchcase
from glob import escape as escape_pattern
import re
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from .common import framework_root, project_root, read_json, read_yaml
from .environment import child_environment


DEFAULT_POLICY: dict[str, Any] = {
    "sources": {
        "canonical": [],
        "protected": [],
        "generated": [],
        "external": [],
    },
    "validation": {
        "profiles": {
            "fast": [],
            "affected": [],
            "full": [],
        }
    },
    "review": {"substantial-required": True},
    "privacy": {"default-class": "PRIVATE"},
    "enforcement": {
        "enabled": False,
        "validation-profile": "affected",
        "require-review": False,
    },
    "routing": {"overrides": {}},
    "merge": {"mode": "human-only"},
}


def normalize_project_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _validated_config_mapping(
    path: Path,
    *,
    schema_name: str,
    label: str,
) -> dict[str, Any]:
    data = read_yaml(path)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid {label}: expected a mapping.")

    schema = read_json(framework_root() / "schemas" / schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        formatted: list[str] = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            formatted.append(f"{location}: {error.message}")
        raise RuntimeError(f"Invalid {label}: " + "; ".join(formatted))

    return data


def read_project_overlay(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    manifest = root / ".embraion" / "project.yaml"
    if not manifest.is_file():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")
    return _validated_config_mapping(
        manifest,
        schema_name="project.schema.json",
        label=".embraion/project.yaml",
    )


def read_routing_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "routing.yaml"
    if not path.is_file():
        return {"overrides": {}}
    return _validated_config_mapping(
        path,
        schema_name="routing.schema.json",
        label=".embraion/routing.yaml",
    )


def read_deployments_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "deployments.yaml"
    if not path.is_file():
        return {"providers": {}, "deployments": {}}
    return _validated_config_mapping(
        path,
        schema_name="deployments.schema.json",
        label=".embraion/deployments.yaml",
    )


def read_knowledge_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "knowledge.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="knowledge.schema.json",
        label=".embraion/knowledge.yaml",
    )


def read_validation_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "validation.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    config = _validated_config_mapping(
        path,
        schema_name="validation.schema.json",
        label=".embraion/validation.yaml",
    )
    # Optional plan keys (areas, impact, full-reasons, default-area) fail closed on bad references.
    from .validation_plan import validate_plan_config

    validate_plan_config(config)
    return config


def read_agents_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "agents.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="agents.schema.json",
        label=".embraion/agents.yaml",
    )


def read_policy_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "policy.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="policy.schema.json",
        label=".embraion/policy.yaml",
    )


class _UniqueMappingLoader(yaml.SafeLoader):
    """Reject ambiguous committed YAML before a consumer relies on its policy."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(None, None, "policy must be a mapping", node.start_mark)
        seen: set[str] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in seen:
                raise yaml.constructor.ConstructorError(None, None, "duplicate or non-string policy key", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def read_policy_config_at_ref(project: Path, ref: str) -> dict[str, Any]:
    """Return a schema-checked committed policy and its resolved commit identity.

    The working tree and projection ledgers do not affect this result. Missing,
    symlinked, malformed or ambiguous policy entries fail closed.
    """
    if not ref or "\x00" in ref or "\n" in ref or "\r" in ref:
        raise RuntimeError("A nonempty Git commit ref is required.")
    # Git's repository-location variables take precedence over -C. A caller's
    # environment must not change which project's committed policy is returned.
    git_location_variables = {
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE", "GIT_PREFIX",
    }
    environment = child_environment()
    for name in git_location_variables:
        environment.pop(name, None)
    requested = project.resolve()

    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", "-C", str(requested), *args], capture_output=True,
                              env=environment, check=False)

    repository = git("rev-parse", "--show-toplevel")
    if repository.returncode:
        raise RuntimeError("Cannot find the requested project's Git repository.")

    resolved = git("rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if resolved.returncode or not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", resolved.stdout.strip()):
        raise RuntimeError("Cannot resolve policy Git ref to a commit.")
    commit = resolved.stdout.decode("ascii").strip()
    entry = git("ls-tree", "-z", commit, "--", ".embraion/policy.yaml")
    if entry.returncode or not entry.stdout:
        raise RuntimeError("Committed .embraion/policy.yaml is missing or unreadable.")
    record = entry.stdout.rstrip(b"\x00").split(b"\t", 1)
    fields = record[0].split() if len(record) == 2 and record[1] == b".embraion/policy.yaml" else []
    if len(fields) != 3 or fields[0] not in {b"100644", b"100755"} or fields[1] != b"blob":
        raise RuntimeError("Committed .embraion/policy.yaml must be a regular file.")
    size = git("cat-file", "-s", fields[2].decode("ascii"))
    if size.returncode or not size.stdout.strip().isdigit() or int(size.stdout) > 2 * 1024 * 1024:
        raise RuntimeError("Committed .embraion/policy.yaml is unreadable or too large.")
    blob = git("cat-file", "blob", fields[2].decode("ascii"))
    if blob.returncode or len(blob.stdout) != int(size.stdout):
        raise RuntimeError("Committed .embraion/policy.yaml cannot be read.")
    try:
        policy = yaml.load(blob.stdout.decode("utf-8"), Loader=_UniqueMappingLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise RuntimeError("Committed .embraion/policy.yaml is invalid YAML.") from error
    schema = read_json(framework_root() / "schemas" / "policy.schema.json")
    if not isinstance(policy, dict) or not Draft202012Validator(schema).is_valid(policy):
        raise RuntimeError("Committed .embraion/policy.yaml does not satisfy policy schema.")
    return {"commit": commit, "policy": policy}


def effective_policy(project: Path | None = None) -> dict[str, Any]:
    read_project_overlay(project)
    project_policy = read_policy_config(project)
    routing = read_routing_config(project)
    validation = read_validation_config(project)

    sources = DEFAULT_POLICY["sources"] | (project_policy.get("sources") or {})
    # Projection ledgers name the files EmbrAIon generated; explicit entries remain.
    derived = projection_generated_patterns(project)
    explicit = list(sources.get("generated") or [])
    sources["generated"] = explicit + [item for item in derived if item not in explicit]
    default_profiles = DEFAULT_POLICY["validation"]["profiles"]
    profiles = default_profiles | (validation.get("profiles") or {})

    return {
        "sources": sources,
        "validation": {"profiles": profiles},
        "review": DEFAULT_POLICY["review"] | (project_policy.get("review") or {}),
        "privacy": DEFAULT_POLICY["privacy"] | (project_policy.get("privacy") or {}),
        "enforcement": (
            DEFAULT_POLICY["enforcement"]
            | (project_policy.get("enforcement") or {})
        ),
        "routing": DEFAULT_POLICY["routing"] | routing,
        "merge": DEFAULT_POLICY["merge"] | (project_policy.get("merge") or {}),
        "derived-sources": {"generated": derived},
    }


def projection_generated_patterns(project: Path | None = None) -> list[str]:
    """Return escaped path patterns for every output recorded in projection ledgers."""
    from .project import projection_ledger_outputs

    return [escape_pattern(path) for path in projection_ledger_outputs(project_root(project))]


def merge_mode(project: Path | None = None) -> str:
    """Return the project's declared merge mode; a missing policy keeps the Core default."""
    root = project_root(project)
    path = root / ".embraion" / "policy.yaml"
    if not path.is_file():
        return DEFAULT_POLICY["merge"]["mode"]
    # Validate only this key: projection keeps working for older policies that
    # 'embraion update' normalizes later, but an unknown merge mode fails closed.
    data = read_yaml(path)
    configured = data.get("merge") if isinstance(data, dict) else None
    if configured is None:
        return DEFAULT_POLICY["merge"]["mode"]
    schema = read_json(framework_root() / "schemas" / "policy.schema.json")["properties"]["merge"]
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(configured)]
    if errors:
        raise RuntimeError("Invalid .embraion/policy.yaml: merge: " + "; ".join(errors))
    return str(configured["mode"])


DATA_CLASS_ORDER = {"PUBLIC": 0, "PRIVATE": 1, "CONFIDENTIAL": 2}


def source_data_classes(project: Path | None = None) -> dict[str, str] | None:
    """Return the declared data class of each source ID, or None when the project declares none."""
    root = project_root(project)
    if not (root / ".embraion" / "policy.yaml").is_file():
        return None
    declared = (read_policy_config(root).get("privacy") or {}).get("sources")
    return dict(declared) if declared is not None else None


def check_source_classes(data_class: str, source_ids: list[str], project: Path | None = None) -> None:
    """Fail closed when a request names an undeclared source or a class below its sources."""
    declared = source_data_classes(project)
    from .sources import effective_data_classes, registry_data_classes
    root = project_root(project)
    if declared is None:
        # Without privacy.sources only the registry's raised classes apply; other IDs stay unchecked.
        declared = registry_data_classes(root)
        if not declared:
            return
        source_ids = [source for source in source_ids if source in declared]
    else:
        declared = effective_data_classes(root, declared)
    unknown = sorted(set(source_ids) - set(declared))
    if unknown:
        raise RuntimeError(
            "Execution names source IDs without a declared data class: " + ", ".join(unknown) + "."
        )
    above = sorted(source for source in source_ids
                   if DATA_CLASS_ORDER[declared[source]] > DATA_CLASS_ORDER[data_class])
    if above:
        raise RuntimeError(
            f"Execution data class {data_class} is below the declared class of: "
            + ", ".join(f"{source} ({declared[source]})" for source in above) + "."
        )


def path_matches(path: str, patterns: list[str]) -> bool:
    normalized = normalize_project_path(path)
    prepared: list[tuple[str, list[int], list[str]]] = []
    for pattern in patterns:
        canonical = pattern.replace("\\", "/")
        if len(canonical) > 4096:
            raise RuntimeError("Policy path pattern exceeds the supported length.")
        segments = canonical.split("/")
        optional = [index for index, segment in enumerate(segments[:-1]) if segment == "**"]
        if len(optional) > 8:
            raise RuntimeError("Policy path pattern has too many recursive segments.")
        prepared.append((canonical, optional, segments))

    for canonical, optional, segments in prepared:
        # Preserve every match the original fnmatchcase semantics allowed,
        # including '*' crossing a slash.
        if fnmatchcase(normalized, canonical):
            return True
        # Whole-segment '**/' also matches zero directory levels. At most eight
        # such segments produce 255 additional bounded variants.
        for mask in range(1, 1 << len(optional)):
            omitted = {optional[bit] for bit in range(len(optional)) if mask & (1 << bit)}
            variant = "/".join(segment for index, segment in enumerate(segments)
                               if index not in omitted)
            if fnmatchcase(normalized, variant):
                return True
    return False


def classify_path(path: str, project: Path | None = None) -> list[str]:
    policy = effective_policy(project)
    return [
        category
        for category, patterns in policy["sources"].items()
        if path_matches(path, list(patterns or []))
    ]


def codex_root_policy(project: Path | None = None) -> dict[str, Any]:
    """Return Codex root checks; project lists extend, never replace, Core defaults."""
    from .codex_config import DEFAULT_FORBIDDEN_ROOT_KEYS

    root = project_root(project)
    configured: dict[str, Any] = {}
    if (root / ".embraion" / "policy.yaml").is_file():
        configured = (read_policy_config(root).get("projection") or {}).get("codex") or {}
    forbidden = list(DEFAULT_FORBIDDEN_ROOT_KEYS)
    forbidden += [key for key in configured.get("forbidden-root-keys") or [] if key not in forbidden]
    allowed = configured.get("allowed-root-keys")
    return {
        "strict-root": bool(configured.get("strict-root", False)),
        "forbidden-root-keys": forbidden,
        "allowed-root-keys": list(allowed) if allowed is not None else None,
    }
