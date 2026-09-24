from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import __version__
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

_LOCAL_STATE_GITIGNORE = """# Local EmbrAIon runtime state
state/
cache/
"""


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
    return {}


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


def update_project(path: Path, version: str | None = None) -> tuple[str | None, str]:
    destination = path.resolve()
    manifest = destination / ".embraion" / "project.yaml"

    if not manifest.exists():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")

    data = read_yaml(manifest) or {}
    data.setdefault("framework", {})

    previous = data["framework"].get("version")
    current = version or __version__

    data["framework"]["repository"] = "GORYNED/EmbrAIon"
    data["framework"]["version"] = current
    write_yaml(manifest, data)

    return previous, current


PROJECT_AGENT_ACCESS = {"read-only", "workspace-write"}


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

        sandbox = "workspace-write" if agent.get("access") == "workspace-write" else "read-only"
        instructions = _agent_instructions(agent).replace('"""', '\\"\\"\\"')

        content = (
            f'name = "{agent["id"]}"\n'
            f'description = {__import__("json").dumps(agent.get("purpose", ""), ensure_ascii=False)}\n'
            f'sandbox_mode = "{sandbox}"\n'
            f'developer_instructions = """\n{instructions}\n"""\n'
        )
        (agents_target / f"{agent['id']}.toml").write_text(content, encoding="utf-8")


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
            f"name: {agent['title']}",
            f"description: {__import__('json').dumps(agent.get('purpose', ''), ensure_ascii=False)}",
            "---",
            "",
            f"# {agent['title']}",
            "",
            _agent_instructions(agent),
            "",
        ]
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
) -> dict[str, Any]:
    project = project_root(destination)
    previous = _load_projection_state(project, host, destination)
    previous_files = (previous or {}).get("files") or {}
    generated_files = _file_hashes(generated)

    plan: dict[str, Any] = {
        "schema-version": 1,
        "host": host,
        "destination": str(destination.resolve()),
        "components": list(components),
        "create": [],
        "update": [],
        "unchanged": [],
        "conflict": [],
        "obsolete-owned": [],
        "obsolete-modified": [],
    }

    for relative, generated_hash in generated_files.items():
        target = destination / relative
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
) -> dict[str, Any]:
    root = framework_root()
    destination = destination.resolve()
    selected = _normalize_components(host, components)

    with tempfile.TemporaryDirectory(prefix="embraion-projection-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated, selected, project=project_root(destination))
        return _projection_plan_from_generated(
            host,
            generated,
            destination,
            selected,
        )


def install(
    host: str,
    destination: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    prune: bool = False,
    components: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    root = framework_root()
    destination = destination.resolve()
    project = project_root(destination)
    selected = _normalize_components(host, components)

    with tempfile.TemporaryDirectory(prefix="embraion-install-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated, selected, project=project)
        plan = _projection_plan_from_generated(
            host,
            generated,
            destination,
            selected,
        )

        if dry_run:
            return plan

        conflicts = list(plan["conflict"])
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
            shutil.copy2(source, target)

        previous = _load_projection_state(project, host, destination)
        previous_files = (previous or {}).get("files") or {}

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
                "managed-components": sorted(
                    set((previous or {}).get("managed-components") or [])
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
        return plan
