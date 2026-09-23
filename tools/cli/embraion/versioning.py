from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

CANONICAL_REPOSITORY = "GORYNED/EmbrAIon"
PROJECT_MANIFEST = Path(".embraion") / "project.yaml"

CACHE_HOME_ENV = "EMBRAION_CACHE_HOME"
DISABLE_RESOLUTION_ENV = "EMBRAION_DISABLE_VERSION_RESOLUTION"
RESOLUTION_GUARD_ENV = "EMBRAION_VERSION_RESOLVED"
RESOLVED_VERSION_ENV = "EMBRAION_RESOLVED_VERSION"
RESOLVED_PROJECT_ENV = "EMBRAION_RESOLVED_PROJECT"

_BYPASS_COMMANDS = {"init", "update", "status", "cache"}
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+!-]{0,127}$")
_LEGACY_DEV_PATTERN = re.compile(r"^(\d+\.\d+\.\d+)-dev$")

_LOCK_TIMEOUT_SECONDS = 60.0
_STALE_LOCK_SECONDS = 600.0


@dataclass(frozen=True)
class CachedRuntime:
    python: Path
    framework_root: Path


def find_project_manifest(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        manifest = candidate / PROJECT_MANIFEST
        if manifest.is_file():
            return manifest

    return None


def read_project_pin(manifest: Path) -> str:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    framework = data.get("framework")
    if not isinstance(framework, dict):
        raise RuntimeError(f"Invalid EmbrAIon project overlay: {manifest}")

    repository = str(framework.get("repository", "")).strip()
    if repository != CANONICAL_REPOSITORY:
        raise RuntimeError(
            f"Unsupported EmbrAIon framework repository '{repository}' in {manifest}. "
            f"Automatic version resolution currently supports {CANONICAL_REPOSITORY} only."
        )

    version = str(framework.get("version", "")).strip()
    if not version:
        raise RuntimeError(f"Missing framework.version in {manifest}")

    return version


def package_version_for_pin(version: str) -> str:
    legacy = _LEGACY_DEV_PATTERN.fullmatch(version)
    if legacy:
        version = legacy.group(1)

    if not _VERSION_PATTERN.fullmatch(version):
        raise RuntimeError(
            f"Unsupported EmbrAIon version '{version}'. "
            "Use an exact published package version."
        )

    return version


def cache_home() -> Path:
    configured = os.getenv(CACHE_HOME_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".embraion"


def _runtime_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _runtime_marker(environment: Path) -> Path:
    return environment / ".embraion-runtime.json"


def _load_cached_runtime(
    environment: Path,
    package_version: str,
    *,
    touch: bool = False,
) -> CachedRuntime | None:
    python = _runtime_python(environment)
    marker = _runtime_marker(environment)

    if not python.is_file() or not marker.is_file():
        return None

    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        framework = Path(str(data["framework-root"])).resolve()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if data.get("version") != package_version:
        return None
    if not (framework / "framework.yaml").is_file():
        return None
    if not (framework / "core" / "catalog.yaml").is_file():
        return None

    if touch:
        try:
            marker.touch()
        except OSError:
            pass

    return CachedRuntime(python=python, framework_root=framework)


def _remove_stale_lock(lock: Path) -> bool:
    try:
        age = time.time() - lock.stat().st_mtime
    except FileNotFoundError:
        return True

    if age <= _STALE_LOCK_SECONDS:
        return False

    shutil.rmtree(lock, ignore_errors=True)
    return True


def _probe_runtime(python: Path, environment: Path) -> CachedRuntime:
    code = (
        "from importlib.metadata import version; "
        "from embraion.common import framework_root; "
        "print(version('embraion')); "
        "print(framework_root())"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        cwd=str(environment),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError("Installed EmbrAIon runtime did not report framework metadata.")

    return CachedRuntime(
        python=python,
        framework_root=Path(lines[-1]).resolve(),
    )


def ensure_cached_runtime(package_version: str) -> CachedRuntime:
    package_version = package_version_for_pin(package_version)
    versions = cache_home() / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    environment = versions / package_version
    cached = _load_cached_runtime(environment, package_version, touch=True)
    if cached is not None:
        return cached

    lock = versions / f".{package_version}.lock"
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS

    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            cached = _load_cached_runtime(environment, package_version, touch=True)
            if cached is not None:
                return cached

            if _remove_stale_lock(lock):
                continue

            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Timed out waiting for EmbrAIon {package_version} to finish installing."
                )
            time.sleep(0.2)

    try:
        cached = _load_cached_runtime(environment, package_version, touch=True)
        if cached is not None:
            return cached

        if environment.exists():
            shutil.rmtree(environment, ignore_errors=True)

        print(
            f"EmbrAIon: preparing pinned runtime {package_version} in {environment}",
            file=sys.stderr,
        )
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _runtime_python(environment)

        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                f"embraion=={package_version}",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        runtime = _probe_runtime(python, environment)
        version_probe = subprocess.run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; print(version('embraion'))",
            ],
            cwd=str(environment),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        installed_version = version_probe.stdout.strip()
        if installed_version != package_version:
            raise RuntimeError(
                f"Expected EmbrAIon {package_version}, installed {installed_version or 'unknown'}."
            )

        _runtime_marker(environment).write_text(
            json.dumps(
                {
                    "version": package_version,
                    "framework-root": str(runtime.framework_root),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        return runtime
    except Exception:
        shutil.rmtree(environment, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(lock, ignore_errors=True)


def _command_name(argv: Sequence[str]) -> str | None:
    for token in argv:
        if not token.startswith("-"):
            return token
    return None


def _resolution_disabled(argv: Sequence[str]) -> bool:
    if os.getenv(RESOLUTION_GUARD_ENV) == "1":
        return True
    if os.getenv(DISABLE_RESOLUTION_ENV) == "1":
        return True
    if os.getenv("EMBRAION_HOME"):
        return True
    return _command_name(argv) in _BYPASS_COMMANDS


def resolve_project_runtime(
    argv: Sequence[str],
    current_version: str,
    *,
    start: Path | None = None,
) -> int | None:
    if _resolution_disabled(argv):
        return None

    manifest = find_project_manifest(start)
    if manifest is None:
        return None

    pin = read_project_pin(manifest)
    package_version = package_version_for_pin(pin)
    active_version = package_version_for_pin(current_version)

    if package_version == active_version:
        return None

    runtime = ensure_cached_runtime(package_version)

    environment = os.environ.copy()
    environment[RESOLUTION_GUARD_ENV] = "1"
    environment[RESOLVED_VERSION_ENV] = package_version
    environment[RESOLVED_PROJECT_ENV] = str(manifest)
    environment["EMBRAION_HOME"] = str(runtime.framework_root)

    result = subprocess.run(
        [str(runtime.python), "-m", "embraion.cli", *argv],
        env=environment,
    )
    return int(result.returncode)


def cached_runtime_path(version: str) -> Path:
    return cache_home() / "versions" / package_version_for_pin(version)


def cached_runtime_ready(version: str) -> bool:
    package_version = package_version_for_pin(version)
    environment = cached_runtime_path(package_version)
    return _load_cached_runtime(environment, package_version, touch=False) is not None


def list_cached_runtimes() -> list[dict[str, object]]:
    versions = cache_home() / "versions"
    if not versions.is_dir():
        return []

    entries: list[dict[str, object]] = []
    for environment in sorted(versions.iterdir(), key=lambda item: item.name):
        if not environment.is_dir() or environment.name.startswith("."):
            continue

        version = environment.name
        marker = _runtime_marker(environment)
        ready = _load_cached_runtime(environment, version, touch=False) is not None

        last_used: str | None = None
        if marker.exists():
            try:
                last_used = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(marker.stat().st_mtime),
                )
            except OSError:
                pass

        entries.append(
            {
                "version": version,
                "path": str(environment),
                "state": "ready" if ready else "invalid",
                "last-used-utc": last_used,
            }
        )

    return entries


def project_runtime_status(
    current_version: str,
    *,
    start: Path | None = None,
) -> dict[str, object]:
    manifest = find_project_manifest(start)
    root = cache_home()

    if manifest is None:
        return {
            "launcher-version": current_version,
            "project": None,
            "manifest": None,
            "project-pin": None,
            "resolved-version": current_version,
            "runtime-source": "launcher",
            "runtime-cache": None,
            "runtime-cached": False,
            "cache-root": str(root),
            "cached-versions": len(list_cached_runtimes()),
        }

    pin = read_project_pin(manifest)
    resolved = package_version_for_pin(pin)
    active = package_version_for_pin(current_version)
    project = manifest.parent.parent

    if resolved == active:
        source = "launcher"
        runtime_cache: str | None = None
        ready = False
    else:
        path = cached_runtime_path(resolved)
        ready = cached_runtime_ready(resolved)
        source = "cache" if ready else "download-on-demand"
        runtime_cache = str(path)

    return {
        "launcher-version": current_version,
        "project": str(project),
        "manifest": str(manifest),
        "project-pin": pin,
        "resolved-version": resolved,
        "runtime-source": source,
        "runtime-cache": runtime_cache,
        "runtime-cached": ready,
        "cache-root": str(root),
        "cached-versions": len(list_cached_runtimes()),
    }


def cache_prune_candidates(
    *,
    older_than_days: int | None = None,
    protected_versions: Sequence[str] = (),
) -> list[dict[str, object]]:
    if older_than_days is not None and older_than_days < 0:
        raise RuntimeError("--older-than must be zero or greater.")

    versions = cache_home() / "versions"
    if not versions.is_dir():
        return []

    protected = {package_version_for_pin(value) for value in protected_versions}
    now = time.time()
    candidates: list[dict[str, object]] = []

    for path in sorted(versions.iterdir(), key=lambda item: item.name):
        if path.name.startswith(".") and path.name.endswith(".lock") and path.is_dir():
            try:
                age_seconds = now - path.stat().st_mtime
            except OSError:
                continue
            if age_seconds > _STALE_LOCK_SECONDS:
                candidates.append(
                    {
                        "version": None,
                        "path": str(path),
                        "reason": "stale-lock",
                    }
                )
            continue

        if not path.is_dir() or path.name.startswith("."):
            continue

        version = path.name
        runtime = _load_cached_runtime(path, version, touch=False)
        if runtime is None:
            candidates.append(
                {
                    "version": version,
                    "path": str(path),
                    "reason": "invalid-runtime",
                }
            )
            continue

        if older_than_days is None or version in protected:
            continue

        marker = _runtime_marker(path)
        try:
            age_days = (now - marker.stat().st_mtime) / 86400
        except OSError:
            continue

        if age_days >= older_than_days:
            candidates.append(
                {
                    "version": version,
                    "path": str(path),
                    "reason": f"unused-{older_than_days}-days",
                }
            )

    return candidates


def prune_cache(
    *,
    apply: bool = False,
    older_than_days: int | None = None,
    protected_versions: Sequence[str] = (),
) -> list[dict[str, object]]:
    candidates = cache_prune_candidates(
        older_than_days=older_than_days,
        protected_versions=protected_versions,
    )

    if apply:
        for item in candidates:
            shutil.rmtree(Path(str(item["path"])), ignore_errors=True)

    return candidates
