"""Fail-closed context envelopes for adapters that require bound repository context.

The builder reads only committed blob content at one explicit commit, never the
working tree. Every refusal names the repository-relative path and the reason;
no refused content is echoed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .common import project_root
from .context import DATA_LEVEL, _knowledge_entries
from .environment import child_environment
from .policy import effective_policy, normalize_project_path, path_matches, read_deployments_config, read_knowledge_config
from .pricing import _validate
from .security import SECRET_PATTERNS, _MACHINE_PATH, redact_text


# Adapters whose preflight requires one context envelope per adapter-bound candidate.
ENVELOPE_ADAPTERS = frozenset({"litellm-loopback"})
DEFAULT_MAX_FILE_BYTES = 262_144
DEFAULT_MAX_TOTAL_BYTES = 524_288
HARD_MAX_BYTES = 1_048_576
MAX_TASK_BYTES = 65_536
MAX_CONTEXT_FILES = 128
# Repository state that never becomes provider context, regardless of project policy.
ALWAYS_WITHHELD = (".git/**", ".embraion/state/**", ".embraion/cache/**", "**/.env", "**/.env.*")
# Credential-like file names, matched case-insensitively against the final path segment.
WITHHELD_NAMES = ("*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*",
                  ".netrc", ".npmrc", ".pypirc")
_LFS_POINTER = b"version https://git-lfs.github.com/spec/"
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_DRIVE = re.compile(r"^[A-Za-z]:")
_FILE_URL = re.compile(r"(?i)\bfile:/")
# These are deliberately path-shaped, rather than every slash-separated phrase:
# a relative repository path or an http(s) URL is ordinary task context.
_POSIX_ABSOLUTE_PATH = re.compile(
    r"(?<![\w./:@-])/(?!/)(?:[\w.~%+-]+/)+[\w.~%+-]+"
)
_DRIVE_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\s\\/:*?\"<>|]+(?:[\\/][^\s\\/:*?\"<>|]+)*"
)
_UNC_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9_\\])\\\\[^\s\\/]+\\[^\s\\/]+(?:\\[^\s\\/]+)*"
)
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/~^@{}-]{0,255}$")


class EnvelopeRefused(RuntimeError):
    """A bounded, non-sensitive refusal; the message never contains file content."""


def _git_environment() -> dict[str, str]:
    """Drop every GIT_* override so repository, object, and replace settings come from the repository."""
    return {key: value for key, value in child_environment().items() if not key.upper().startswith("GIT_")}


def _git(root: Path, *arguments: str, limit: int | None = None) -> bytes:
    command = ["git", "--no-replace-objects", "-c", "core.quotePath=false", "--literal-pathspecs",
               "-C", str(root), *arguments]
    try:
        completed = subprocess.run(command, env=_git_environment(), stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EnvelopeRefused("Git is unavailable for the context envelope.") from error
    if completed.returncode != 0:
        raise EnvelopeRefused("Git could not verify the requested committed content.")
    if limit is not None and len(completed.stdout) > limit:
        raise EnvelopeRefused("Git returned more content than the verified bound.")
    return completed.stdout


def normalize_context_path(value: str) -> str:
    """Return one safe repository-relative path or refuse it."""
    if not isinstance(value, str) or not value or _CONTROL.search(value):
        raise EnvelopeRefused("Context path must be a safe repository-relative path.")
    path = normalize_project_path(value)
    if (path.startswith("/") or path.startswith("\\") or _DRIVE.match(path) or ":" in path
            or path.endswith("/") or any(part in {"", ".", ".."} for part in path.split("/"))):
        raise EnvelopeRefused(f"Context path is outside the repository or not normalized: {path or value}")
    return path


def is_withheld(path: str, patterns: list[str]) -> bool:
    """Case-insensitive policy match: a case variant of a protected path is still protected."""
    name = path.rsplit("/", 1)[-1].lower()
    return (path_matches(path.lower(), [pattern.lower() for pattern in patterns])
            or any(fnmatchcase(name, pattern) for pattern in WITHHELD_NAMES))


def _contains_credential(text: str, credentials: list[str]) -> bool:
    if redact_text(text) != text:
        return True
    if any(pattern.search(text) for category, _, pattern in SECRET_PATTERNS if category != "machine-path"):
        return True
    return any(value and value in text for value in credentials)


def _contains_machine_path(text: str, root: Path) -> bool:
    if any(pattern.search(text) for pattern in (
        _MACHINE_PATH, _FILE_URL, _POSIX_ABSOLUTE_PATH,
        _DRIVE_ABSOLUTE_PATH, _UNC_ABSOLUTE_PATH,
    )):
        return True
    variants = {str(root), root.as_posix(), str(root).replace("/", "\\")}
    lowered = text.lower()
    return any(len(item) > 1 and item.lower() in lowered for item in variants)


def _check_text(text: str, label: str, root: Path, credentials: list[str]) -> None:
    if _contains_credential(text, credentials):
        raise EnvelopeRefused(f"{label} contains credential material.")
    if _contains_machine_path(text, root):
        raise EnvelopeRefused(f"{label} contains a machine-local absolute path or file URL.")


def _file_data_class(path: str, entries: list[dict[str, Any]], default_class: str) -> str:
    classes = [entry["data-class"] for entry in entries
               if path == normalize_project_path(entry["path"]).rstrip("/")
               or path.startswith(normalize_project_path(entry["path"]).rstrip("/") + "/")]
    if not classes:
        classes = [default_class]
    if any(item not in DATA_LEVEL for item in classes):
        raise EnvelopeRefused(f"Context path has an unknown data class: {path}")
    return max(classes, key=lambda item: DATA_LEVEL[item])


def _resolve_commit(root: Path, commit: str) -> str:
    if not isinstance(commit, str) or not _REVISION.fullmatch(commit):
        raise EnvelopeRefused("Context commit must be a plain Git revision.")
    top = _git(root, "rev-parse", "--show-toplevel").decode("utf-8", "replace").strip()
    try:
        same = Path(top).resolve() == root.resolve()
    except OSError:
        same = False
    if not same:
        raise EnvelopeRefused("Context envelopes require the exact repository root.")
    resolved = _git(root, "rev-parse", "--verify", "--quiet", commit + "^{commit}").decode("ascii", "replace").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", resolved):
        raise EnvelopeRefused("Context commit cannot be resolved to one immutable commit.")
    return resolved


def _committed_blob(root: Path, commit: str, path: str, limit: int) -> bytes:
    listing = _git(root, "ls-tree", "-z", "--full-tree", commit, "--", path, limit=65_536)
    rows = [row for row in listing.split(b"\0") if row]
    if len(rows) != 1:
        raise EnvelopeRefused(f"Context path is absent from the commit: {path}")
    match = re.fullmatch(rb"(\d{6}) (\w+) ([0-9a-f]{40}|[0-9a-f]{64})\t(.+)", rows[0], re.DOTALL)
    if not match or match.group(4).decode("utf-8", "replace") != path:
        raise EnvelopeRefused(f"Context path is ambiguous in the commit: {path}")
    if match.group(1) == b"120000":
        raise EnvelopeRefused(f"Context path is a symbolic link: {path}")
    if match.group(1) not in {b"100644", b"100755"} or match.group(2) != b"blob":
        raise EnvelopeRefused(f"Context path is not a regular committed file: {path}")
    blob = match.group(3).decode("ascii")
    size_text = _git(root, "cat-file", "-s", blob, limit=64).decode("ascii", "replace").strip()
    if not size_text.isdigit() or int(size_text) > limit:
        raise EnvelopeRefused(f"Context file exceeds the per-file or remaining total byte bound: {path}")
    content = _git(root, "cat-file", "blob", blob, limit=limit)
    if len(content) != int(size_text):
        raise EnvelopeRefused(f"Context file size cannot be verified: {path}")
    return content


def adapter_bound_candidates(request: dict[str, Any], registry: dict[str, Any],
                             bindings: dict[str, Any]) -> list[str]:
    """Candidates on the request host whose binding adapter consumes context envelopes."""
    return [item["deployment"] for item in request["candidates"]
            if (registry.get(item["deployment"]) or {}).get("host") == request["host"]
            and (bindings.get(item["deployment"]) or {}).get("adapter") in ENVELOPE_ADAPTERS]


def build_payload(request: dict[str, Any], *, paths: list[str], task: str, project: Path | None = None,
                  commit: str = "HEAD", max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
                  max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
                  max_output_tokens: int | None = None) -> dict[str, Any]:
    """Build `payload.inputsByDeployment` for every adapter-bound candidate of a request."""
    from .adapters.litellm_execution import _BODY_LIMIT, _valid_envelope, _valid_input
    from .execution import _eligible, read_execution_config

    _validate(request, "execution-request.schema.json")
    if not (1 <= max_file_bytes <= HARD_MAX_BYTES and 1 <= max_total_bytes <= HARD_MAX_BYTES):
        raise EnvelopeRefused(f"Context byte bounds must be between 1 and {HARD_MAX_BYTES}.")
    if not isinstance(task, str) or not task.strip() or len(task.encode("utf-8")) > MAX_TASK_BYTES:
        raise EnvelopeRefused(f"Task text must be nonempty and at most {MAX_TASK_BYTES} bytes.")
    root = project_root(project)
    registry = read_deployments_config(root)["deployments"]
    bindings = read_execution_config(root)["bindings"]
    bound = adapter_bound_candidates(request, registry, bindings)
    if not bound:
        raise EnvelopeRefused("The request has no candidate bound to an envelope adapter on its host.")
    credentials: list[str] = []
    for identifier in bound:
        binding = bindings[identifier]
        if not isinstance(binding.get("contextBoundary"), str) or not binding["contextBoundary"]:
            raise EnvelopeRefused(f"Binding has no approved context boundary: {identifier}")
        if not _eligible(request, registry[identifier], binding):
            raise EnvelopeRefused(f"Candidate violates the request role/data/source/trust/access ceilings: {identifier}")
        limit = binding.get("maxContextBytes")
        if isinstance(limit, int):
            max_total_bytes = min(max_total_bytes, limit)
        reference = binding.get("credentialRef")
        if isinstance(reference, str) and reference.startswith("env:") and os.environ.get(reference[4:]):
            credentials.append(os.environ[reference[4:]])

    policy = effective_policy(root)
    default_class = str(policy["privacy"].get("default-class"))
    entries = _knowledge_entries(read_knowledge_config(root), default_class)
    withheld = [*ALWAYS_WITHHELD, *[str(item) for item in policy["sources"].get("protected") or []]]
    _check_text(task, "Task text", root, credentials)
    for label, value in (("Work item ID", request["workItemId"]), ("Task ID", request.get("taskId")),
                         *(("Source ID", item) for item in request["sourceIds"])):
        if isinstance(value, str):
            _check_text(value, label, root, credentials)
    normalized = sorted(dict.fromkeys(normalize_context_path(item) for item in paths))
    if len(normalized) > MAX_CONTEXT_FILES:
        raise EnvelopeRefused(f"Context exceeds {MAX_CONTEXT_FILES} files.")
    request_level = DATA_LEVEL[request["dataClass"]]
    for path in normalized:
        if is_withheld(path, withheld):
            raise EnvelopeRefused(f"Context path is protected or withheld by policy: {path}")
        if DATA_LEVEL[_file_data_class(path, entries, default_class)] > request_level:
            raise EnvelopeRefused(f"Context path is more sensitive than the request data class: {path}")

    resolved = _resolve_commit(root, commit)
    context: list[dict[str, Any]] = []
    total = 0
    for path in normalized:
        content = _committed_blob(root, resolved, path, min(max_file_bytes, max_total_bytes - total))
        if content.startswith(_LFS_POINTER):
            raise EnvelopeRefused(f"Context file is a Git LFS pointer, not content: {path}")
        if b"\0" in content:
            raise EnvelopeRefused(f"Context file is binary: {path}")
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise EnvelopeRefused(f"Context file is not UTF-8 text: {path}") from error
        _check_text(text, f"Context file {path}", root, credentials)
        total += len(content)
        if total > max_total_bytes:
            raise EnvelopeRefused("Context exceeds the total byte bound.")
        context.append({"path": path, "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content), "content": text})

    digest = hashlib.sha256(json.dumps([[item["path"], item["sha256"]] for item in context],
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    inputs: dict[str, Any] = {}
    for identifier in bound:
        binding, deployment = bindings[identifier], registry[identifier]
        envelope = {
            "schemaVersion": 1, "boundary": binding["contextBoundary"],
            "workItem": {"workItemId": request["workItemId"], "deploymentId": identifier,
                         "model": deployment["model"], "role": request["role"],
                         "sourceIds": list(request["sourceIds"]), "access": request["access"],
                         "dataClass": (binding.get("dataClassAliases") or {}).get(request["dataClass"], request["dataClass"])},
            "task": {"responsibility": task},
            "provenance": {"commit": resolved, "contextDigest": digest},
            "context": context,
        }
        value = [{"role": "user", "content": [{"type": "input_text",
                                               "text": json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))}]}]
        # The adapter re-encodes the input inside its bounded request body.
        if (not _valid_input(value) or not _valid_envelope(value, request, identifier, deployment, binding)
                or len(json.dumps(value, separators=(",", ":")).encode("utf-8")) + 4096 > _BODY_LIMIT):
            raise EnvelopeRefused(f"Context envelope exceeds the adapter transport bound or contract: {identifier}")
        inputs[identifier] = value
    payload: dict[str, Any] = {"inputsByDeployment": inputs}
    if max_output_tokens is not None:
        payload["maxOutputTokens"] = max_output_tokens
    return payload


def with_payload(request: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Attach a built payload without overwriting caller-supplied input."""
    existing = request.get("payload")
    if existing is not None and (not isinstance(existing, dict) or set(existing) - {"maxOutputTokens"}):
        raise EnvelopeRefused("The request already supplies payload input; refusing to replace it.")
    merged = dict(payload)
    if isinstance(existing, dict) and "maxOutputTokens" in existing and "maxOutputTokens" not in merged:
        merged["maxOutputTokens"] = existing["maxOutputTokens"]
    return {**request, "payload": merged}
