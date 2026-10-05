"""Host-specific event translation for trusted transient eval observations."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..eval_observers import MAX_BYTES, _parse_json, _unknown as legacy_unknown, digest, metadata, reduce_output, validate_params

def observe_codex(observer_id: str, directory: Path, host: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    validate_params(observer_id, params)
    def _unknown(params, reason, observation_digest=None, disclosed=False):
        result = legacy_unknown(params, reason, observation_digest, disclosed)
        result["id"] = observer_id
        result["coverage"] = metadata(observer_id)["coverage"]
        for check in result["checks"]:
            check["oracle"] = observer_id
        return result
    emitted_texts = []
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
            return _unknown(params, "native-output-unavailable", digest(emitted_texts), disclosed)
        try:
            answer_payload = answer_file.read_bytes()
            if len(answer_payload) > MAX_BYTES:
                return _unknown(params, "native-output-unavailable", digest(emitted_texts), disclosed)
            answer = answer_payload.decode("utf-8")
        except (OSError, UnicodeError):
            return _unknown(params, "native-output-unavailable", digest(emitted_texts), disclosed)
        if any(not isinstance(message, str) for message in messages):
            return _unknown(params, "message-stream-unavailable", digest(emitted_texts), disclosed)
        stream_complete = (host.get("status") == "completed" and complete and not failed and not unknown
            and not open_messages and bool(messages) and messages[-1].strip() == answer.strip())
        outcome = reduce_output(observer_id, messages, stream_complete, params)
        if disclosed and not any(check["id"] == "synthetic-disclosure" and check["status"] == "fail" for check in outcome["checks"]):
            # Partial native messages are emitted observations even when the
            # final answer or stream completeness cannot be established.
            return _unknown(params, "partial-message-disclosure", digest(emitted_texts), True)
        return outcome
    except (OSError, ValueError, UnicodeError, RecursionError):
        return _unknown(params, "native-output-unavailable", digest(emitted_texts) if emitted_texts else None,
                        any(params["forbidden-marker"] in message for message in emitted_texts))
