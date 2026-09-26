from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import __version__
from .contracts import default_project_contract_slots
from .common import (
    framework_root,
    framework_version,
    project_root,
    read_json,
    read_yaml,
    state_root,
    write_json,
    write_yaml,
)
from .policy import read_agents_config
from .versioning import ensure_cached_runtime


HOST_SKILL_DIRECTORIES = {
    "codex": Path(".agents") / "skills",
    "copilot": Path(".github") / "skills",
    "claude-code": Path(".claude") / "skills",
}

HOST_COMPONENTS = {
    "codex": ("config", "agents", "skills"),
    "copilot": ("agents", "skills"),
    "claude-code": ("agents", "skills"),
    "portable": ("bundle",),
}

HOST_ACCESS_PROJECTIONS = {
    "codex": {
        "read-only": {"sandbox_mode": "read-only"},
        "workspace-write": {"sandbox_mode": "workspace-write"},
    },
    "copilot": {
        "read-only": {"tools": ("read", "search")},
        "workspace-write": {"tools": ("read", "search", "edit", "execute")},
    },
    "claude-code": {
        "read-only": {"tools": ("Read", "Grep", "Glob")},
        "workspace-write": {
            "tools": ("Read", "Grep", "Glob", "Write", "Edit", "Bash"),
        },
    },
}

_LOCAL_STATE_GITIGNORE = """# Local EmbrAIon runtime state
state/
cache/
"""

CODEX_CONFIG_MODES = {"replace", "merge"}
CODEX_CONFIG_MANAGED_BEGIN = "# >>> EmbrAIon managed: agents"
CODEX_CONFIG_MANAGED_END = "# <<< EmbrAIon managed: agents"
CODEX_CONFIG_MANAGED_KEYS = {
    "enabled": "enabled = true",
    "max_concurrent_threads_per_session": "max_concurrent_threads_per_session = 3",
}
_TOML_TABLE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")
_CODEX_MANAGED_ASSIGNMENT = re.compile(
    r"^\s*(enabled|max_concurrent_threads_per_session)\s*="
)


def _normalize_components(
    host: str,
    components: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    supported = HOST_COMPONENTS.get(host)
    if supported is None:
        raise RuntimeError(f"Unsupported host: {host}")

    if not components:
        return supported

    requested = tuple(dict.fromkeys(str(item) for item in components))
    invalid = [item for item in requested if item not in supported]
    if invalid:
        raise RuntimeError(
            f"Host '{host}' does not support projection component(s): "
            + ", ".join(invalid)
            + f". Supported: {', '.join(supported)}."
        )
    return requested


def _component_for_path(host: str, relative: str) -> str | None:
    normalized = relative.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]

    if host == "codex":
        if normalized == ".codex/config.toml":
            return "config"
        if normalized.startswith(".codex/agents/"):
            return "agents"
        if normalized.startswith(".agents/skills/"):
            return "skills"
    elif host == "copilot":
        if normalized.startswith(".github/agents/"):
            return "agents"
        if normalized.startswith(".github/skills/"):
            return "skills"
    elif host == "claude-code":
        if normalized.startswith(".claude/agents/"):
            return "agents"
        if normalized.startswith(".claude/skills/"):
            return "skills"
    elif host == "portable" and normalized.startswith("embraion/"):
        return "bundle"

    return None


def _validate_codex_config_mode(
    host: str,
    components: tuple[str, ...],
    mode: str,
) -> str:
    if mode not in CODEX_CONFIG_MODES:
        raise RuntimeError(
            f"Unsupported Codex config mode '{mode}'. "
            f"Expected one of: {', '.join(sorted(CODEX_CONFIG_MODES))}."
        )
    if mode == "merge" and (host != "codex" or "config" not in components):
        raise RuntimeError(
            "--config-mode merge is only valid for the Codex config component."
        )
    return mode


def _codex_managed_block() -> list[str]:
    return [
        CODEX_CONFIG_MANAGED_BEGIN,
        CODEX_CONFIG_MANAGED_KEYS["enabled"],
        CODEX_CONFIG_MANAGED_KEYS["max_concurrent_threads_per_session"],
        CODEX_CONFIG_MANAGED_END,
    ]


