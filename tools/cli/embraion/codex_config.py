"""Syntax-preserving ownership of the Codex orchestration projection."""
from __future__ import annotations

import tomllib
from copy import deepcopy

import tomlkit
from tomlkit.items import Comment, Table

AGENTS_BEGIN = "# >>> EmbrAIon managed: agents"
AGENTS_END = "# <<< EmbrAIon managed: agents"
ORCHESTRATION_BEGIN = "# >>> EmbrAIon managed: orchestration"
ORCHESTRATION_END = "# <<< EmbrAIon managed: orchestration"
AGENTS_SETTINGS = {"enabled": True, "max_concurrent_threads_per_session": 3}


def _unsafe(reason: str) -> RuntimeError:
    return RuntimeError(f"Cannot safely merge .codex/config.toml: {reason}")


def orchestration_block(instructions: str) -> str:
    return f"{ORCHESTRATION_BEGIN}\n{instructions.strip()}\n{ORCHESTRATION_END}"


def _instruction_parts(value: str) -> tuple[str, str, bool]:
    # Delimiters belong to the parsed instruction value, never to TOML syntax.
    counts = (value.count(ORCHESTRATION_BEGIN), value.count(ORCHESTRATION_END))
    if counts == (0, 0):
        return value, "", False
    if counts != (1, 1):
        raise _unsafe("duplicate or incomplete orchestration markers")
    begin = value.index(ORCHESTRATION_BEGIN)
    end = value.index(ORCHESTRATION_END)
    if end < begin:
        raise _unsafe("orchestration markers are out of order")
    for index, marker in ((begin, ORCHESTRATION_BEGIN), (end, ORCHESTRATION_END)):
        if (index and value[index - 1] != "\n") or (
            index + len(marker) < len(value) and value[index + len(marker)] != "\n"
        ):
            raise _unsafe("orchestration markers must occupy complete lines")
    return value[:begin], value[end + len(ORCHESTRATION_END):], True


def merge_codex_config(existing: str, generated: str) -> str:
    try:
        before = tomllib.loads(existing)
        expected = tomllib.loads(generated)
        document = tomlkit.parse(existing)
    except (ValueError, tomlkit.exceptions.ParseError) as error:
        raise _unsafe(f"invalid TOML: {error}") from error

    instructions = before.get("developer_instructions", "")
    if not isinstance(instructions, str):
        raise _unsafe("root developer_instructions must be a string")
    prefix, suffix, owned = _instruction_parts(instructions)
    block = expected["developer_instructions"]
    generated_prefix, generated_suffix, generated_owned = _instruction_parts(block)
    if not generated_owned or generated_prefix or generated_suffix:
        raise _unsafe("generated orchestration ownership is invalid")
    effective = prefix + block + suffix if owned else instructions + ("\n\n" if instructions else "") + block

    # Reserved ownership delimiters anywhere else are ambiguous, including
    # nested instructions and table-looking lines inside multiline strings.
    for marker in (ORCHESTRATION_BEGIN, ORCHESTRATION_END):
        if existing.count(marker) != instructions.count(marker):
            raise _unsafe("orchestration markers outside root developer_instructions")

    agents = document.get("agents")
    if agents is None:
        agents = tomlkit.table()
    if not isinstance(agents, Table) or agents.is_super_table():
        raise _unsafe("agents must use a single explicit TOML table for managed ownership")
    body = agents.value.body
    begin = [i for i, (_, item) in enumerate(body) if isinstance(item, Comment) and item.as_string().strip() == AGENTS_BEGIN]
    end = [i for i, (_, item) in enumerate(body) if isinstance(item, Comment) and item.as_string().strip() == AGENTS_END]
    for marker, indexes in ((AGENTS_BEGIN, begin), (AGENTS_END, end)):
        if existing.count(marker) != len(indexes):
            raise _unsafe("agents markers outside [agents] or duplicated")
    if len(begin) > 1 or len(end) > 1 or bool(begin) != bool(end):
        raise _unsafe("duplicate or incomplete agents markers")
    if begin:
        if end[0] < begin[0]:
            raise _unsafe("agents markers are out of order")
        keys = [key.key for key, _ in body[begin[0] + 1:end[0]] if key is not None]
        if set(keys) != set(AGENTS_SETTINGS) or len(keys) != len(AGENTS_SETTINGS):
            raise _unsafe("agents managed block has missing or unrelated fields")

    if begin:
        for key, value in AGENTS_SETTINGS.items():
            agents[key] = value
    else:
        updated = tomlkit.table()
        if agents.trivia.comment:
            updated.comment(agents.trivia.comment)
        # Comments appended after a child table are emitted in that child's
        # scope even when scalar keys are reordered by the TOML serializer.
        # Put the entire managed block before all user scalar/child entries.
        updated.add(tomlkit.comment(AGENTS_BEGIN[2:]))
        for key, value in AGENTS_SETTINGS.items():
            updated.add(key, value)
        updated.add(tomlkit.comment(AGENTS_END[2:]))
        for key, item in body:
            if key is not None and key.key in AGENTS_SETTINGS:
                continue
            updated.add(deepcopy(key), deepcopy(item))
        document["agents"] = updated
    if effective != instructions:
        document["developer_instructions"] = tomlkit.string(effective, multiline=True)
    merged = tomlkit.dumps(document)

    try:
        after = tomllib.loads(merged)
    except ValueError as error:
        raise _unsafe(f"merged TOML is invalid: {error}") from error
    preserved_before = deepcopy(before)
    preserved_after = deepcopy(after)
    for value in (preserved_before, preserved_after):
        value.pop("developer_instructions", None)
        agent_values = value.pop("agents", {})
        for key in AGENTS_SETTINGS:
            agent_values.pop(key, None)
        if agent_values:
            value["agents"] = agent_values
    if preserved_before != preserved_after or after["developer_instructions"] != effective or any(
        after["agents"].get(key) != value for key, value in AGENTS_SETTINGS.items()
    ):
        raise _unsafe("non-managed content changed or managed settings are ineffective")
    return merged


