"""Run declarative skill cases against isolated native Codex sessions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path, PureWindowsPath
from typing import Any

from jsonschema import Draft202012Validator

from .common import framework_root, write_json

MAX_SOURCE_BYTES = 2_000_000
MAX_SOURCE_FILES = 200
MAX_EVENT_BYTES = 2_000_000
VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
READ_COMMAND = re.compile(r"(?:^|\s)(?:cat|sed|head|tail|rg|grep|less|more|type)\s")


def _safe_relative(value: str) -> Path:
    if (not isinstance(value, str) or not value or "\\" in value or "\0" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or PureWindowsPath(value).drive or PureWindowsPath(value).root):
        raise ValueError("suite contains an unsafe relative path")
    return Path(value)


def _reject_source_ancestors(source: Path, trusted_base: Path) -> None:
    """Reject links in the path below a trusted root before resolving it."""
    try:
        relative = source.relative_to(trusted_base)
    except ValueError as error:
        raise ValueError("source path escapes trusted root") from error
    current = trusted_base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("fixture or skill source has a symlink ancestor")


def _source_files(source: Path) -> list[tuple[Path, Path]]:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("fixture or skill source must be a regular directory")
    files: list[tuple[Path, Path]] = []
    total = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("fixture or skill source contains a symlink")
        if path.is_file():
            files.append((path.relative_to(source), path))
            total += path.stat().st_size
        elif not path.is_dir():
            raise ValueError("fixture or skill source contains a special file")
        if len(files) > MAX_SOURCE_FILES or total > MAX_SOURCE_BYTES:
            raise ValueError("fixture or skill source exceeds size limits")
    return files


def _digest(source: Path) -> str:
    digest = hashlib.sha256()
    for relative, path in _source_files(source):
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _copy_source(source: Path, destination: Path) -> None:
    files = _source_files(source)
    destination.mkdir(parents=True, exist_ok=False)
    for relative, path in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target, follow_symlinks=False)


def _snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative, path in _source_files(root):
        result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _field(value: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _grade(root: Path, before: dict[str, str], checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    after = _snapshot(root)
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    results = []
    for index, check in enumerate(checks):
        relative = _safe_relative(check["path"]).as_posix() if "path" in check else None
        kind = check["type"]
        target = root / relative if relative else None
        if target is not None and target.is_symlink():
            passed = False
        elif kind == "file-exists":
            passed = bool(target and target.is_file())
        elif kind == "file-absent":
            passed = bool(target and not target.exists())
        elif kind == "file-contains":
            try:
                passed = bool(target and target.is_file() and check["text"] in target.read_text(encoding="utf-8"))
            except UnicodeError:
                passed = False
        elif kind == "json-field-equals":
            try:
                passed = bool(target and target.is_file() and _field(json.loads(target.read_text(encoding="utf-8")), check["field"]) == check["value"])
            except (ValueError, UnicodeError):
                passed = False
        elif kind == "unchanged-path":
            passed = relative not in changed
        elif kind == "changed-paths-within":
            allowed = tuple(_safe_relative(item).as_posix() for item in check["paths"])
            passed = bool(changed) and all(any(path == prefix or path.startswith(prefix + "/") for prefix in allowed) for path in changed)
        else:
            raise ValueError("unsupported check type")
        results.append({"index": index, "type": kind, "passed": passed})
    return results


def _events(path: Path, skill_ids: list[str]) -> dict[str, Any]:
    completed = False
    failed = False
    tool_calls = 0
    tokens: dict[str, int] = {}
    reads: set[str] = set()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError("invalid host event")
            kind = event["type"]
            completed |= kind == "turn.completed"
            failed |= kind == "turn.failed"
            if kind == "turn.completed" and isinstance(event.get("usage"), dict):
                for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
                    value = event["usage"].get(key)
                    if type(value) is int and value >= 0:
                        tokens[key] = tokens.get(key, 0) + value
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") in {"command_execution", "mcp_tool_call", "web_search"}:
                if kind == "item.started":
                    tool_calls += 1
                command = item.get("command")
                if kind == "item.completed" and item.get("type") == "command_execution" and item.get("exit_code") == 0 and isinstance(command, str) and READ_COMMAND.search(command):
                    for skill_id in skill_ids:
                        if f".agents/skills/{skill_id}/SKILL.md" in command:
                            reads.add(skill_id)
    return {"completed": completed, "failed": failed, "tool-calls": tool_calls, "tokens": tokens, "observed-reads": sorted(reads)}


def _terminate_host(process: subprocess.Popen[bytes], *, windows: bool) -> None:
    if windows:
        process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _invoke_codex(binary: str, root: Path, prompt: str, model: str | None, effort: str | None, timeout: int, skill_ids: list[str], scratch: Path) -> dict[str, Any]:
    argv = [binary, "exec", "--ignore-user-config", "--ephemeral", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", "--cd", str(root), "--output-last-message", str(scratch / "last-message.txt")]
    if model:
        argv += ["--model", model]
    if effort:
        argv += ["--config", f'model_reasoning_effort="{effort}"']
    argv.append("-")
    start = time.monotonic()
    stdout = scratch / "events.jsonl"
    stderr = scratch / "stderr.txt"
    prompt_path = scratch / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    with stdout.open("wb") as out, stderr.open("wb") as err, prompt_path.open("rb") as prompt_stream:
        try:
            process = subprocess.Popen(argv, cwd=root, stdin=prompt_stream, stdout=out, stderr=err, start_new_session=os.name != "nt")
        except OSError:
            return {"status": "host-unavailable", "duration-seconds": 0.0}
        status = "completed"
        while process.poll() is None:
            if time.monotonic() - start > timeout:
                status = "timeout"
                _terminate_host(process, windows=os.name == "nt")
                break
            if stdout.stat().st_size > MAX_EVENT_BYTES or stderr.stat().st_size > MAX_EVENT_BYTES:
                status = "output-limit"
                _terminate_host(process, windows=os.name == "nt")
                break
            time.sleep(0.05)
        process.wait()
    result: dict[str, Any] = {"status": status, "duration-seconds": round(time.monotonic() - start, 3), "exit-code": process.returncode}
    if status != "completed":
        return result
    if stdout.stat().st_size > MAX_EVENT_BYTES or stderr.stat().st_size > MAX_EVENT_BYTES:
        result["status"] = "output-limit"
        return result
    try:
        observations = _events(stdout, skill_ids)
    except (ValueError, UnicodeError):
        result["status"] = "invalid-host-events"
        return result
    result.update(observations)
    if process.returncode != 0 or observations["failed"] or not observations["completed"]:
        result["status"] = "host-failed"
    return result


def _load_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((framework_root() / "schemas/skill-eval.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(suite)
    for case in suite["cases"]:
        _safe_relative(case["fixture"])
        for check in case["checks"]:
            if "path" in check:
                _safe_relative(check["path"])
            for item in check.get("paths", []):
                _safe_relative(item)
    ids = [case["id"] for case in suite["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")
    skills = [skill["id"] for skill in suite["skills"]]
    if len(skills) != len(set(skills)):
        raise ValueError("duplicate skill id")
    return suite


def run_suite(suite: Path, *, host: str, model: str | None, effort: str | None, attempts: int, output: Path, timeout_seconds: int = 180, codex_binary: str = "codex") -> dict[str, Any]:
    """Run baseline and candidate against clean copies of each fixture.

    A previous variant is included when every suite skill supplies `previous`.
    The report contains only digests, check outcomes, and bounded metrics.
    """
    if host != "codex":
        raise ValueError("live skill eval currently supports host=codex only")
    if attempts < 1 or attempts > 20 or timeout_seconds < 1 or timeout_seconds > 3600:
        raise ValueError("attempts or timeout outside allowed range")
    if effort is not None and effort not in VALID_EFFORTS:
        raise ValueError("unsupported reasoning effort")
    if model is not None and (not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", model)):
        raise ValueError("invalid model name")
    suite = suite.resolve(strict=True)
    data = _load_suite(suite)
    source_root = framework_root().resolve()
    skills: list[dict[str, Any]] = []
    for skill in data["skills"]:
        item = {"id": skill["id"]}
        for version in ("candidate", "previous"):
            if version in skill:
                relative = _safe_relative(skill[version])
                source = source_root / relative
                _reject_source_ancestors(source, source_root)
                if not source.resolve().is_relative_to(source_root) or not (source / "SKILL.md").is_file():
                    raise ValueError("skill path must be a framework skill directory")
                item[version] = {"path": source, "digest": _digest(source)}
        skills.append(item)
    previous = all("previous" in skill for skill in skills)
    if any("previous" in skill for skill in skills) and not previous:
        raise ValueError("previous skill must be supplied for every skill")
    variants = ["baseline", "candidate"] + (["previous"] if previous else [])
    records: list[dict[str, Any]] = []
    for case in data["cases"]:
        fixture = suite.parent / _safe_relative(case["fixture"])
        _reject_source_ancestors(fixture, suite.parent)
        if not fixture.resolve().is_relative_to(suite.parent):
            raise ValueError("fixture path escapes suite directory")
        fixture_digest = _digest(fixture)
        case_digest = hashlib.sha256(json.dumps({"case": case, "fixture": fixture_digest}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        for attempt in range(1, attempts + 1):
            for variant in variants:
                with tempfile.TemporaryDirectory(prefix="embraion-skill-eval-") as temp:
                    scratch = Path(temp)
                    project = scratch / "project"
                    _copy_source(fixture, project)
                    if variant != "baseline":
                        for skill in skills:
                            destination = project / ".agents" / "skills" / skill["id"]
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            _copy_source(skill[variant]["path"], destination)
                    before = _snapshot(project)
                    host_result = _invoke_codex(codex_binary, project, case["prompt"], model, effort, timeout_seconds, [skill["id"] for skill in skills], scratch)
                    try:
                        checks = _grade(project, before, case["checks"])
                    except (ValueError, OSError):
                        host_result["status"] = "grading-error"
                        checks = [{"index": index, "type": check["type"], "passed": False} for index, check in enumerate(case["checks"])]
                    observed = set(host_result.get("observed-reads", []))
                    record = {"case": case["id"], "case-digest": case_digest, "fixture-digest": fixture_digest, "polarity": case["polarity"], "attempt": attempt, "variant": variant, "host": host_result, "checks": checks, "behavior-passed": host_result["status"] == "completed" and all(check["passed"] for check in checks), "trigger-evidence": {skill["id"]: ("read-observed" if skill["id"] in observed else "unverified") for skill in skills}}
                    records.append(record)
        if _digest(fixture) != fixture_digest:
            raise RuntimeError("fixture source changed during evaluation")
    for skill in skills:
        for version in ("candidate", "previous"):
            if version in skill and _digest(skill[version]["path"]) != skill[version]["digest"]:
                raise RuntimeError("skill source changed during evaluation")
    identity = {skill["id"]: {version: skill[version]["digest"] for version in ("candidate", "previous") if version in skill} for skill in skills}
    summary = {variant: {"total": sum(record["variant"] == variant for record in records), "behavior-passed": sum(record["variant"] == variant and record["behavior-passed"] for record in records)} for variant in variants}
    pairs: list[dict[str, Any]] = []
    for case in data["cases"]:
        for attempt in range(1, attempts + 1):
            group = {record["variant"]: record for record in records if record["case"] == case["id"] and record["attempt"] == attempt}
            comparisons = {}
            for reference in ("baseline", "previous"):
                if reference not in group:
                    continue
                candidate = group["candidate"]
                other = group[reference]
                if candidate["host"]["status"] != "completed" or other["host"]["status"] != "completed":
                    outcome = "unavailable"
                elif candidate["behavior-passed"] and not other["behavior-passed"]:
                    outcome = "improved"
                elif other["behavior-passed"] and not candidate["behavior-passed"]:
                    outcome = "regressed"
                else:
                    outcome = "tied-pass" if candidate["behavior-passed"] else "tied-fail"
                comparisons[reference] = outcome
            pairs.append({"case": case["id"], "attempt": attempt, "candidate-vs": comparisons})
    pair_summary = {reference: {outcome: sum(pair["candidate-vs"].get(reference) == outcome for pair in pairs) for outcome in ("improved", "regressed", "tied-pass", "tied-fail", "unavailable")} for reference in ("baseline", "previous") if reference in variants}
    report = {"schema-version": 1, "evidence-kind": "live-codex-subprocess", "suite": data["id"], "suite-digest": hashlib.sha256(suite.read_bytes()).hexdigest(), "host": host, "model": model, "effort": effort, "attempts": attempts, "skill-identities": identity, "summary": summary, "pair-summary": pair_summary, "pairs": pairs, "runs": records}
    write_json(output, report)
    return report
