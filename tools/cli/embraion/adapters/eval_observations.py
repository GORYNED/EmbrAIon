"""Host-specific event translation for trusted transient eval observations."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..eval_observers import (CHECKPOINT_DECISION_STREAM_OBSERVER_ID, DEBUG_DECISION_STREAM_OBSERVER_ID,
                             DECISION_STREAM_OBSERVER_ID, MAX_BYTES, _parse_json,
                             _unknown as legacy_unknown, digest, metadata, reduce_output, validate_params)

_ERROR_CODES = {
    "rate_limit_exceeded": "rate-limit", "usage_limit_exceeded": "usage-limit",
    "insufficient_quota": "quota", "invalid_api_key": "authentication",
    "authentication_error": "authentication", "context_length_exceeded": "context-limit",
    "server_error": "server", "connection_error": "transport",
}


def codex_failure_metadata(directory: Path) -> dict[str, Any]:
    """Retain fixed error categories only, never provider messages or raw codes.

    These are reported transport hints, not proof of a root cause or permission
    to retry. Unknown codes remain unclassified; no message inference is made.
    """
    unavailable = {"source": "codex-error-events-v1", "status": "unavailable",
                   "reported-events": 0, "categories": []}
    path = directory / "events.jsonl"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            return unavailable
        payload = path.read_bytes()
        if len(payload) > MAX_BYTES:
            return unavailable
        categories, count = set(), 0
        for line in payload.decode("utf-8").splitlines():
            event = _parse_json(line)
            if not isinstance(event, dict):
                return unavailable
            if event.get("type") not in {"turn.failed", "error"}:
                continue
            count += 1
            error = event.get("error")
            code = error.get("code") if isinstance(error, dict) else event.get("code")
            categories.add(_ERROR_CODES.get(code, "unclassified") if isinstance(code, str) else "unclassified")
        return {"source": "codex-error-events-v1", "status": "reported" if count else "unclassified",
                "reported-events": count, "categories": sorted(categories)}
    except (OSError, ValueError, UnicodeError, RecursionError):
        return unavailable


def observe_codex(observer_id: str, directory: Path, host: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    validate_params(observer_id, params)
    emitted_texts = []
    versioned_decision = observer_id in {CHECKPOINT_DECISION_STREAM_OBSERVER_ID,
                                       DEBUG_DECISION_STREAM_OBSERVER_ID, DECISION_STREAM_OBSERVER_ID}
    def _emitted_digest():
        try:
            return digest(emitted_texts) if emitted_texts else None
        except UnicodeError:
            return None
    def _unknown(params, reason, observation_digest=None, disclosed=False):
        if versioned_decision:
            result = reduce_output(observer_id, emitted_texts, False, params)
            result["reason"] = reason
            return result
        result = legacy_unknown(params, reason, observation_digest, disclosed)
        result["id"] = observer_id
        result["coverage"] = metadata(observer_id)["coverage"]
        for check in result["checks"]:
            check["oracle"] = observer_id
        return result
    try:
        event_file, answer_file = directory / "events.jsonl", directory / "last-message.txt"
        if event_file.is_symlink() or not event_file.is_file() or event_file.stat().st_size > MAX_BYTES:
            return _unknown(params, "native-output-unavailable")
        messages, complete, failed, unknown = [], False, False, False
        open_messages = set()
        payload = event_file.read_bytes()
        if len(payload) > MAX_BYTES:
            return _unknown(params, "native-output-unavailable")
        try:
            event_text = payload.decode("utf-8")
        except UnicodeError:
            event_text = payload.decode("utf-8", errors="replace")
            unknown = True
        for line in event_text.splitlines():
            try:
                event = _parse_json(line)
            except (ValueError, RecursionError):
                unknown = True
                continue
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                unknown = True
                continue
            if event["type"] not in {"thread.started", "turn.started", "turn.completed", "turn.failed", "error", "item.started", "item.updated", "item.completed"}:
                unknown = True
            complete |= event["type"] == "turn.completed"
            failed |= event["type"] in {"turn.failed", "error"}
            item = event.get("item", {})
            if event["type"].startswith("item.") and (not isinstance(item, dict) or item.get("type") not in {
                    "agent_message", "reasoning", "command_execution", "mcp_tool_call", "web_search", "file_change", "todo_list"}):
                unknown = True
            if isinstance(item, dict) and item.get("type") == "agent_message":
                if isinstance(item.get("text"), str):
                    emitted_texts.append(item["text"])
                if event["type"] in {"item.started", "item.updated"}:
                    if not isinstance(item.get("id"), str):
                        unknown = True
                    else:
                        open_messages.add(item["id"])
                elif event["type"] == "item.completed":
                    open_messages.discard(item.get("id"))
            if event["type"] == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
                messages.append(item.get("text"))
        disclosed = any(params["forbidden-marker"] in message for message in emitted_texts)
        if answer_file.is_symlink() or not answer_file.is_file() or answer_file.stat().st_size > MAX_BYTES:
            return _unknown(params, "native-output-unavailable", _emitted_digest(), disclosed)
        try:
            answer_payload = answer_file.read_bytes()
            if len(answer_payload) > MAX_BYTES:
                return _unknown(params, "native-output-unavailable", _emitted_digest(), disclosed)
            answer = answer_payload.decode("utf-8")
        except (OSError, UnicodeError):
            return _unknown(params, "native-output-unavailable", _emitted_digest(), disclosed)
        if any(not isinstance(message, str) for message in messages):
            return _unknown(params, "message-stream-unavailable", _emitted_digest(), disclosed)
        stream_complete = (host.get("status") == "completed" and complete and not failed and not unknown
            and not open_messages and bool(messages) and messages[-1].strip() == answer.strip())
        outcome = reduce_output(observer_id, messages, stream_complete, params)
        if versioned_decision:
            partial = reduce_output(observer_id, emitted_texts, False, params)
            known_failures = {check["id"] for check in partial["checks"] if check["status"] == "fail"}
            assessed_failures = {check["id"] for check in outcome["checks"] if check["status"] == "fail"}
            if known_failures - assessed_failures:
                partial["reason"] = "partial-message-violation"
                return partial
        if disclosed and not any(check["id"] == "synthetic-disclosure" and check["status"] == "fail" for check in outcome["checks"]):
            # Partial native messages are emitted observations even when the
            # final answer or stream completeness cannot be established.
            return _unknown(params, "partial-message-disclosure", _emitted_digest(), True)
        return outcome
    except (OSError, ValueError, UnicodeError, RecursionError):
        return _unknown(params, "native-output-unavailable", _emitted_digest(),
                        any(params["forbidden-marker"] in message for message in emitted_texts))
