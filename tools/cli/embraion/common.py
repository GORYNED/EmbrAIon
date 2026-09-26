from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".toml", ".txt", ".py", ".ps1", ".sh"}
SKIP_PARTS = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", "Library"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def framework_root(start: Path | None = None) -> Path:
    env = os.getenv("EMBRAION_HOME")
    if env:
        candidate = Path(env).expanduser().resolve()
        if (candidate / "framework.yaml").is_file():
            return candidate

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "framework.yaml").is_file() and (candidate / "core" / "catalog.yaml").is_file():
            return candidate

    source_candidate = Path(__file__).resolve().parents[3]
    if (
        (source_candidate / "framework.yaml").is_file()
        and (source_candidate / "core" / "catalog.yaml").is_file()
    ):
        return source_candidate

    packaged_candidates = [
        Path(sysconfig.get_path("data")) / "share" / "embraion",
        Path(sys.prefix) / "share" / "embraion",
    ]
    for candidate in packaged_candidates:
        if (
            (candidate / "framework.yaml").is_file()
            and (candidate / "core" / "catalog.yaml").is_file()
        ):
            return candidate.resolve()

    raise RuntimeError(
        "Could not locate the EmbrAIon framework data. Reinstall EmbrAIon or set EMBRAION_HOME."
    )


def find_project_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()

    try:
        result = run(["git", "-C", str(current), "rev-parse", "--show-toplevel"])
        return Path(result.stdout.strip()).resolve()
    except Exception:
        pass

    for candidate in (current, *current.parents):
        if (candidate / ".embraion" / "project.yaml").is_file():
            return candidate

    return None


def project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    return find_project_root(current) or current


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def framework_version(root: Path) -> str:
    data = read_yaml(root / "framework.yaml") or {}
    return str(data.get("version", "0.1.0-dev"))


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if relative.parts[:2] == (".embraion", "state"):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {".gitignore", ".editorconfig"}:
            yield path


def state_root(project: Path) -> Path:
    path = project / ".embraion" / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path
