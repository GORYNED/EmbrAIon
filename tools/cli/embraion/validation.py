from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator

from .common import iter_text_files, read_json, read_yaml

README_TIMESTAMP = re.compile(
    r"<sub>(?:Last updated|Последнее обновление|最后更新)[^<]*UTC</sub>\s*$",
    re.IGNORECASE,
)


def _schema_errors(instance: Any, schema_path: Path) -> list[str]:
    validator = Draft202012Validator(read_json(schema_path))
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(value) for value in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def _model_refs(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "model" and isinstance(child, str):
                yield child
            yield from _model_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _model_refs(child)


def collect_issues(root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, path: str, message: str, severity: str = "error") -> None:
        issues.append(
            {
                "severity": severity,
                "code": code,
                "path": path,
                "message": message,
            }
        )

    for path in iter_text_files(root):
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                read_yaml(path)
            elif path.suffix.lower() == ".json":
                read_json(path)
        except Exception as error:
            add("parse", str(path.relative_to(root)), str(error))

    schema_pairs = [
        (root / "framework.yaml", root / "schemas/framework.schema.json"),
        (root / "core/catalog.yaml", root / "schemas/catalog.schema.json"),
    ]
    for instance_path, schema_path in schema_pairs:
        if not instance_path.exists() or not schema_path.exists():
            continue
        try:
            for message in _schema_errors(read_yaml(instance_path), schema_path):
                add("schema", str(instance_path.relative_to(root)), message)
        except Exception as error:
            add("schema", str(instance_path.relative_to(root)), str(error))

    agent_schema = root / "schemas/agent.schema.json"
    if agent_schema.exists():
        for path in sorted((root / "core/agents").glob("*.yaml")):
            for message in _schema_errors(read_yaml(path), agent_schema):
                add("agent-schema", str(path.relative_to(root)), message)

    model_schema = root / "schemas/model.schema.json"
    if model_schema.exists():
        for path in sorted((root / "adapters").glob("**/models.yaml")):
            for message in _schema_errors(read_yaml(path), model_schema):
                add("model-schema", str(path.relative_to(root)), message)

    eval_schema = root / "schemas/eval.schema.json"
    if eval_schema.exists():
        for path in sorted((root / "evals/cases").glob("*.yaml")):
            for message in _schema_errors(read_yaml(path), eval_schema):
                add("eval-schema", str(path.relative_to(root)), message)

    catalog = read_yaml(root / "core/catalog.yaml") or {}
    seen: set[str] = set()
    for item in catalog.get("capabilities", []):
        capability_id = item.get("id")
        if capability_id in seen:
            add("duplicate-capability", "core/catalog.yaml", f"Duplicate capability id: {capability_id}")
        seen.add(capability_id)

        relative = item.get("path")
        if not relative:
            continue

        target = root / "core" / relative
        if item.get("type") == "skill":
            if not target.is_dir() or not (target / "SKILL.md").is_file():
                add(
                    "catalog-path",
                    "core/catalog.yaml",
                    f"Skill '{capability_id}' does not resolve to {relative}/SKILL.md",
                )
        elif not target.exists():
            add(
                "catalog-path",
                "core/catalog.yaml",
                f"Capability '{capability_id}' does not resolve to {relative}",
            )

    skills_root = root / "core/skills"
    if skills_root.exists():
        for directory in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            entry = directory / "SKILL.md"
            if not entry.exists():
                add("skill-entry", str(directory.relative_to(root)), "Missing SKILL.md")
                continue

            text = entry.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if not match:
                add("skill-frontmatter", str(entry.relative_to(root)), "Missing YAML frontmatter")
                continue

            try:
                metadata = yaml.safe_load(match.group(1)) or {}
                if metadata.get("name") != directory.name:
                    add("skill-name", str(entry.relative_to(root)), f"name must be '{directory.name}'")
                if not metadata.get("description"):
                    add("skill-description", str(entry.relative_to(root)), "description is required")
            except Exception as error:
                add("skill-frontmatter", str(entry.relative_to(root)), str(error))

    for route_path in sorted((root / "adapters").glob("*/routes.yaml")):
        model_path = route_path.parent / "models.yaml"
        if not model_path.exists():
            continue

        models = read_yaml(model_path) or {}
        known = {
            str(item.get("id"))
            for group in ("models", "options")
            for item in models.get(group, []) or []
            if item.get("id")
        }
        routes = read_yaml(route_path) or {}
        for model in _model_refs(routes):
            if model not in known:
                add("route-model", str(route_path.relative_to(root)), f"Unknown model id: {model}")

    docs = {path.name for path in (root / "docs").glob("*.md")}
    for locale in ("ru", "zh-CN"):
        local = root / "localization" / "docs" / locale
        names = {path.name for path in local.glob("*.md")} if local.exists() else set()

        for name in sorted(docs - names):
            add("localization", f"localization/docs/{locale}", f"Missing {name}")

        for name in sorted(names - docs):
            add(
                "localization",
                f"localization/docs/{locale}",
                f"Extra localized document {name}",
                "warning",
            )

    for path in root.rglob("README*.md"):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if not README_TIMESTAMP.search(text):
            add(
                "readme-timestamp",
                str(path.relative_to(root)),
                "README must end with a UTC last-updated timestamp",
            )

    forbidden = {
        "COMPANY" + "_SECRET": "Use CONFIDENTIAL data class",
        "adapters/agent" + "-plugin": "Use adapters/portable",
        "AI" + "-first": "Use AI-First",
    }
    for path in iter_text_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token, message in forbidden.items():
            if token in text:
                add(
                    "forbidden-token",
                    str(path.relative_to(root)),
                    f"{message}; legacy token is still present",
                )

    return issues
