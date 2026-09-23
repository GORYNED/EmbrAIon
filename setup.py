from __future__ import annotations

from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).resolve().parent
DESTINATION = Path("share") / "embraion"

ROOT_FILES = (
    "framework.yaml",
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "TRADEMARKS.md",
)

RESOURCE_DIRECTORIES = (
    "core",
    "adapters",
    "schemas",
    "templates",
    "docs",
    "localization",
    "evals",
    "examples",
    "brand",
)

SKIP_NAMES = {".DS_Store"}
SKIP_PARTS = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}


def _eligible(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and path.name not in SKIP_NAMES
        and not any(part in SKIP_PARTS for part in relative.parts)
    )


def _collect_framework_files() -> list[tuple[str, list[str]]]:
    groups: dict[str, list[str]] = {}

    def add(path: Path) -> None:
        relative = path.relative_to(ROOT)
        destination = DESTINATION / relative.parent
        groups.setdefault(destination.as_posix(), []).append(relative.as_posix())

    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            add(path)

    for name in RESOURCE_DIRECTORIES:
        directory = ROOT / name
        if directory.is_dir():
            for path in directory.rglob("*"):
                if _eligible(path):
                    add(path)

    tools = ROOT / "tools"
    if tools.is_dir():
        for path in tools.rglob("*"):
            if not _eligible(path):
                continue
            relative = path.relative_to(tools)
            if relative.parts and relative.parts[0] == "cli":
                continue
            add(path)

    return [
        (destination, sorted(paths))
        for destination, paths in sorted(groups.items())
    ]


setup(data_files=_collect_framework_files())
