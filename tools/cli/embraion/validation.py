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


MODEL_AGNOSTIC_SEMANTIC_SCOPES = {
    "core",
    "docs",
    "localization",
    "adapters",
}

LEGACY_MODEL_TIER_ROUTE_TOKENS = (
    "economy-read",
    "economy-write",
    "strong-high",
)


def find_model_agnostic_semantic_violations(
    root: Path,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    for path in iter_text_files(root):
        relative = path.relative_to(root)
        in_scope = (
            relative.as_posix() in {"README.md", "AGENTS.md"}
            or (
                bool(relative.parts)
                and relative.parts[0] in MODEL_AGNOSTIC_SEMANTIC_SCOPES
            )
        )
        if not in_scope or path.suffix.lower() not in {".md", ".yaml", ".yml"}:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            reason: str | None = None

            if any(token in lowered for token in LEGACY_MODEL_TIER_ROUTE_TOKENS):
                reason = "legacy model-tier route class is not allowed"
            elif "routing.overrides" in lowered:
                reason = (
                    "obsolete nested routing path; project model overrides belong "
                    "in .embraion/routing.yaml under overrides"
                )
            elif "model/effort route" in lowered:
                reason = (
                    "EmbrAIon roles and Core routes must not own concrete "
                    "model/effort selection"
                )
            elif re.search(
                r"\blead\b.{0,120}\b(?:selects?|chooses?)\b.{0,80}\bmodel\b",
                line,
                re.IGNORECASE,
            ):
                reason = (
                    "Lead classifies task routing and resolves the host; "
                    "it does not select a concrete model"
                )
            elif (
                ".embraion/project.yaml" in lowered
                and ".embraion/routing.yaml" not in lowered
                and ".embraion/deployments.yaml" not in lowered
                and re.search(
                    r"\b(model|routing|override|selector|effort)\b",
                    lowered,
                    re.IGNORECASE,
                )
            ):
                reason = (
                    "model-routing choices belong in .embraion/routing.yaml or "
                    "project deployments in .embraion/deployments.yaml, not "
                    ".embraion/project.yaml"
                )

            if reason:
                violations.append(
                    {
                        "path": path,
                        "line": line_number,
                        "reason": reason,
                    }
                )

    return violations


def _schema_errors(instance: Any, schema_path: Path) -> list[str]:
    validator = Draft202012Validator(read_json(schema_path))
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(value) for value in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def _unity_extension_issues(root: Path, version: str) -> list[tuple[str, str, str]]:
    """Check the optional framework-owned Unity bundle without following links."""
    extension = root / "extensions/unity"
    manifest_path = extension / "manifest.yaml"
    skills_root = extension / "skills"
    if not extension.exists() and not extension.is_symlink():
        return []

    issues: list[tuple[str, str, str]] = []

    def report(code: str, path: Path, message: str) -> None:
        issues.append((code, path.relative_to(root).as_posix(), message))

    if extension.is_symlink() or skills_root.is_symlink() or manifest_path.is_symlink():
        report("unity-manifest", manifest_path, "Unity extension paths must not be symbolic links")
        return issues
    if not manifest_path.is_file():
        report("unity-manifest", manifest_path, "Missing Unity extension manifest")
        return issues
    try:
        manifest = read_yaml(manifest_path)
    except Exception:
        report("unity-manifest", manifest_path, "Invalid Unity extension manifest YAML")
        return issues
    if not isinstance(manifest, dict) or set(manifest) != {"schema-version", "id", "version", "license", "skills"}:
        report("unity-manifest", manifest_path, "Unity manifest must contain only schema-version, id, version, license, and skills")
        return issues
    if type(manifest["schema-version"]) is not int or manifest["schema-version"] != 1 or manifest["id"] != "unity" or manifest["license"] != "MIT":
        report("unity-manifest", manifest_path, "Unity manifest identity, schema version, or license is invalid")
    if manifest["version"] != version:
        report("unity-manifest", manifest_path, f"Unity manifest version must match framework version {version}")
    skills = manifest["skills"]
    if not isinstance(skills, dict) or not skills:
        report("unity-manifest", manifest_path, "Unity manifest skills must be a nonempty mapping")
        return issues
    if not skills_root.is_dir():
        report("unity-manifest", skills_root, "Missing Unity skills directory")
        return issues

    core_names = {path.name for path in (root / "core/skills").glob("*") if path.is_dir()}
    skill_name = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    for identifier, relative in skills.items():
        if not isinstance(identifier, str) or not skill_name.fullmatch(identifier):
            report("unity-manifest", manifest_path, "Unity skill ID is invalid")
            continue
        if identifier in core_names:
            report("unity-skill-collision", manifest_path, f"Unity skill '{identifier}' collides with Core")
        if relative != f"skills/{identifier}":
            report("unity-manifest", manifest_path, f"Unity skill '{identifier}' must map to skills/{identifier}")
            continue
        directory = skills_root / identifier
        entry = directory / "SKILL.md"
        if directory.is_symlink() or entry.is_symlink() or not entry.is_file():
            report("unity-skill-entry", entry, f"Unity skill '{identifier}' has no safe SKILL.md")
            continue
        if any(member.is_symlink() for member in directory.rglob("*")):
            report("unity-skill-entry", directory, f"Unity skill '{identifier}' contains a symbolic link")
        try:
            text = entry.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            metadata = yaml.safe_load(match.group(1)) if match else None
        except (UnicodeError, yaml.YAMLError):
            metadata = None
        if not isinstance(metadata, dict) or metadata.get("name") != identifier or not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
            report("unity-skill-frontmatter", entry, f"Unity skill '{identifier}' needs matching name and description in YAML frontmatter")

    for directory in skills_root.iterdir():
        if directory.is_symlink() or (directory.is_dir() and directory.name not in skills):
            report("unity-skill-entry", directory, "Unity skill directory is unlisted or symbolic")
    return issues


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
                "EmbrAIon Core must not own model catalogs or adapter route-to-model "
                "maps; keep reusable model/deployment choices in the consuming "
                "project's .embraion configuration"
            ),
        )

    for item in find_model_agnostic_semantic_violations(root):
        path = item["path"]
        add(
            "model-agnostic-semantics",
            str(path.relative_to(root)),
            f"line {item['line']}: {item['reason']}",
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
        (root / "adapters/harness-capabilities.yaml", root / "schemas/harness.schema.json"),
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
    routing_schema = root / "schemas/routing.schema.json"
    deployments_schema = root / "schemas/deployments.schema.json"
    optional_project_schemas = {
        "execution.yaml": root / "schemas/execution-config.schema.json",
        "pricing.yaml": root / "schemas/pricing-config.schema.json",
        "pricing.snapshot.json": root / "schemas/pricing-snapshot.schema.json",
        "external-capabilities.yaml": root / "schemas/external-capabilities.schema.json",
        "organization.yaml": root / "schemas/organization.schema.json",
        "knowledge-maintenance.yaml": root / "schemas/knowledge-audit.schema.json",
    }
    policy_schema = root / "schemas/policy.schema.json"
    knowledge_schema = root / "schemas/knowledge.schema.json"
    validation_config_schema = root / "schemas/validation.schema.json"
    project_agents_schema = root / "schemas/agents.schema.json"
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

            routing_manifest = manifest.parent / "routing.yaml"
            if not routing_manifest.is_file():
                add(
                    "routing-schema",
                    str(routing_manifest.relative_to(root)),
                    "Missing routing.yaml",
                )
            elif routing_schema.exists():
                for message in _schema_errors(
                    read_yaml(routing_manifest) or {},
                    routing_schema,
                ):
                    add(
                        "routing-schema",
                        str(routing_manifest.relative_to(root)),
                        message,
                    )

            deployments_manifest = manifest.parent / "deployments.yaml"
            if not deployments_manifest.is_file():
                add(
                    "deployments-schema",
                    str(deployments_manifest.relative_to(root)),
                    "Missing deployments.yaml",
                )
            elif deployments_schema.exists():
                for message in _schema_errors(
                    read_yaml(deployments_manifest) or {},
                    deployments_schema,
                ):
                    add(
                        "deployments-schema",
                        str(deployments_manifest.relative_to(root)),
                        message,
                    )

            for optional_name, optional_schema in optional_project_schemas.items():
                optional_manifest = manifest.parent / optional_name
                if optional_manifest.is_symlink():
                    add("project-schema", str(optional_manifest.relative_to(root)), "Optional configuration must not be a symbolic link")
                    continue
                if optional_manifest.is_file():
                    if not optional_schema.is_file():
                        add("project-schema", str(optional_manifest.relative_to(root)), "Missing optional configuration schema")
                        continue
                    try:
                        optional_data = (read_json(optional_manifest) if optional_name.endswith(".json")
                                         else read_yaml(optional_manifest))
                        messages = _schema_errors(optional_data, optional_schema)
                        if optional_name == "external-capabilities.yaml" and messages:
                            # Schema messages may contain user-supplied credential values.
                            add("project-schema", str(optional_manifest.relative_to(root)), "Invalid external capability metadata")
                        else:
                            for message in messages:
                                add("project-schema", str(optional_manifest.relative_to(root)), message)
                    except Exception:
                        add("project-schema", str(optional_manifest.relative_to(root)), "Invalid optional configuration")

            policy_manifest = manifest.parent / "policy.yaml"
            if not policy_manifest.is_file():
                add(
                    "policy-schema",
                    str(policy_manifest.relative_to(root)),
                    "Missing policy.yaml",
                )
            elif policy_schema.exists():
                for message in _schema_errors(
                    read_yaml(policy_manifest) or {},
                    policy_schema,
                ):
                    add(
                        "policy-schema",
                        str(policy_manifest.relative_to(root)),
                        message,
                    )

            knowledge_manifest = manifest.parent / "knowledge.yaml"
            knowledge_data: dict[str, Any] = {}
            if not knowledge_manifest.is_file():
                add(
                    "knowledge-schema",
                    str(knowledge_manifest.relative_to(root)),
                    "Missing knowledge.yaml",
                )
            else:
                knowledge_data = read_yaml(knowledge_manifest) or {}
                if knowledge_schema.exists():
                    for message in _schema_errors(
                        knowledge_data,
                        knowledge_schema,
                    ):
                        add(
                            "knowledge-schema",
                            str(knowledge_manifest.relative_to(root)),
                            message,
                        )

            validation_manifest = manifest.parent / "validation.yaml"
            if not validation_manifest.is_file():
                add(
                    "validation-schema",
                    str(validation_manifest.relative_to(root)),
                    "Missing validation.yaml",
                )
            elif validation_config_schema.exists():
                for message in _schema_errors(
                    read_yaml(validation_manifest) or {},
                    validation_config_schema,
                ):
                    add(
                        "validation-schema",
                        str(validation_manifest.relative_to(root)),
                        message,
                    )

            agents_manifest = manifest.parent / "agents.yaml"
            if not agents_manifest.is_file():
                add(
                    "agents-schema",
                    str(agents_manifest.relative_to(root)),
                    "Missing agents.yaml",
                )
            elif project_agents_schema.exists():
                for message in _schema_errors(
                    read_yaml(agents_manifest) or {},
                    project_agents_schema,
                ):
                    add(
                        "agents-schema",
                        str(agents_manifest.relative_to(root)),
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
            knowledge_entries: list[tuple[str, Any]] = []
            slot_bindings = knowledge_data.get("slots") or {}
            for slot, value in slot_bindings.items():
                if value is not None:
                    knowledge_entries.append((f"slot:{slot}", value))
            knowledge_entries.extend(
                (str(knowledge_id), value)
                for knowledge_id, value in knowledge_data.items()
                if knowledge_id != "slots"
            )

            for knowledge_id, value in knowledge_entries:
                relative = value.get("path") if isinstance(value, dict) else value
                if not relative:
                    add(
                        "project-knowledge",
                        str(knowledge_manifest.relative_to(root)),
                        f"knowledge '{knowledge_id}' has no path",
                    )
                    continue

                target = (project_root / str(relative)).resolve()
                try:
                    target.relative_to(project_root.resolve())
                except ValueError:
                    add(
                        "project-knowledge",
                        str(knowledge_manifest.relative_to(root)),
                        f"knowledge '{knowledge_id}' escapes the project root",
                    )
                    continue

                if not target.is_file():
                    add(
                        "project-knowledge",
                        str(knowledge_manifest.relative_to(root)),
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

    skill_eval_schema = root / "schemas/skill-eval.schema.json"
    for path in sorted((root / "evals/skills").glob("*.json")):
        if not skill_eval_schema.is_file():
            add("skill-eval-schema", str(path.relative_to(root)), "Missing skill evaluation schema")
            continue
        try:
            for message in _schema_errors(read_json(path), skill_eval_schema):
                add("skill-eval-schema", str(path.relative_to(root)), message)
        except Exception:
            add("skill-eval-schema", str(path.relative_to(root)), "Invalid skill evaluation JSON")

    for code, path, message in _unity_extension_issues(root, current_framework_version):
        add(code, path, message)

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

    # Public documentation is bilingual: English is canonical and every
    # canonical page must have a Russian suffix translation next to it.
    docs_root = root / "docs"
    english_docs = {
        path.relative_to(docs_root)
        for path in docs_root.rglob("*.md")
        if not path.name.endswith(".ru.md")
    }
    russian_docs = {
        Path(str(path.relative_to(docs_root)).replace(".ru.md", ".md"))
        for path in docs_root.rglob("*.ru.md")
    }

    for relative in sorted(english_docs - russian_docs):
        add(
            "localization",
            str(docs_root / relative),
            "Missing Russian translation (.ru.md)",
        )

    for relative in sorted(russian_docs - english_docs):
        add(
            "localization",
            str(docs_root / relative),
            "Russian translation has no canonical English source",
        )

    legacy_localization = root / "localization"
    if legacy_localization.exists():
        add(
            "localization",
            "localization",
            "Legacy localization/ tree must not exist; use docs/*.ru.md and root README.ru.md / TRADEMARKS.ru.md",
        )

    for required in (root / "README.ru.md", root / "TRADEMARKS.ru.md"):
        if not required.is_file():
            add(
                "localization",
                str(required.relative_to(root)),
                "Missing required Russian translation",
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
