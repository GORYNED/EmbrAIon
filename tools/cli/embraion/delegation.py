"""Prepare native representations of an already resolved assignment; never execute."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .common import framework_root, read_yaml


def prepare_native_assignment(
    selected: dict[str, Any],
    surface: str,
    *,
    role: str,
    existing: dict[str, Any] | None = None,
    verified_native_fields: list[str] | None = None,
    native_agent: str | None = None,
    project: Path | None = None,
    access: str | None = None,
) -> dict[str, Any]:
    """Static translation is not proof of installed capabilities or applied settings."""
    surfaces = read_yaml(framework_root() / "adapters/harness-capabilities.yaml")["delegation-surfaces"]
    spec = surfaces.get(surface)
    plan: dict[str, Any] = {
        "surface": surface,
        "status": "prepared",
        "executed": False,
        "arguments": {},
        "definition-overrides": {},
        "limitations": [],
        "requirements": [
            "verify installed native tool schema and selected specialist role",
            "verify selector, effort, options, effective precedence, privacy and access before invocation",
            "preserve the bounded assignment and original specialist permissions",
            "record actual native invocation and verify effective settings before claiming success",
        ],
        "reuse": "fresh-assignment",
    }

    def block(reason: str) -> dict[str, Any]:
        plan["status"] = "capability-limitation"
        plan["limitations"].append(reason)
        # A partially translated choice must never look dispatchable.
        plan["arguments"] = {}
        plan["definition-overrides"] = {}
        plan.pop("scoped-definition", None)
        return plan

    if not spec or spec["mode"] != "runtime":
        return block("This surface has no verified native delegation mechanism; Portable is an interchange bundle.")
    if native_agent is not None and surface != "claude-agent":
        return block("Explicit native-agent binding is currently supported only for Claude definitions.")
    plan["mechanism"] = spec["mechanism"]
    plan["sources"] = spec["sources"]
    resolution = selected.get("resolution")
    if not isinstance(resolution, str) or resolution not in {"host-default", "project-override", "project-deployment"}:
        return block("Missing or unknown routing resolution is not host-default.")
    if selected.get("host") != spec["host"]:
        plan["status"] = "handoff-required"
        plan["limitations"].append("Selected host differs from this native surface; resolve a supported handoff with fresh privacy/access checks.")
        return plan
    settings = {key: selected.get(key) for key in ("model", "effort")}
    options = selected.get("options")
    if options is None:
        options = {}
    if not isinstance(options, dict):
        return block("Resolved options must be a mapping.")
    if resolution == "host-default" and (any(value is not None for value in settings.values()) or options):
        return block("Host-default must not contain explicit project selection fields.")
    if resolution != "host-default" and not any(value is not None for value in settings.values()) and not options:
        return block("Explicit routing has no applicable selection fields.")
    supported_options = spec.get("options") or {}
    unknown_options = [key for key in options if key not in supported_options]
    if unknown_options:
        return block("Native option translation is not verified for these keys: " + ", ".join(sorted(map(str, unknown_options))))
    for key, value in options.items():
        if not Draft202012Validator(supported_options[key]["schema"]).is_valid(value):
            return block("Native option conflicts with mandatory routing semantics: " + key)

    for key, value in settings.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            return block(f"Explicit {key} must be a non-empty native selector.")
        binding = spec.get(key)
        conditional = spec.get("conditional-" + key)
        if not binding and conditional and conditional["field"] in (verified_native_fields or []):
            binding = conditional
            plan["requirements"].append("retain installed-version/schema evidence for conditional field " + binding["field"])
        if not binding:
            return block(f"Per-assignment {key} is not verified on this installed surface; verify a supported mechanism or hand off.")
        if key == "effort" and spec.get("effort-levels") and value not in spec["effort-levels"]:
            return block("Requested effort is outside this surface's documented levels.")
        plan[binding["location"]][binding["field"]] = value

    if spec.get("bounded-fork"):
        plan["arguments"]["agent_type"] = role
        if any(value is not None for value in settings.values()):
            plan["arguments"]["fork_turns"] = "none"
        plan["requirements"].append("confirm spawn fields and custom role config do not replace explicit settings")
    if spec.get("required-model-policy") and settings["model"] is not None:
        plan["definition-overrides"]["modelPolicy"] = "required"
    for key, value in options.items():
        binding = supported_options[key]
        plan[binding["location"]][binding["field"]] = value
    if plan["definition-overrides"]:
        plan["requirements"].append("merge these derived fields into a scoped native definition preserving the selected role and access; load/select it before dispatch")
    if surface == "claude-agent":
        from .project import _agent_instructions, _claude_agent_name, _host_access_projection, load_agents

        identity = native_agent or role
        agent = next((item for item in load_agents(framework_root(), project)
                      if item["id"] == identity and identity != "lead"), None)
        if agent is None:
            return block("No native specialist definition for this routing role; select an explicit native-agent binding.")
        if not agent.get("purpose", "").strip():
            return block("The native specialist requires a nonblank description.")
        agent = dict(agent)
        read_access = {"inspect", "plan", "review", "external-read", "read-only"}
        narrower_access = access in read_access and agent.get("access") != "read-only"
        if access in read_access:
            agent["access"] = "read-only"
        elif access not in {None, "write", "workspace-write"}:
            return block("Unknown native assignment access; permissions cannot be inferred.")
        # A writable assignment cannot widen a read-only specialist's tool set.
        tools = list(_host_access_projection("claude-code", agent)["tools"])
        if plan["definition-overrides"] or narrower_access:
            definition = {
                "description": agent.get("purpose", ""),
                "prompt": _agent_instructions(agent),
                "tools": tools,
                **plan["definition-overrides"],
            }
            digest = hashlib.sha256(json.dumps({"role": identity, "definition": definition},
                                               sort_keys=True).encode()).hexdigest()[:12]
            # Claude AgentSpec limits names to 64 characters; project IDs can
            # be longer. Hash the full identity to retain distinct bindings.
            name = f"embraion-{identity[:42]}-{digest}"
            plan["scoped-definition"] = {"name": name, **definition}
            plan["arguments"]["subagent_type"] = name
        else:
            plan["arguments"]["subagent_type"] = _claude_agent_name(identity)
        plan["requirements"].append("supply the bounded task prompt separately; subagent_type is usable only after its exact definition is loaded")
    if spec.get("definition-handoff") and (plan["definition-overrides"] or plan.get("scoped-definition")):
        plan["status"] = "handoff-required"
        plan["requirements"].append("load the complete scoped definition through the native agent loader or a fresh --agents session; do not invent Agent model IDs or effort arguments")

    if existing:
        matches = (existing.get("effective-settings-verified") is True
                   and existing.get("surface") == surface and existing.get("role") == role
                   and all(isinstance(existing.get(key), str) and existing[key].strip()
                           for key in ("model", "effort")))
        if resolution == "host-default":
            matches = matches and existing.get("resolution") == "host-default" and existing.get("current-host-defaults-verified") is True
        else:
            matches = matches and all(value is None or existing.get(key) == value for key, value in settings.items())
            matches = matches and (existing.get("options") or {}) == options
        if surface == "claude-agent":
            matches = (matches and existing.get("native-agent") == plan["arguments"]["subagent_type"]
                       and existing.get("effective-tools") == tools)
        if matches:
            plan["reuse"] = "verified-existing-agent"
    return plan
