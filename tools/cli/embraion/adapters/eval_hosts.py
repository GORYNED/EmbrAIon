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
from typing import Any

from ..skill_evals import VALID_EFFORTS, _invoke_codex


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
        policy = {"sandbox": "workspace-write", "user-config": "ignored", "session": "ephemeral"}
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
                effort: str | None, timeout: int, skills: list[str], scratch: Path) -> dict[str, Any]:
    if model is not None and not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", model):
        raise ValueError("invalid native model selector")
    if effort is not None and effort not in VALID_EFFORTS:
        raise ValueError("unsupported native effort")
    if host == "codex":
        windows_sandbox = _windows_sandbox()
        if os.name == "nt" and windows_sandbox is None:
            return {"status": "native-sandbox-unverified", "duration-seconds": None}
        # This pilot resolves Worker; the main config represents Lead and must
        # never silently supply a different role's instructions.
        config = project / ".codex/agents/worker.toml"
        try:
            profile = tomllib.loads(config.read_text(encoding="utf-8"))
            instructions = profile.get("developer_instructions")
        except (OSError, ValueError):
            return {"status": "native-config-unverified", "duration-seconds": None}
        if not isinstance(instructions, str) or not instructions or len(instructions) > 64000:
            return {"status": "native-config-unverified", "duration-seconds": None}
        if profile.get("name") != "worker" or profile.get("sandbox_mode") != "workspace-write":
            return {"status": "native-config-unverified", "duration-seconds": None}
        # Stable project trust must not imply retained answers or events from a
        # previous attempt. Raw observations have their own short lifetime.
        from ..experiment_evals import _scratch_root
        with tempfile.TemporaryDirectory(prefix="native-observation-", dir=_scratch_root()) as observation:
            result = _invoke_codex(binary, project, prompt, model, effort, timeout, skills, Path(observation),
                                   developer_instructions=instructions, windows_sandbox=windows_sandbox,
                                   trusted_workspace=True)
        result["configuration-evidence"] = "explicit-native-developer-instructions-argument"
        result["role-evidence"] = "worker-profile-explicit-argument"
        return result
    # Missing native containment/event translation is not host-default or a pass.
    return {"status": "native-eval-backend-unavailable", "duration-seconds": None,
            "coverage": "projection checks supported; live behavior unverified"}


def preflight_host(host: str, binary: str, snapshot: Path, model: str | None,
                   effort: str | None, timeout: int, *, workspace: Path | None = None) -> dict[str, Any]:
    """Prove tool read/write on harmless data before scoring Core behavior.

    Successful model completion alone never proves operational tools. This is
    infrastructure evidence, not a security isolation or Core quality claim.
    """
    result: dict[str, Any] = {"status": "inconclusive", "kind": "fixture-read-write",
                              "coverage": "nonce read and local file write only; external actions and containment against all channels unverified"}
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
            profile = project / ".codex/agents/worker.toml"
            profile.parent.mkdir(parents=True)
            shutil.copyfile(snapshot / ".codex/agents/worker.toml", profile)
            nonce = secrets.token_hex(16)
            (project / "marker.txt").write_text(nonce, encoding="utf-8")
            observation = invoke_host(host, binary, project,
                "Read marker.txt using available tools and write its exact contents to result.txt. "
                "This is a bounded infrastructure probe. Change no other files. Report tool failures accurately.",
                model, effort, min(timeout, 120), [], scratch)
            output = project / "result.txt"
            valid = (observation.get("status") == "completed" and output.is_file() and not output.is_symlink()
                     and output.stat().st_size <= 100 and output.read_text(encoding="utf-8").strip() == nonce)
            result.update({"status": "pass" if valid else "inconclusive", "observation": observation,
                           "read-write-verified": valid})
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
