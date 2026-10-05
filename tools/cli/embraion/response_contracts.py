"""Trusted, public output shapes for opt-in native experiment responses.

These schemas constrain syntax only. Observer parameters and source-derived gold
remain in the controller and are never incorporated into a native schema.
"""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .common import framework_root


# A fixed registry prevents suite data from selecting a path or command.
CONTRACTS = {
    "artifact-response-v1": ("response-artifact.schema.json", "finite-stream-v1"),
    "research-response-v1": ("response-research.schema.json", "decision-stream-v1"),
    "debug-response-v1": ("response-debug.schema.json", "debug-decision-stream-v1"),
    "checkpoint-response-v1": ("response-checkpoint.schema.json", "checkpoint-decision-stream-v1"),
    "security-response-v1": ("response-security.schema.json", "finite-stream-v1"),
}


def resolve_response_contract(contract_id: str, observer: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve a registered public shape and reject incompatible observer gold."""
    if not isinstance(contract_id, str) or contract_id not in CONTRACTS:
        raise ValueError("unknown response contract")
    filename, expected_observer = CONTRACTS[contract_id]
    if observer is not None:
        if observer.get("id") != expected_observer or observer.get("mandatory") is not True:
            raise ValueError("response contract requires matching mandatory observer")
        if (contract_id == "artifact-response-v1"
                and observer.get("params", {}).get("required-procedures") != {}):
            raise ValueError("artifact response contract requires empty expected procedures")
        if contract_id == "security-response-v1" and not set(
                observer.get("params", {}).get("required-procedures", {})).issubset({"security-assessment"}):
            raise ValueError("security response contract requires only security assessment")
    path = framework_root() / "schemas" / filename
    if (path.parent.is_symlink() or path.is_symlink() or not path.is_file()
            or path.stat().st_size > 100_000):
        raise ValueError("response contract schema unavailable")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, UnicodeError, TypeError, SchemaError):
        raise ValueError("response contract schema unavailable") from None
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("invalid response contract schema")
    return schema