def _merge_codex_config_text(existing: str) -> str:
    try:
        parsed_existing = tomllib.loads(existing) if existing.strip() else {}
    except tomllib.TOMLDecodeError as error:
        raise RuntimeError(
            f"Cannot safely merge .codex/config.toml: invalid TOML: {error}"
        ) from error

    lines = existing.splitlines()
    begin_indexes = [
        index for index, line in enumerate(lines)
        if line.strip() == CODEX_CONFIG_MANAGED_BEGIN
    ]
    end_indexes = [
        index for index, line in enumerate(lines)
        if line.strip() == CODEX_CONFIG_MANAGED_END
    ]
    if len(begin_indexes) > 1 or len(end_indexes) > 1:
        raise RuntimeError(
            "Cannot safely merge .codex/config.toml: duplicate EmbrAIon managed markers."
        )
    if bool(begin_indexes) != bool(end_indexes):
        raise RuntimeError(
            "Cannot safely merge .codex/config.toml: incomplete EmbrAIon managed markers."
        )

    managed = _codex_managed_block()
    if begin_indexes:
        begin = begin_indexes[0]
        end = end_indexes[0]
        if end < begin:
            raise RuntimeError(
                "Cannot safely merge .codex/config.toml: managed markers are out of order."
            )
        lines = lines[:begin] + managed + lines[end + 1 :]
    else:
        agents_header = None
        agents_end = len(lines)
        for index, line in enumerate(lines):
            match = _TOML_TABLE.match(line)
            if not match:
                continue
            table_name = match.group(1).strip()
            if table_name == "agents":
                agents_header = index
                continue
            if agents_header is not None and index > agents_header:
                agents_end = index
                break

        if agents_header is None:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(["[agents]", *managed])
        else:
            body = lines[agents_header + 1 : agents_end]
            body = [
                line
                for line in body
                if not _CODEX_MANAGED_ASSIGNMENT.match(line)
            ]
            lines = (
                lines[: agents_header + 1]
                + managed
                + body
                + lines[agents_end:]
            )

    merged = "\n".join(lines).rstrip() + "\n"
    try:
        parsed = tomllib.loads(merged)
    except tomllib.TOMLDecodeError as error:
        raise RuntimeError(
            f"Cannot safely merge .codex/config.toml: merged TOML is invalid: {error}"
        ) from error

    agents = parsed.get("agents") or {}
    if (
        agents.get("enabled") is not True
        or agents.get("max_concurrent_threads_per_session") != 3
    ):
        raise RuntimeError(
            "Cannot safely merge .codex/config.toml: EmbrAIon managed agents "
            "settings are not effective after merge."
        )

    # Ensure we never silently erase existing non-managed tables or values.
    for key, value in parsed_existing.items():
        if key == "agents":
            continue
        if parsed.get(key) != value:
            raise RuntimeError(
                f"Cannot safely merge .codex/config.toml: non-managed table '{key}' changed."
            )

    return merged


def projection_is_verified(plan: dict[str, Any]) -> bool:
    return not any(
        plan.get(key)
        for key in (
            "create",
            "update",
            "conflict",
            "obsolete-owned",
            "obsolete-modified",
        )
    )


def _default_project_overlay(name: str) -> dict[str, Any]:
    return {
        "framework": {
            "repository": "GORYNED/EmbrAIon",
            "version": __version__,
        },
        "project": {"name": name},
        "capabilities": {},
    }


def _default_routing_config() -> dict[str, Any]:
    return {"overrides": {}}


def _default_knowledge_config() -> dict[str, Any]:
    return {"slots": default_project_contract_slots()}


def _default_validation_config() -> dict[str, Any]:
    return {
        "profiles": {
            "fast": [],
            "affected": [],
            "full": [],
        }
    }


def _default_agents_config() -> dict[str, Any]:
    return {"agents": []}


def _default_policy_config() -> dict[str, Any]:
    return {
        "sources": {
            "canonical": [],
            "protected": [],
            "generated": [],
            "external": [],
        },
        "review": {"substantial-required": True},
        "privacy": {"default-class": "PRIVATE"},
        "enforcement": {
            "enabled": False,
            "validation-profile": "affected",
            "require-review": False,
        },
    }


