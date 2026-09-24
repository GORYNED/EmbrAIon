from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .common import iter_text_files, read_json, read_yaml

README_TIMESTAMP = re.compile(
    r"<sub>(?:Last updated|Последнее обновление|最后更新|अंतिम अपडेट|Última actualización)[^<]*UTC</sub>\s*$",
    re.IGNORECASE,
)

MODEL_AGNOSTIC_FORBIDDEN_GLOBS = (
    "core/**/models.yaml",
    "core/**/models.yml",
    "core/**/models.json",
    "adapters/**/models.yaml",
    "adapters/**/models.yml",
    "adapters/**/models.json",
    "adapters/**/model-catalog.yaml",
    "adapters/**/model-catalog.yml",
    "adapters/**/model-catalog.json",
    "schemas/model.schema.json",
)


def _contains_model_selector(value: Any) -> bool:
    if isinstance(value, dict):
        if "model" in value:
            return True
        return any(_contains_model_selector(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_model_selector(item) for item in value)
    return False


def find_model_agnostic_violations(root: Path) -> list[Path]:
    matches: set[Path] = set()
    for pattern in MODEL_AGNOSTIC_FORBIDDEN_GLOBS:
        matches.update(path for path in root.glob(pattern) if path.is_file())

    for suffix in ("yaml", "yml", "json"):
        for path in root.glob(f"adapters/**/routes.{suffix}"):
            if not path.is_file():
                continue
            try:
                data = read_json(path) if suffix == "json" else read_yaml(path)
            except Exception:
                continue
            if _contains_model_selector(data):
                matches.add(path)

    return sorted(matches)


def _schema_errors(instance: Any, schema_path: Path) -> list[str]:
    validator = Draft202012Validator(read_json(schema_path))
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(value) for value in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


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

    for path in find_model_agnostic_violations(root):
        add(
            "model-agnostic-invariant",
            str(path.relative_to(root)),
            (
                "EmbrAIon must not own model catalogs or adapter route-to-model "
                "maps; keep model availability with the execution host and "
                "project choices under routing.overrides"
            ),
        )

    for path in iter_text_files(root):
        relative = path.relative_to(root)
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                # Tool-owned configuration can use valid custom YAML tags that
                # are intentionally outside EmbrAIon's SafeLoader contract.
                # MkDocs validates mkdocs.yml through the strict docs build.
                if relative.as_posix() != "mkdocs.yml":
                    read_yaml(path)
            elif path.suffix.lower() == ".json":
                read_json(path)
        except Exception as error:
            add("parse", str(relative), str(error))

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

    project_schema = root / "schemas/project.schema.json"
    framework_data = read_yaml(root / "framework.yaml") or {}
    current_framework_version = str(framework_data.get("version", ""))

    project_manifests = [
        root / "templates/project-overlay/.embraion/project.yaml",
        *sorted((root / "examples").glob("*/.embraion/project.yaml")),
    ]
    for manifest in project_manifests:
        if not manifest.exists():
            continue

        try:
            project_data = read_yaml(manifest) or {}
            if project_schema.exists():
                for message in _schema_errors(project_data, project_schema):
                    add(
                        "project-schema",
                        str(manifest.relative_to(root)),
                        message,
                    )

            framework = project_data.get("framework") or {}
            declared_repository = str(framework.get("repository", ""))
            declared_version = str(framework.get("version", ""))

            if declared_repository != "GORYNED/EmbrAIon":
                add(
                    "project-repository",
                    str(manifest.relative_to(root)),
                    "framework.repository must be GORYNED/EmbrAIon",
                )

            if declared_version != current_framework_version:
                add(
                    "project-version",
                    str(manifest.relative_to(root)),
                    (
                        f"framework.version must match current EmbrAIon "
                        f"version {current_framework_version}; got {declared_version}"
                    ),
                )

            project_root = manifest.parent.parent
            for knowledge_id, value in (project_data.get("knowledge") or {}).items():
                relative = value.get("path") if isinstance(value, dict) else value
                if not relative:
                    add(
                        "project-knowledge",
                        str(manifest.relative_to(root)),
                        f"knowledge '{knowledge_id}' has no path",
                    )
                    continue

                target = (project_root / str(relative)).resolve()
                try:
                    target.relative_to(project_root.resolve())
                except ValueError:
                    add(
                        "project-knowledge",
                        str(manifest.relative_to(root)),
                        f"knowledge '{knowledge_id}' escapes the project root",
                    )
                    continue

                if not target.is_file():
                    add(
                        "project-knowledge",
                        str(manifest.relative_to(root)),
                        f"knowledge '{knowledge_id}' does not resolve to {relative}",
                    )
        except Exception as error:
            add(
                "project-schema",
                str(manifest.relative_to(root)),
                str(error),
            )

    agent_schema = root / "schemas/agent.schema.json"
    if agent_schema.exists():
        for path in sorted((root / "core/agents").glob("*.yaml")):
            for message in _schema_errors(read_yaml(path), agent_schema):
                add("agent-schema", str(path.relative_to(root)), message)

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

    docs = {path.name for path in (root / "docs").glob("*.md")}
    site_only_docs = {"index.md"}
    localized_index_docs = {"README.md"}
    canonical_docs = docs - site_only_docs

    for locale in ("ru", "zh-CN", "hi", "es"):
        local = root / "localization" / "docs" / locale
        names = {path.name for path in local.glob("*.md")} if local.exists() else set()
        localized_docs = names - localized_index_docs

        for name in sorted(canonical_docs - localized_docs):
            add("localization", f"localization/docs/{locale}", f"Missing {name}")

        for name in sorted(localized_docs - canonical_docs):
            add(
                "localization",
                f"localization/docs/{locale}",
                f"Extra localized document {name}",
                "warning",
            )

    required_localized_readmes = {
        "ru": root / "localization" / "README.ru.md",
        "zh-CN": root / "localization" / "README.zh-CN.md",
        "hi": root / "localization" / "README.hi.md",
        "es": root / "localization" / "README.es.md",
    }
    for locale, path in required_localized_readmes.items():
        if not path.exists():
            add("localization", f"localization/{locale}", "Missing localized root README")

    for locale in ("ru", "zh-CN", "hi", "es"):
        legal = root / "localization" / "legal" / locale / "trademarks.md"
        if not legal.exists():
            add("localization", f"localization/legal/{locale}", "Missing trademark localization")

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
