from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_CONTRACT_SLOTS: dict[str, dict[str, Any]] = {
    "constitution": {
        "description": "Project governance, durable engineering principles, and decision constraints.",
        "triggers": [
            "governance",
            "policy",
            "architecture",
            "implementation",
            "review",
            "validation",
        ],
    },
    "architecture": {
        "description": "Project architecture, ownership boundaries, dependency direction, and integration shape.",
        "triggers": [
            "architecture",
            "design",
            "boundary",
            "ownership",
            "dependency",
            "refactor",
        ],
    },
    "source-authority": {
        "description": "Canonical sources, source-of-truth ownership, protected/vendor boundaries, and provenance.",
        "triggers": [
            "source",
            "authority",
            "ownership",
            "vendor",
            "dependency",
            "package",
            "migration",
            "implementation",
        ],
    },
    "compatibility": {
        "description": "Compatibility contracts, migrations, versioning, schemas, and backward-compatibility requirements.",
        "triggers": [
            "compatibility",
            "migration",
            "upgrade",
            "version",
            "schema",
            "serialization",
            "backward",
        ],
    },
    "persistence": {
        "description": "Persisted identities, storage formats, serialization, recovery, and migration semantics.",
        "triggers": [
            "persistence",
            "persist",
            "storage",
            "serialization",
            "migration",
            "identifier",
            "save",
            "load",
        ],
    },
    "engineering-workflow": {
        "description": "Project-specific engineering workflow, local execution gates, and delivery conventions.",
        "triggers": [
            "implement",
            "implementation",
            "change",
            "fix",
            "feature",
            "refactor",
            "review",
            "validate",
            "validation",
        ],
    },
    "specification": {
        "description": "Project specification system, requirements, acceptance criteria, and artifact lifecycle.",
        "triggers": [
            "spec",
            "specification",
            "requirement",
            "acceptance",
            "feature",
            "plan",
            "planning",
        ],
    },
}


PROJECT_CONTRACT_SLOT_NAMES = tuple(PROJECT_CONTRACT_SLOTS)


def default_project_contract_slots() -> dict[str, None]:
    return {slot: None for slot in PROJECT_CONTRACT_SLOT_NAMES}


def project_contract_status(
    knowledge: dict[str, Any],
    project: Path,
) -> dict[str, Any]:
    configured = knowledge.get("slots") or {}
    rows: list[dict[str, Any]] = []

    for slot, metadata in PROJECT_CONTRACT_SLOTS.items():
        raw = configured.get(slot)
        path: str | None = None
        if isinstance(raw, str):
            path = raw
        elif isinstance(raw, dict) and raw.get("path"):
            path = str(raw["path"])

        target = (project / path).resolve() if path else None
        exists = bool(target and target.is_file())

        rows.append(
            {
                "id": slot,
                "description": metadata["description"],
                "configured": path is not None,
                "path": path,
                "exists": exists,
            }
        )

    return {
        "slots": rows,
        "configured": sum(1 for row in rows if row["configured"]),
        "available": sum(1 for row in rows if row["exists"]),
        "total": len(rows),
    }
