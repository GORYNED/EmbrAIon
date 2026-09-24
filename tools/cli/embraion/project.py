from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

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


HOST_SKILL_DIRECTORIES = {
    "codex": Path(".agents") / "skills",
    "copilot": Path(".github") / "skills",
    "claude-code": Path(".claude") / "skills",
}


def _default_project_overlay(name: str) -> dict[str, Any]:
    return {
        "framework": {
            "repository": "GORYNED/EmbrAIon",
            "version": __version__,
        },
        "project": {"name": name},
        "knowledge": {},
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
        "agents": [],
        "capabilities": {},
    }


def init_project(path: Path, name: str | None = None, force: bool = False) -> Path:
    destination = path.resolve()
    manifest = destination / ".embraion" / "project.yaml"

    if manifest.exists() and not force:
        raise RuntimeError(f"{manifest} already exists; use --force to replace it.")

    write_yaml(manifest, _default_project_overlay(name or destination.name))
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


def load_agents(root: Path) -> list[dict[str, Any]]:
    return [read_yaml(path) for path in sorted((root / "core/agents").glob("*.yaml"))]


def _agent_instructions(agent: dict[str, Any]) -> str:
    lines = [agent.get("purpose", "")]

    if agent.get("responsibilities"):
        lines.append("Responsibilities:")
        lines.extend(f"- {value}" for value in agent["responsibilities"])

    if agent.get("restrictions"):
        lines.append("Restrictions:")
        lines.extend(f"- {value}" for value in agent["restrictions"])

    return "\n".join(lines).strip()


def _generate_codex(root: Path, output: Path) -> None:
    target = output / ".codex"
    (target / "agents").mkdir(parents=True, exist_ok=True)

    routes = read_yaml(root / "adapters/codex/routes.yaml") or {}
    default = routes.get("defensive-default", routes.get("routes", {}).get("economy", {}))

    config = [
        "[agents]",
        "enabled = true",
        "max_concurrent_threads_per_session = 3",
        f'default_subagent_model = "{default.get("model", "gpt-6-luna")}"',
        f'default_subagent_reasoning_effort = "{default.get("effort", "medium")}"',
        "",
    ]
    (target / "config.toml").write_text("\n".join(config), encoding="utf-8")

    for agent in load_agents(root):
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
        (target / "agents" / f"{agent['id']}.toml").write_text(content, encoding="utf-8")


def _generate_markdown_agents(root: Path, output: Path, host: str) -> None:
    if host == "copilot":
        target = output / ".github" / "agents"
        suffix = ".agent.md"
    else:
        target = output / ".claude" / "agents"
        suffix = ".md"

    target.mkdir(parents=True, exist_ok=True)

    for agent in load_agents(root):
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


def generate_host(root: Path, host: str, output: Path) -> None:
    if host == "codex":
        _generate_codex(root, output)
        _generate_host_skills(root, output, host)
    elif host == "copilot":
        _generate_markdown_agents(root, output, "copilot")
        _generate_host_skills(root, output, host)
    elif host == "claude-code":
        _generate_markdown_agents(root, output, "claude-code")
        _generate_host_skills(root, output, host)
    elif host == "portable":
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
) -> dict[str, Any]:
    project = project_root(destination)
    previous = _load_projection_state(project, host, destination)
    previous_files = (previous or {}).get("files") or {}
    generated_files = _file_hashes(generated)

    plan: dict[str, Any] = {
        "schema-version": 1,
        "host": host,
        "destination": str(destination.resolve()),
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

    for relative, previous_hash in previous_files.items():
        if relative in generated_files:
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


def projection_plan(host: str, destination: Path) -> dict[str, Any]:
    root = framework_root()
    destination = destination.resolve()

    with tempfile.TemporaryDirectory(prefix="embraion-projection-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated)
        return _projection_plan_from_generated(host, generated, destination)


def install(
    host: str,
    destination: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    prune: bool = False,
) -> dict[str, Any]:
    root = framework_root()
    destination = destination.resolve()
    project = project_root(destination)

    with tempfile.TemporaryDirectory(prefix="embraion-install-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated)
        plan = _projection_plan_from_generated(host, generated, destination)

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

        current_files = _file_hashes(generated)
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
                "files": current_files,
            },
        )
        return plan
