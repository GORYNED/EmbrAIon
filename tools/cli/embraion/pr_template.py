"""Install the optional, project-neutral pull request template without overwriting anything."""
from __future__ import annotations

from pathlib import Path

from .common import atomic_write_bytes, framework_root

TEMPLATE = Path("templates") / "pull-request" / "pull-request-template.md"
TARGET = Path(".github") / "pull_request_template.md"
# Locations (and case variants) a Git host reads a single pull request template from.
_SEARCH_DIRECTORIES = (Path("."), Path(".github"), Path("docs"))


def _existing_template(root: Path) -> Path | None:
    """Return a template or template folder a host would already use, if any."""
    for directory in _SEARCH_DIRECTORIES:
        folder = root / directory
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            if entry.name.lower() in {"pull_request_template.md", "pull_request_template"}:
                return entry.relative_to(root)
    return None


def install_pr_template(path: Path) -> dict[str, str]:
    """Write `.github/pull_request_template.md` under `path` unless a template already exists.

    Returns ``{"status": "created" | "exists", "path": <project-relative path>}``. An existing
    file, folder, or link is never replaced, and the result names it.
    """
    root = path.resolve()
    if not root.is_dir():
        raise RuntimeError(f"{root} is not a directory")
    found = _existing_template(root)
    if found is not None:
        return {"status": "exists", "path": found.as_posix()}
    target = root / TARGET
    if target.is_symlink() or target.exists():
        return {"status": "exists", "path": TARGET.as_posix()}
    if target.parent.is_symlink() or (target.parent.exists() and not target.parent.is_dir()):
        raise RuntimeError(f"{TARGET.parent.as_posix()} must be a regular directory")
    content = (framework_root(root) / TEMPLATE).read_bytes()
    atomic_write_bytes(target, content)
    return {"status": "created", "path": TARGET.as_posix()}