# Root keys that silently replace the user's root model or effort choice, or the
# routed subagent selection. Projects may extend this list but never shrink it.
DEFAULT_FORBIDDEN_ROOT_KEYS = (
    "model",
    "model_reasoning_effort",
    "agents.default_subagent_*",
)
MANAGED_ROOT_KEYS = ("developer_instructions", "agents")


def _key_paths(value: dict, prefix: str = "") -> list[str]:
    paths: list[str] = []
    for key, item in value.items():
        path = f"{prefix}{key}"
        paths.append(path)
        if isinstance(item, dict):
            paths.extend(_key_paths(item, path + "."))
    return paths


def codex_root_findings(
    existing: str,
    *,
    forbidden_keys: list[str] | tuple[str, ...] = DEFAULT_FORBIDDEN_ROOT_KEYS,
    allowed_root_keys: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    """Report user content outside managed ownership that merge preserves.

    Merge mode intentionally keeps user content, so these findings never make a
    merge unsafe; verify reports them and fails only when strict root is chosen.
    """
    from fnmatch import fnmatchcase

    try:
        values = tomllib.loads(existing)
    except ValueError as error:
        return [{"code": "root-config-invalid", "path": "<root>", "message": f"invalid TOML: {error}"}]

    findings: list[dict[str, str]] = []
    for path in _key_paths(values):
        if any(fnmatchcase(path, pattern) for pattern in forbidden_keys):
            findings.append({
                "code": "root-key-override",
                "path": path,
                "message": "Overrides the root model/effort or routed subagent selection outside EmbrAIon ownership.",
            })
    if allowed_root_keys is not None:
        allowed = set(allowed_root_keys) | set(MANAGED_ROOT_KEYS)
        for key in sorted(set(values) - allowed):
            findings.append({
                "code": "root-key-unreviewed",
                "path": key,
                "message": "Root key is not in the project's allowed-root-keys.",
            })

    instructions = values.get("developer_instructions")
    if isinstance(instructions, str):
        try:
            prefix, suffix, owned = _instruction_parts(instructions)
        except RuntimeError as error:
            findings.append({"code": "root-instructions-markers", "path": "developer_instructions", "message": str(error)})
        else:
            if (prefix + suffix).strip() if owned else instructions.strip():
                findings.append({
                    "code": "root-instructions-unmanaged-text",
                    "path": "developer_instructions",
                    "message": "Root developer_instructions contain text outside the EmbrAIon managed orchestration block.",
                })
    return findings
