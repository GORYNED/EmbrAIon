"""Native host translation; experiment contracts and graders remain neutral."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import tomllib
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

from ..skill_evals import VALID_EFFORTS, _invoke_codex

NATIVE_ROLES = frozenset({"lead", "worker", "reviewer", "architect", "analyst", "validator", "researcher", "steward"})
NATIVE_ACCESS = frozenset({"read-only", "workspace-write"})
READ_ONLY_ROLES = frozenset({"reviewer", "architect", "analyst", "researcher"})


def _model_bearing(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in {"model", "model_reasoning_effort", "model_provider"} or _model_bearing(item)
                   for key, item in value.items())
    return isinstance(value, list) and any(_model_bearing(item) for item in value)


def _native_instructions(project: Path, role: str, access: str) -> str | None:
    """Load a bounded, model-neutral Core projection without following profile links."""
    config = project / (".codex/config.toml" if role == "lead" else f".codex/agents/{role}.toml")
    if any(path.is_symlink() for path in (project / ".codex", config.parent, config)):
        return None
    try:
        if not config.is_file() or config.stat().st_size > 128_000:
            return None
        profile = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if _model_bearing(profile):
        return None
    instructions = profile.get("developer_instructions")
    if not isinstance(instructions, str) or not instructions or len(instructions) > 64_000:
        return None
    if role == "lead":
        ceiling = profile.get("sandbox_mode", "workspace-write")
    else:
        if profile.get("name") != role:
            return None
        ceiling = profile.get("sandbox_mode")
    if (ceiling not in NATIVE_ACCESS or (ceiling == "read-only" and access == "workspace-write")
            or (role in READ_ONLY_ROLES and (ceiling != "read-only" or access != "read-only"))):
        return None
    return instructions


def _observer_outcome(observer: Callable[[Path, dict[str, Any]], dict[str, Any]],
                      raw_directory: Path, native_result: dict[str, Any]) -> dict[str, Any]:
    try:
        outcome = observer(raw_directory, native_result)
        if (not isinstance(outcome, dict) or outcome.get("status") not in {"pass", "fail", "inconclusive"}
                or set(outcome) - {"status", "observer-id", "observation-digest", "params-digest"}
                or any(not isinstance(value, str) or len(value) > 128 for value in outcome.values())
                or ("observer-id" in outcome and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", outcome["observer-id"]))
                or any(not re.fullmatch(r"[a-f0-9]{64}", outcome[key])
                       for key in ("observation-digest", "params-digest") if key in outcome)):
            raise ValueError("invalid observer outcome")
        return outcome
    except Exception:
        return {"status": "inconclusive", "reason": "observer-unavailable"}


def binding_available(host: str, route: dict[str, Any]) -> bool:
    """Native applicability belongs to adapters, never to Core or graders."""
    return host == "codex" and not route.get("provider") and not route.get("options")


def _windows_sandbox() -> str | None:
    if os.name != "nt":
        return None
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    path = home / "config.toml"
    try:
        if not path.is_file() or path.stat().st_size > 256_000:
            return None
        value = tomllib.loads(path.read_text(encoding="utf-8")).get("windows", {}).get("sandbox")
        return value if value in {"elevated", "unelevated"} else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def describe_context(host: str) -> dict[str, Any]:
    if host == "codex":
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        names = ("AGENTS.md", "config.toml")
        policy = {"sandbox": "explicit-per-invocation-access", "user-config": "ignored", "session": "ephemeral"}
        policy["project-trust"] = "explicit-stable-fixture-in-private-eval-profile"
        if os.name == "nt":
            policy["windows-sandbox-explicit-argument"] = _windows_sandbox() or "unverified"
    elif host == "claude-code":
        home, names = Path.home() / ".claude", ("CLAUDE.md", "settings.json")
        policy = {"containment": "unverified", "session": "unverified"}
    else:
        return {"configuration": "unverified", "containment": "unverified"}
    files = {}
    for name in names:
        path = home / name
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    rules = home / "rules"
    if rules.is_dir():
        from ..experiment_evals import _files, identity
        files["rules"] = identity(_files(rules))
    instruction_files = {}
    for label, directory in (("host-skills", home / "skills"), ("shared-skills", Path.home() / ".agents/skills"),
                             ("plugin-instructions", home / "plugins/cache")):
        inventory = {}
        if directory.is_dir():
            for path in sorted(directory.rglob("SKILL.md")):
                if path.is_symlink() or path.stat().st_size > 64_000 or len(inventory) >= 1500:
                    inventory = {}
                    instruction_files[label] = "unverified"
                    break
                inventory[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if label not in instruction_files:
            from ..experiment_evals import identity
            instruction_files[label] = identity(inventory)
    return {"files": files, "instruction-inventory": instruction_files, "execution": policy,
            "plugin-runtime-and-external-integrations": "unverified"}


def describe_host(binary: str) -> dict[str, Any]:
    resolved = shutil.which(binary)
    if not resolved:
        return {"availability": "unavailable", "version": "unverified", "binary-digest": None}
    try:
        result = subprocess.run([resolved, "--version"], capture_output=True, timeout=10, text=True)
        # Do not persist arbitrary executable output or local absolute paths.
        match = re.search(r"(?:codex-cli|Claude Code|claude|copilot)?\s*(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)", result.stdout)
        return {"availability": "available" if result.returncode == 0 else "unavailable",
                "version": match.group(1) if match else "unverified",
                "binary-digest": hashlib.sha256(Path(resolved).read_bytes()).hexdigest()}
    except (OSError, subprocess.TimeoutExpired):
        return {"availability": "unavailable", "version": "unverified", "binary-digest": None}


def invoke_host(host: str, binary: str, project: Path, prompt: str, model: str | None,
                effort: str | None, timeout: int, skills: list[str], scratch: Path, *,
                role: str = "worker", access: str = "workspace-write",
                observer: Callable[[Path, dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    if role not in NATIVE_ROLES:
        raise ValueError("unsupported native role")
    if access not in NATIVE_ACCESS:
        raise ValueError("unsupported native access")
    if model is not None and not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", model):
        raise ValueError("invalid native model selector")
    if effort is not None and effort not in VALID_EFFORTS:
        raise ValueError("unsupported native effort")
    if host == "codex":
        windows_sandbox = _windows_sandbox()
        if os.name == "nt" and windows_sandbox is None:
            return {"status": "native-sandbox-unverified", "duration-seconds": None}
        instructions = _native_instructions(project, role, access)
        if instructions is None:
            return {"status": "native-config-unverified", "duration-seconds": None}
        # Stable project trust must not imply retained answers or events from a
        # previous attempt. Raw observations have their own short lifetime.
        from ..experiment_evals import _observation_root
        with tempfile.TemporaryDirectory(prefix="native-observation-", dir=_observation_root()) as observation:
            result = _invoke_codex(binary, project, prompt, model, effort, timeout, skills, Path(observation),
                                   developer_instructions=instructions, windows_sandbox=windows_sandbox,
                                   trusted_workspace=True, sandbox=access)
            if result.get("status") != "completed":
                from .eval_observations import codex_failure_metadata
                result["native-failure"] = codex_failure_metadata(Path(observation))
            if observer is not None:
                result["observer"] = _observer_outcome(observer, Path(observation), result)
        result["configuration-evidence"] = "explicit-native-developer-instructions-argument"
        result["role-evidence"] = f"{role}-profile-explicit-argument"
        result["access-evidence"] = access
        return result
    # Missing native containment/event translation is not host-default or a pass.
    return {"status": "native-eval-backend-unavailable", "duration-seconds": None,
            "coverage": "projection checks supported; live behavior unverified"}


def preflight_host(host: str, binary: str, snapshot: Path, model: str | None,
                   effort: str | None, timeout: int, *, workspace: Path | None = None,
                   role: str = "worker", access: str = "workspace-write") -> dict[str, Any]:
    """Prove bounded tool access on harmless data before scoring Core behavior.

    Successful model completion alone never proves operational tools. This is
    infrastructure evidence, not a security isolation or Core quality claim.
    """
    if role not in NATIVE_ROLES or access not in NATIVE_ACCESS:
        raise ValueError("unsupported preflight role or access")
    read_only = access == "read-only"
    result: dict[str, Any] = {"status": "inconclusive",
                              "kind": "fixture-read" if read_only else "fixture-read-write",
                              "coverage": ("nonce read through native answer only; file isolation and external actions unverified"
                                           if read_only else
                                           "nonce read and local file write only; external actions and containment against all channels unverified")}
    if host != "codex":
        return result
    try:
        from ..experiment_evals import _scratch_root
        home_text = os.environ.get("CODEX_HOME")
        home = Path(home_text) if home_text else None
        if (home is None or home.is_symlink() or home.resolve() == (Path.home() / ".codex").resolve()
                or not (home / "embraion-eval-profile.json").is_file()
                or (home / "embraion-eval-profile.json").is_symlink()
                or (home / "embraion-eval-profile.json").stat().st_size > 1024
                or (home / "config.toml").is_symlink() or not (home / "config.toml").is_file()
                or (home / "config.toml").stat().st_size > 256_000):
            result["reason"] = "private-eval-profile-required"
            return result
        marker = json.loads((home / "embraion-eval-profile.json").read_text(encoding="utf-8"))
        if marker != {"schema-version": 1, "purpose": "embraion-native-eval"}:
            result["reason"] = "private-eval-profile-required"
            return result
        before = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
        context = (nullcontext(workspace.parent) if workspace is not None else
                   tempfile.TemporaryDirectory(prefix="embraion-preflight-", dir=_scratch_root()))
        with context as temporary:
            scratch = Path(temporary)
            project = workspace if workspace is not None else scratch / "project"
            if home.resolve().is_relative_to(project.resolve()) or project.is_symlink() or project.exists():
                raise ValueError("unsafe preflight workspace")
            if _native_instructions(snapshot, role, access) is None:
                result["reason"] = "native-role-profile-unverified"
                return result
            relative_profile = ".codex/config.toml" if role == "lead" else f".codex/agents/{role}.toml"
            profile = project / relative_profile
            profile.parent.mkdir(parents=True)
            profile.write_bytes((snapshot / relative_profile).read_bytes())
            nonce = secrets.token_hex(16)
            (project / "marker.txt").write_text(nonce, encoding="utf-8")
            if read_only:
                def answer_observer(raw: Path, native: dict[str, Any]) -> dict[str, str]:
                    answer = raw / "last-message.txt"
                    valid_answer = (native.get("status") == "completed" and answer.is_file()
                                    and not answer.is_symlink() and answer.stat().st_size <= 100
                                    and answer.read_text(encoding="utf-8").strip() == nonce)
                    return {"status": "pass" if valid_answer else "inconclusive"}

                observation = invoke_host(host, binary, project,
                    "Read marker.txt using available tools and reply with its exact contents only. "
                    "Do not write any files. This is a bounded infrastructure probe.",
                    model, effort, min(timeout, 120), [], scratch,
                    role=role, access=access, observer=answer_observer)
                valid = (observation.get("status") == "completed"
                         and observation.get("observer", {}).get("status") == "pass")
            else:
                observation = invoke_host(host, binary, project,
                    "Read marker.txt using available tools and write its exact contents to result.txt. "
                    "This is a bounded infrastructure probe. Change no other files. Report tool failures accurately.",
                    model, effort, min(timeout, 120), [], scratch, role=role, access=access)
                output = project / "result.txt"
                valid = (observation.get("status") == "completed" and output.is_file() and not output.is_symlink()
                         and output.stat().st_size <= 100 and output.read_text(encoding="utf-8").strip() == nonce)
            result.update({"status": "pass" if valid else "inconclusive", "observation": observation,
                           "read-verified" if read_only else "read-write-verified": valid})
            expected = json.loads(json.dumps(before))
            expected.setdefault("projects", {}).setdefault(str(project.resolve()), {})["trust_level"] = "trusted"
            if (home / "config.toml").is_symlink() or not (home / "config.toml").is_file() or (home / "config.toml").stat().st_size > 256_000:
                raise ValueError("unsafe profile configuration after preflight")
            after = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
            prepared = not (home / "config.toml").is_symlink() and after in (before, expected)
            result["configuration-preparation"] = {"status": "pass" if prepared else "inconclusive",
                "coverage": "only the exact stable fixture trust entry may be registered before environment freeze"}
            if not prepared:
                result["status"] = "inconclusive"
                result["reason"] = "unexpected-eval-profile-configuration-change"
    except (OSError, ValueError, RuntimeError, TypeError):
        result["reason"] = "native-preflight-unavailable"
    return result