def init_project(path: Path, name: str | None = None, force: bool = False) -> Path:
    destination = path.resolve()
    manifest = destination / ".embraion" / "project.yaml"
    routing = destination / ".embraion" / "routing.yaml"
    policy = destination / ".embraion" / "policy.yaml"
    knowledge = destination / ".embraion" / "knowledge.yaml"
    validation = destination / ".embraion" / "validation.yaml"
    agents = destination / ".embraion" / "agents.yaml"

    if manifest.exists() and not force:
        raise RuntimeError(f"{manifest} already exists; use --force to replace it.")

    if routing.exists() and not force:
        raise RuntimeError(f"{routing} already exists; use --force to replace it.")

    if policy.exists() and not force:
        raise RuntimeError(f"{policy} already exists; use --force to replace it.")

    if knowledge.exists() and not force:
        raise RuntimeError(f"{knowledge} already exists; use --force to replace it.")

    if validation.exists() and not force:
        raise RuntimeError(f"{validation} already exists; use --force to replace it.")

    if agents.exists() and not force:
        raise RuntimeError(f"{agents} already exists; use --force to replace it.")

    write_yaml(manifest, _default_project_overlay(name or destination.name))
    write_yaml(routing, _default_routing_config())
    write_yaml(policy, _default_policy_config())
    write_yaml(knowledge, _default_knowledge_config())
    write_yaml(validation, _default_validation_config())
    write_yaml(agents, _default_agents_config())

    local_ignore = destination / ".embraion" / ".gitignore"
    if not local_ignore.exists():
        local_ignore.write_text(_LOCAL_STATE_GITIGNORE, encoding="utf-8")

    return manifest


def _merge_missing_defaults(
    current: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(current)
    for key, default in defaults.items():
        if key not in merged:
            merged[key] = default
            continue

        existing = merged[key]
        if isinstance(existing, dict) and isinstance(default, dict):
            merged[key] = _merge_missing_defaults(existing, default)

    return merged


def _config_upgrade_inputs(
    destination: Path,
    *,
    version: str,
) -> dict[Path, tuple[dict[str, Any], Path]]:
    config_root = destination / ".embraion"
    manifest = config_root / "project.yaml"
    raw_manifest = read_yaml(manifest)
    if raw_manifest is None:
        raw_manifest = {}
    if not isinstance(raw_manifest, dict):
        raise RuntimeError(f"Invalid project configuration mapping: {manifest}")

    project_name = str(
        (raw_manifest.get("project") or {}).get("name")
        or destination.name
    )
    project_defaults = _default_project_overlay(project_name)
    project_defaults["framework"]["version"] = version

    definitions = {
        manifest: (project_defaults, Path("schemas/project.schema.json")),
        config_root / "routing.yaml": (
            _default_routing_config(),
            Path("schemas/routing.schema.json"),
        ),
        config_root / "policy.yaml": (
            _default_policy_config(),
            Path("schemas/policy.schema.json"),
        ),
        config_root / "knowledge.yaml": (
            _default_knowledge_config(),
            Path("schemas/knowledge.schema.json"),
        ),
        config_root / "validation.yaml": (
            _default_validation_config(),
            Path("schemas/validation.schema.json"),
        ),
        config_root / "agents.yaml": (
            _default_agents_config(),
            Path("schemas/agents.schema.json"),
        ),
    }

    missing = [path for path in definitions if not path.is_file()]
    if missing:
        relative = ", ".join(
            path.relative_to(destination).as_posix()
            for path in missing
        )
        raise RuntimeError(
            "Project configuration uses an incomplete or legacy layout. "
            "Automatic update only normalizes the modular .embraion layout; "
            f"missing: {relative}."
        )

    return definitions


def _validate_upgrade_candidate(
    path: Path,
    data: dict[str, Any],
    schema_path: Path,
) -> None:
    schema = read_json(framework_root() / schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda item: list(item.absolute_path),
    )
    if not errors:
        return

    formatted: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")

    raise RuntimeError(
        f"Cannot safely update {path}: current values are incompatible with "
        "the target configuration contract; " + "; ".join(formatted)
    )


def normalize_project_config(
    path: Path,
    *,
    version: str,
) -> list[Path]:
    destination = path.resolve()
    manifest = destination / ".embraion" / "project.yaml"
    if not manifest.is_file():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")

    definitions = _config_upgrade_inputs(destination, version=version)
    candidates: dict[Path, dict[str, Any]] = {}
    originals: dict[Path, dict[str, Any]] = {}

    for config_path, (defaults, schema_path) in definitions.items():
        loaded = read_yaml(config_path)
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            raise RuntimeError(
                f"Invalid project configuration mapping: {config_path}"
            )

        originals[config_path] = loaded
        candidate = _merge_missing_defaults(loaded, defaults)

        if config_path == manifest:
            framework = dict(candidate.get("framework") or {})
            framework["repository"] = "GORYNED/EmbrAIon"
            framework["version"] = version
            candidate["framework"] = framework

        _validate_upgrade_candidate(config_path, candidate, schema_path)
        candidates[config_path] = candidate

    changed = [
        config_path
        for config_path, candidate in candidates.items()
        if candidate != originals[config_path]
    ]

    for config_path in changed:
        write_yaml(config_path, candidates[config_path])

    return changed


def update_project(path: Path, version: str | None = None) -> tuple[str | None, str]:
    destination = path.resolve()
    manifest = destination / ".embraion" / "project.yaml"

    if not manifest.exists():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")

    data = read_yaml(manifest)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid project configuration mapping: {manifest}")

    previous = (data.get("framework") or {}).get("version")
    current = str(version or __version__).strip()
    if current != __version__:
        raise RuntimeError(
            "Safe project configuration update currently targets the installed "
            f"EmbrAIon launcher version ({__version__}) only. Install the desired "
            "launcher version first, then run 'embraion update'."
        )

    recovery = _capture_prior_projection_evidence(
        destination,
        source_version=str(previous or "").strip(),
        target_version=current,
    )
    normalize_project_config(destination, version=current)
    _persist_projection_recovery_evidence(destination, recovery)
    return previous, current


PROJECT_AGENT_ACCESS = {"read-only", "workspace-write"}
NON_LEAD_DELEGATION_RESTRICTION = "do not recursively delegate"


def _core_agents(root: Path) -> list[dict[str, Any]]:
    return [read_yaml(path) for path in sorted((root / "core/agents").glob("*.yaml"))]


def _merge_agent_items(*values: Any) -> list[str]:
    merged: list[str] = []
    for value in values:
        for item in value or []:
            text = str(item)
            if text not in merged:
                merged.append(text)
    return merged


def _validate_project_agents_schema(
    root: Path,
    config: dict[str, Any],
) -> None:
    schema = read_json(root / "schemas" / "agents.schema.json")
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(config),
        key=lambda item: list(item.absolute_path),
    )
    if not errors:
        return

    formatted = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")
    raise RuntimeError(
        "Invalid .embraion/agents.yaml: " + "; ".join(formatted)
    )


