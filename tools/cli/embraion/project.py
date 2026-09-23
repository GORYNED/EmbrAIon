from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .common import framework_root, framework_version, read_yaml, write_json, write_yaml


def init_project(path: Path, name: str | None = None, force: bool = False) -> Path:
    destination = path.resolve()
    manifest = destination / ".embraion" / "project.yaml"

    if manifest.exists() and not force:
        raise RuntimeError(f"{manifest} already exists; use --force to replace it.")

    data = {
        "framework": {
            "repository": "GORYNED/EmbrAIon",
            "version": __version__,
        },
        "project": {"name": name or destination.name},
        "knowledge": {},
        "agents": [],
        "capabilities": {},
    }
    write_yaml(manifest, data)
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
    elif host == "copilot":
        _generate_markdown_agents(root, output, "copilot")
    elif host == "claude-code":
        _generate_markdown_agents(root, output, "claude-code")
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


def _merge_tree(source: Path, destination: Path, force: bool) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = destination / relative

        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        if target.exists() and not force:
            raise RuntimeError(f"Refusing to overwrite {target}; use --force.")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def install(host: str, destination: Path, force: bool = False) -> None:
    root = framework_root()

    with tempfile.TemporaryDirectory(prefix="embraion-install-") as temporary:
        generated = Path(temporary)
        generate_host(root, host, generated)
        _merge_tree(generated, destination.resolve(), force)
