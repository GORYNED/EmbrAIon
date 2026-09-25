from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root, read_json, state_root, write_json
from .contracts import PROJECT_CONTRACT_SLOTS
from .policy import effective_policy, read_knowledge_config
from .security import redact_value


DATA_LEVEL = {
    "PUBLIC": 0,
    "PRIVATE": 1,
    "CONFIDENTIAL": 2,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_entry(
    knowledge_id: str,
    value: Any,
    default_data_class: str,
    *,
    default_triggers: list[str] | None = None,
    slot: str | None = None,
) -> dict[str, Any]:
    if isinstance(value, str):
        item = {
            "id": knowledge_id,
            "path": value,
            "data-class": default_data_class,
            "trust": "project",
            "roles": [],
            "triggers": list(default_triggers or []),
        }
    else:
        if not isinstance(value, dict) or not value.get("path"):
            raise RuntimeError(f"Invalid knowledge entry '{knowledge_id}'.")

        item = {
            "id": knowledge_id,
            "path": str(value["path"]),
            "data-class": str(value.get("data-class", default_data_class)),
            "trust": str(value.get("trust", "project")),
            "roles": [str(entry) for entry in value.get("roles", [])],
            "triggers": [
                str(entry)
                for entry in (
                    value["triggers"]
                    if "triggers" in value
                    else (default_triggers or [])
                )
            ],
        }

    if slot is not None:
        item["slot"] = slot
    return item


def _knowledge_entries(
    knowledge: dict[str, Any],
    default_data_class: str,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    slot_bindings = knowledge.get("slots") or {}

    for slot, metadata in PROJECT_CONTRACT_SLOTS.items():
        raw = slot_bindings.get(slot)
        if raw is None:
            continue
        entries.append(
            _normalize_entry(
                f"slot:{slot}",
                raw,
                default_data_class,
                default_triggers=list(metadata["triggers"]),
                slot=slot,
            )
        )

    for knowledge_id, raw in knowledge.items():
        if knowledge_id == "slots":
            continue
        entries.append(
            _normalize_entry(
                str(knowledge_id),
                raw,
                default_data_class,
            )
        )

    return entries


def _is_inside(project: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(project.resolve())
        return True
    except ValueError:
        return False


def build_context(
    task: str,
    role: str,
    data_class: str,
    *,
    max_chars: int = 20000,
    slots: list[str] | None = None,
    project: Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if data_class not in DATA_LEVEL:
        raise RuntimeError(f"Unknown data class: {data_class}")
    if max_chars < 0:
        raise RuntimeError("--max-chars must be zero or greater.")

    requested_slots = list(dict.fromkeys(slots or []))
    unknown_slots = [
        slot for slot in requested_slots
        if slot not in PROJECT_CONTRACT_SLOTS
    ]
    if unknown_slots:
        raise RuntimeError(
            "Unknown project contract slot(s): " + ", ".join(unknown_slots)
        )

    root = project_root(project)
    knowledge = read_knowledge_config(root)
    policy = effective_policy(root)
    default_data = str(policy["privacy"]["default-class"])
    task_lower = task.lower()

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    total_chars = 0

    configured_slots = knowledge.get("slots") or {}
    for slot in requested_slots:
        if configured_slots.get(slot) is None:
            excluded.append(
                {"id": f"slot:{slot}", "reason": "unconfigured"}
            )

    for item in _knowledge_entries(knowledge, default_data):
        item_data = item["data-class"]
        force_slot = item.get("slot") in requested_slots

        if item_data not in DATA_LEVEL:
            excluded.append({"id": item["id"], "reason": "unknown-data-class"})
            continue
        if DATA_LEVEL[item_data] > DATA_LEVEL[data_class]:
            excluded.append({"id": item["id"], "reason": "data-class"})
            continue
        if item["roles"] and role not in item["roles"]:
            excluded.append({"id": item["id"], "reason": "role"})
            continue
        if item["triggers"] and not force_slot and not any(
            trigger.lower() in task_lower for trigger in item["triggers"]
        ):
            excluded.append({"id": item["id"], "reason": "trigger"})
            continue

        target = (root / item["path"]).resolve()
        if not _is_inside(root, target):
            excluded.append({"id": item["id"], "reason": "outside-project"})
            continue
        if not target.is_file():
            excluded.append({"id": item["id"], "reason": "missing"})
            continue

        chars = len(target.read_text(encoding="utf-8", errors="replace"))
        if total_chars + chars > max_chars:
            excluded.append({"id": item["id"], "reason": "budget"})
            continue

        selected.append(
            {
                **item,
                "sha256": _sha256(target),
                "chars": chars,
                "reason": "eligible",
            }
        )
        total_chars += chars

    context_id = uuid.uuid4().hex
    record = redact_value(
        {
            "schema-version": 1,
            "context-id": context_id,
            "task": task,
            "role": role,
            "data-class": data_class,
            "max-chars": max_chars,
            "requested-slots": requested_slots,
            "selected": selected,
            "excluded": excluded,
            "total-chars": total_chars,
            "created-utc": datetime.now(timezone.utc).isoformat(),
        }
    )

    if persist:
        destination = state_root(root) / "context" / f"{context_id}.json"
        write_json(destination, record)

    return record


def read_context(context_id: str, project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = state_root(root) / "context" / f"{context_id}.json"
    if not path.is_file():
        raise RuntimeError(f"Unknown context record: {context_id}")
    return read_json(path)