def _project_agents(
    root: Path,
    project: Path,
    core_agents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    config = read_agents_config(project)
    _validate_project_agents_schema(root, config)

    core_by_id = {str(agent["id"]): agent for agent in core_agents}
    project_agents: list[dict[str, Any]] = []
    seen: set[str] = set()

    for definition in config.get("agents") or []:
        agent_id = str(definition["id"])
        if agent_id in core_by_id:
            raise RuntimeError(
                f"Project agent '{agent_id}' conflicts with a Core agent id."
            )
        if agent_id in seen:
            raise RuntimeError(f"Duplicate project agent id: {agent_id}")
        seen.add(agent_id)

        base_id = definition.get("extends")
        base: dict[str, Any] = {}
        if base_id:
            if base_id == "lead":
                raise RuntimeError(
                    f"Project agent '{agent_id}' cannot extend the Core Lead role."
                )
            if base_id not in core_by_id:
                raise RuntimeError(
                    f"Project agent '{agent_id}' extends unknown Core agent "
                    f"'{base_id}'."
                )
            base = core_by_id[base_id]

        access = str(definition["access"])
        if access not in PROJECT_AGENT_ACCESS:
            raise RuntimeError(
                f"Project agent '{agent_id}' has unsupported access '{access}'."
            )
        if base and access != base.get("access"):
            raise RuntimeError(
                f"Project agent '{agent_id}' must preserve access "
                f"'{base.get('access')}' inherited from Core agent '{base_id}'."
            )

        project_agents.append(
            {
                "schema-version": 1,
                "id": agent_id,
                "title": definition.get("title")
                or agent_id.replace("-", " ").title(),
                "purpose": definition["purpose"],
                "access": access,
                "model-neutral": True,
                "responsibilities": _merge_agent_items(
                    base.get("responsibilities"),
                    definition.get("responsibilities"),
                ),
                "restrictions": _merge_agent_items(
                    base.get("restrictions"),
                    [NON_LEAD_DELEGATION_RESTRICTION],
                    definition.get("restrictions"),
                ),
                "triggers": _merge_agent_items(
                    base.get("triggers"),
                    definition.get("triggers"),
                ),
                "outputs": _merge_agent_items(
                    base.get("outputs"),
                    definition.get("outputs"),
                ),
                "extends": base_id,
            }
        )

    return project_agents


def load_agents(
    root: Path,
    project: Path | None = None,
) -> list[dict[str, Any]]:
    core_agents = _core_agents(root)
    if project is None:
        return core_agents
    return core_agents + _project_agents(root, project, core_agents)


def _agent_instructions(agent: dict[str, Any]) -> str:
    lines = [agent.get("purpose", "")]

    if agent.get("responsibilities"):
        lines.append("Responsibilities:")
        lines.extend(f"- {value}" for value in agent["responsibilities"])

    if agent.get("restrictions"):
        lines.append("Restrictions:")
        lines.extend(f"- {value}" for value in agent["restrictions"])

    return "\n".join(lines).strip()


def _generate_codex(
    root: Path,
    output: Path,
    components: tuple[str, ...],
    project: Path | None = None,
) -> None:
    target = output / ".codex"

    if "config" in components:
        target.mkdir(parents=True, exist_ok=True)
        config = [
            "[agents]",
            "enabled = true",
            "max_concurrent_threads_per_session = 3",
            "",
        ]
        (target / "config.toml").write_text("\n".join(config), encoding="utf-8")

    if "agents" not in components:
        return

    agents_target = target / "agents"
    agents_target.mkdir(parents=True, exist_ok=True)

    for agent in load_agents(root, project):
        if agent.get("id") == "lead":
            continue

        access_projection = _host_access_projection("codex", agent)
        instructions = _agent_instructions(agent).replace('"""', '\\"\\"\\"')

        content = (
            f'name = "{agent["id"]}"\n'
            f'description = {__import__("json").dumps(agent.get("purpose", ""), ensure_ascii=False)}\n'
            f'sandbox_mode = "{access_projection["sandbox_mode"]}"\n'
            f'developer_instructions = """\n{instructions}\n"""\n'
        )
        (agents_target / f"{agent['id']}.toml").write_text(content, encoding="utf-8")


def _host_access_projection(
    host: str,
    agent: dict[str, Any],
) -> dict[str, Any]:
    host_mappings = HOST_ACCESS_PROJECTIONS.get(host)
    if host_mappings is None:
        raise RuntimeError(
            f"Host '{host}' has no enforceable agent access projection."
        )

    access = str(agent.get("access") or "")
    projection = host_mappings.get(access)
    if projection is None:
        raise RuntimeError(
            f"Agent '{agent.get('id', '<unknown>')}' has unsupported access "
            f"mapping '{access}' for host '{host}'."
        )
    return dict(projection)


def _generate_markdown_agents(
    root: Path,
    output: Path,
    host: str,
    project: Path | None = None,
) -> None:
    if host == "copilot":
        target = output / ".github" / "agents"
        suffix = ".agent.md"
    else:
        target = output / ".claude" / "agents"
        suffix = ".md"

    target.mkdir(parents=True, exist_ok=True)

    for agent in load_agents(root, project):
        if agent.get("id") == "lead":
            continue

        lines = [
            "---",
            f"name: {__import__('json').dumps(str(agent['title']), ensure_ascii=False)}",
            f"description: {__import__('json').dumps(agent.get('purpose', ''), ensure_ascii=False)}",
        ]
        access_projection = _host_access_projection(host, agent)
        tools = access_projection.get("tools")
        if tools:
            lines.append("tools:")
            lines.extend(f"  - {tool}" for tool in tools)
        if host == "copilot":
            lines.append("include-custom-instructions: true")
        lines.extend(
            [
                "---",
                "",
                f"# {agent['title']}",
                "",
                _agent_instructions(agent),
                "",
            ]
        )
        (target / f"{agent['id']}{suffix}").write_text("\n".join(lines), encoding="utf-8")


def _generate_host_skills(root: Path, output: Path, host: str) -> None:
    relative = HOST_SKILL_DIRECTORIES.get(host)
    if relative is None:
        return

    target = output / relative
    target.mkdir(parents=True, exist_ok=True)

    for directory in sorted((root / "core" / "skills").iterdir()):
        if not directory.is_dir() or not (directory / "SKILL.md").is_file():
            continue
        shutil.copytree(directory, target / directory.name, dirs_exist_ok=True)


def _generate_portable(root: Path, output: Path) -> None:
    target = output / "embraion"
    target.mkdir(parents=True, exist_ok=True)

    write_json(
        target / "plugin.json",
        {
            "schemaVersion": 1,
            "name": "EmbrAIon",
            "version": framework_version(root),
            "description": "Portable AI-First Engineering System capability bundle",
        },
    )

    shutil.copy2(root / "core/catalog.yaml", target / "catalog.yaml")
    shutil.copytree(root / "core/skills", target / "skills", dirs_exist_ok=True)
    shutil.copytree(root / "core/knowledge", target / "knowledge", dirs_exist_ok=True)
    shutil.copytree(root / "core/routing", target / "routing", dirs_exist_ok=True)


def generate_host(
    root: Path,
    host: str,
    output: Path,
    components: list[str] | tuple[str, ...] | None = None,
    *,
    project: Path | None = None,
) -> None:
    selected = _normalize_components(host, components)

    if host == "codex":
        _generate_codex(root, output, selected, project)
        if "skills" in selected:
            _generate_host_skills(root, output, host)
    elif host == "copilot":
        if "agents" in selected:
            _generate_markdown_agents(root, output, "copilot", project)
        if "skills" in selected:
            _generate_host_skills(root, output, host)
    elif host == "claude-code":
        if "agents" in selected:
            _generate_markdown_agents(root, output, "claude-code", project)
        if "skills" in selected:
            _generate_host_skills(root, output, host)
    elif host == "portable":
        if "bundle" in selected:
            _generate_portable(root, output)
    else:
        raise RuntimeError(f"Unsupported host: {host}")


def sync(host: str, output: Path, force: bool = False) -> list[Path]:
    root = framework_root()
    hosts = ["codex", "copilot", "claude-code", "portable"] if host == "all" else [host]

    if output.exists() and force:
        shutil.rmtree(output)

    output.mkdir(parents=True, exist_ok=True)
    generated = []

    for current in hosts:
        host_output = output / current
        if host_output.exists():
            shutil.rmtree(host_output)
        host_output.mkdir(parents=True, exist_ok=True)
        generate_host(root, current, host_output)
        generated.append(host_output)

    return generated


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _projection_state_path(project: Path, host: str) -> Path:
    return state_root(project) / "projections" / f"{host}.json"


def _projection_recovery_path(project: Path, host: str) -> Path:
    return state_root(project) / "projections" / f"{host}.recovery.json"


def _host_has_projection_candidates(host: str, destination: Path) -> bool:
    hints = {
        "codex": (
            destination / ".codex",
            destination / ".agents" / "skills",
        ),
        "copilot": (
            destination / ".github" / "agents",
            destination / ".github" / "skills",
        ),
        "claude-code": (
            destination / ".claude" / "agents",
            destination / ".claude" / "skills",
        ),
        "portable": (destination / "embraion",),
    }
    return any(path.exists() for path in hints.get(host, ()))


def _generate_host_with_cached_runtime(
    runtime_python: Path,
    runtime_root: Path,
    host: str,
    output: Path,
    project: Path,
) -> None:
    code = (
        "import sys; "
        "from pathlib import Path; "
        "from embraion.common import framework_root; "
        "from embraion.project import generate_host; "
        "generate_host("
        "framework_root(), sys.argv[1], Path(sys.argv[2]), "
        "project=Path(sys.argv[3]))"
    )
    environment = os.environ.copy()
    environment["EMBRAION_HOME"] = str(runtime_root)
    environment["EMBRAION_DISABLE_VERSION_RESOLUTION"] = "1"
    subprocess.run(
        [
            str(runtime_python),
            "-c",
            code,
            host,
            str(output),
            str(project),
        ],
        cwd=str(project),
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _capture_prior_projection_evidence(
    project: Path,
    *,
    source_version: str,
    target_version: str,
) -> dict[str, dict[str, Any]]:
    if not source_version or source_version == target_version:
        return {}

    candidates = [
        host
        for host in HOST_COMPONENTS
        if _load_projection_state(project, host, project) is None
        and _host_has_projection_candidates(host, project)
    ]
    if not candidates:
        return {}

    try:
        runtime = ensure_cached_runtime(source_version)
    except Exception:
        return {}

    evidence: dict[str, dict[str, Any]] = {}
    for host in candidates:
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"embraion-recovery-{host}-"
            ) as temporary:
                generated = Path(temporary)
                _generate_host_with_cached_runtime(
                    runtime.python,
                    runtime.framework_root,
                    host,
                    generated,
                    project,
                )
                generated_files = _file_hashes(generated)
                matched = {
                    relative: digest
                    for relative, digest in generated_files.items()
                    if (target := project / relative).is_file()
                    and _sha256(target) == digest
                }
        except Exception:
            continue

        if not matched:
            continue

        evidence[host] = {
            "schema-version": 1,
            "source-framework-version": source_version,
            "target-framework-version": target_version,
            "host": host,
            "destination": str(project.resolve()),
            "managed-components": sorted(
                {
                    component
                    for relative in matched
                    if (component := _component_for_path(host, relative))
                }
            ),
            "files": matched,
        }

    return evidence


def _persist_projection_recovery_evidence(
    project: Path,
    evidence: dict[str, dict[str, Any]],
) -> None:
    for host, record in evidence.items():
        write_json(_projection_recovery_path(project, host), record)


def _load_projection_recovery(
    project: Path,
    host: str,
    destination: Path,
) -> dict[str, Any] | None:
    path = _projection_recovery_path(project, host)
    if not path.is_file():
        return None

    data = read_json(path) or {}
    if data.get("destination") != str(destination.resolve()):
        return None

    manifest = read_yaml(project / ".embraion" / "project.yaml") or {}
    current_pin = str((manifest.get("framework") or {}).get("version", ""))
    if data.get("target-framework-version") != current_pin:
        return None
    return data


def _load_projection_state(
    project: Path,
    host: str,
    destination: Path,
) -> dict[str, Any] | None:
    path = _projection_state_path(project, host)
    if not path.is_file():
        return None

    data = read_json(path) or {}
    if data.get("destination") != str(destination.resolve()):
        return None
    return data


def _projection_plan_from_generated(
    host: str,
    generated: Path,
    destination: Path,
    components: tuple[str, ...],
    *,
    config_mode: str = "replace",
) -> dict[str, Any]:
    project = project_root(destination)
    previous = _load_projection_state(project, host, destination)
    recovery = (
        None
        if previous is not None
        else _load_projection_recovery(project, host, destination)
    )
    previous_files = (previous or recovery or {}).get("files") or {}
    generated_files = _file_hashes(generated)

    plan: dict[str, Any] = {
        "schema-version": 1,
        "host": host,
        "destination": str(destination.resolve()),
        "components": list(components),
        "config-mode": (
            config_mode
            if host == "codex" and "config" in components
            else None
        ),
        "create": [],
        "update": [],
        "unchanged": [],
        "conflict": [],
        "obsolete-owned": [],
        "obsolete-modified": [],
        "ownership-recovery": (
            {
                "source-framework-version": recovery.get(
                    "source-framework-version"
                ),
                "files": sorted((recovery.get("files") or {}).keys()),
            }
            if recovery
            else None
        ),
    }

    for relative, generated_hash in generated_files.items():
        target = destination / relative

        if (
            host == "codex"
            and relative == ".codex/config.toml"
            and config_mode == "merge"
        ):
            if not target.exists():
                plan["create"].append(relative)
                continue
            try:
                current_text = target.read_text(encoding="utf-8")
                merged_text = _merge_codex_config_text(current_text)
            except (OSError, UnicodeError, RuntimeError):
                plan["conflict"].append(relative)
                continue
            if current_text == merged_text:
                plan["unchanged"].append(relative)
            else:
                plan["update"].append(relative)
            continue

        if not target.exists():
            plan["create"].append(relative)
            continue

        current_hash = _sha256(target)
        if current_hash == generated_hash:
            plan["unchanged"].append(relative)
            continue

        previous_hash = previous_files.get(relative)
        if previous_hash and previous_hash == current_hash:
            plan["update"].append(relative)
        else:
            plan["conflict"].append(relative)

    selected = set(components)
    for relative, previous_hash in previous_files.items():
        if relative in generated_files:
            continue
        if _component_for_path(host, relative) not in selected:
            continue

        target = destination / relative
        if not target.exists():
            continue

        if _sha256(target) == previous_hash:
            plan["obsolete-owned"].append(relative)
        else:
            plan["obsolete-modified"].append(relative)

    for key in (
        "create",
        "update",
        "unchanged",
        "conflict",
        "obsolete-owned",
        "obsolete-modified",
    ):
        plan[key] = sorted(plan[key])

    return plan


def projection_plan(
    host: str,
    destination: Path,
    *,
    components: list[str] | tuple[str, ...] | None = None,
    config_mode: str = "replace",
) -> dict[str, Any]:
    root = framework_root()
    destination = destination.resolve()
    selected = _normalize_components(host, components)
    config_mode = _validate_codex_config_mode(host, selected, config_mode)

    with tempfile.TemporaryDirectory(prefix="embraion-projection-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated, selected, project=project_root(destination))
        return _projection_plan_from_generated(
            host,
            generated,
            destination,
            selected,
            config_mode=config_mode,
        )


def install(
    host: str,
    destination: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    prune: bool = False,
    components: list[str] | tuple[str, ...] | None = None,
    config_mode: str = "replace",
) -> dict[str, Any]:
    root = framework_root()
    destination = destination.resolve()
    project = project_root(destination)
    selected = _normalize_components(host, components)
    config_mode = _validate_codex_config_mode(host, selected, config_mode)

    with tempfile.TemporaryDirectory(prefix="embraion-install-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated, selected, project=project)
        plan = _projection_plan_from_generated(
            host,
            generated,
            destination,
            selected,
            config_mode=config_mode,
        )

        if dry_run:
            return plan

        conflicts = list(plan["conflict"])
        if (
            config_mode == "merge"
            and ".codex/config.toml" in conflicts
        ):
            raise RuntimeError(
                "Cannot safely merge .codex/config.toml. Fix the TOML/managed "
                "markers, or use --config-mode replace --force only when full "
                "replacement is explicitly intended."
            )
        if conflicts and not force:
            joined = ", ".join(conflicts[:5])
            suffix = "" if len(conflicts) <= 5 else f" (+{len(conflicts) - 5} more)"
            raise RuntimeError(
                f"Projection conflicts with user-modified or unowned files: "
                f"{joined}{suffix}. Review with 'embraion projection diff' "
                f"and use --force only when replacement is intentional."
            )

        destination.mkdir(parents=True, exist_ok=True)

        writable = list(plan["create"]) + list(plan["update"])
        if force:
            writable += conflicts

        for relative in writable:
            source = generated / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if (
                host == "codex"
                and relative == ".codex/config.toml"
                and config_mode == "merge"
            ):
                existing = (
                    target.read_text(encoding="utf-8")
                    if target.is_file()
                    else ""
                )
                target.write_text(
                    _merge_codex_config_text(existing),
                    encoding="utf-8",
                )
            else:
                shutil.copy2(source, target)

        previous = _load_projection_state(project, host, destination)
        recovery = (
            None
            if previous is not None
            else _load_projection_recovery(project, host, destination)
        )
        previous_files = (previous or recovery or {}).get("files") or {}

        if prune:
            for relative in plan["obsolete-owned"]:
                target = destination / relative
                if target.is_file():
                    target.unlink()

        selected_components = set(selected)
        current_files = {
            relative: digest
            for relative, digest in previous_files.items()
            if _component_for_path(host, relative) not in selected_components
        }
        current_files.update(_file_hashes(generated))
        if (
            host == "codex"
            and "config" in selected
            and config_mode == "merge"
        ):
            merged_config = destination / ".codex/config.toml"
            if merged_config.is_file():
                current_files[".codex/config.toml"] = _sha256(merged_config)
        preserved_obsolete = list(plan["obsolete-modified"])
        if not prune:
            preserved_obsolete += list(plan["obsolete-owned"])

        for relative in preserved_obsolete:
            target = destination / relative
            previous_hash = previous_files.get(relative)
            if target.is_file() and previous_hash:
                current_files[relative] = previous_hash

        write_json(
            _projection_state_path(project, host),
            {
                "schema-version": 1,
                "framework-version": framework_version(root),
                "host": host,
                "destination": str(destination),
                "config-mode": (
                    config_mode
                    if host == "codex" and "config" in selected
                    else None
                ),
                "managed-components": sorted(
                    set((previous or recovery or {}).get("managed-components") or [])
                    | {
                        component
                        for relative in previous_files
                        if (component := _component_for_path(host, relative))
                    }
                    | set(selected)
                ),
                "files": current_files,
            },
        )
        recovery_path = _projection_recovery_path(project, host)
        if recovery_path.is_file():
            recovery_path.unlink()
        return plan
