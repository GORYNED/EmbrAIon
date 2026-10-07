"""Detect changes that need an architecture decision record, and scaffold records."""
from __future__ import annotations

import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .common import atomic_write_bytes, framework_root, project_root
from .policy import _validated_config_mapping, path_matches, read_knowledge_config

DEFAULT_FOLDER = "docs/architecture/decisions"
DEFAULT_INDEX = "README.md"
DEFAULT_TEMPLATE = "0000-template.md"
WAIVER_TRAILER = "Decision-Waiver"
CHANGE_KINDS = {"A": "added", "D": "deleted", "M": "modified", "T": "modified", "R": "renamed"}
# A new or removed package is the only default trigger: a changed manifest is mostly a routine
# dependency bump, and a false positive on routine work gets the check disabled.
DEFAULT_TRIGGERS: list[dict[str, Any]] = [{
    "id": "package-added-or-removed",
    "paths": ["**/package.json", "**/*.asmdef", "**/pyproject.toml", "**/Cargo.toml", "**/go.mod", "**/*.csproj"],
    "changes": ["added", "deleted"],
}]
MAX_LINE = 4096
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCALE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})?$")
NUMBERED = re.compile(r"(?<![0-9A-Za-z])(\d{2,})-[a-z0-9][a-z0-9-]*\.md\b")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f"Decision Git operation failed ({' '.join(args[:2])}): "
                           + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.decode("utf-8", "surrogateescape")


def read_decisions_config(root: Path) -> dict[str, Any] | None:
    """Return the validated `.embraion/decisions.yaml`, or None when the project has none."""
    path = root / ".embraion" / "decisions.yaml"
    if not path.is_file():
        return None
    config = _validated_config_mapping(path, schema_name="decisions.schema.json",
                                       label=".embraion/decisions.yaml")
    for trigger in config.get("triggers", []):
        for pattern in trigger.get("patterns", []):
            try:
                re.compile(pattern)
            except re.error:
                raise RuntimeError("Invalid .embraion/decisions.yaml: a trigger pattern is not a regular expression") from None
    return config


def decisions_folder(root: Path) -> str:
    """Return the project-relative decisions folder: the `decisions` knowledge slot, else the default."""
    slots: dict[str, Any] = {}
    if (root / ".embraion" / "knowledge.yaml").is_file():
        slots = read_knowledge_config(root).get("slots") or {}
    raw = slots.get("decisions")
    folder = str(raw.get("path") if isinstance(raw, dict) else raw or DEFAULT_FOLDER).rstrip("/")
    parts = folder.split("/")
    if (not folder or folder.startswith("/") or "\\" in folder or "\x00" in folder
            or any(part in ("", ".", "..") for part in parts)):
        raise RuntimeError("The decisions folder must be a project-relative path")
    if not (root / folder).resolve().is_relative_to(root.resolve()):
        raise RuntimeError("The decisions folder resolves outside the project")
    return folder


def _changes(root: Path, base: str, head: str) -> list[dict[str, str]]:
    chunks = _git(root, "diff", "--find-renames", "--name-status", "-z", base, head).split("\x00")
    changes: list[dict[str, str]] = []
    index = 0
    while index < len(chunks) and chunks[index]:
        status = chunks[index][0]
        if status == "R" and index + 2 < len(chunks):
            changes.append({"change": "renamed", "path": chunks[index + 2], "old": chunks[index + 1]})
            index += 3
        elif index + 1 < len(chunks):
            changes.append({"change": CHANGE_KINDS.get(status, "modified"), "path": chunks[index + 1]})
            index += 2
        else:
            break
    return changes


def _changed_lines(root: Path, base: str, head: str, change: dict[str, str]) -> list[str]:
    paths = [change["path"]] + ([change["old"]] if "old" in change else [])
    raw = _git(root, "--literal-pathspecs", "diff", "--find-renames", "--unified=0", "--no-color", "--no-ext-diff", base, head, "--", *paths)
    return [line[1:MAX_LINE] for line in raw.splitlines()
            if line[:1] in ("+", "-") and not line.startswith(("+++", "---"))]


def _fired(root: Path, base: str, head: str, changes: list[dict[str, str]], triggers: list[dict[str, Any]]) -> list[dict[str, str]]:
    fired: list[dict[str, str]] = []
    for trigger in triggers:
        kinds = set(trigger.get("changes") or CHANGE_KINDS.values())
        patterns = [re.compile(pattern) for pattern in trigger.get("patterns", [])]
        for change in changes:
            if change["change"] not in kinds:
                continue
            if not any(path_matches(path, trigger["paths"]) for path in (change["path"], change.get("old")) if path):
                continue
            if patterns and not any(pattern.search(line) for line in _changed_lines(root, base, head, change)
                                    for pattern in patterns):
                continue
            fired.append({"trigger": trigger.get("id", "declared"), "path": change["path"], "change": change["change"]})
    return fired


def check_decisions(project: Path | None = None, *, base_ref: str, head_ref: str = "HEAD",
                    waiver: str | None = None, require_config: bool = False) -> dict[str, Any]:
    """Fail when the change from `base_ref` to `head_ref` fires a trigger without a record or a waiver.

    The check is read-only. A trigger is satisfied by an added or changed record in the decisions
    folder, or by a waiver: a `Decision-Waiver:` trailer on a commit in the change, or `waiver` text.
    """
    root = project_root(project)
    config = read_decisions_config(root)
    if config is None:
        if require_config:
            return {"status": "failed", "passed": False, "reason": "No .embraion/decisions.yaml",
                    "triggers": [], "records": [], "waivers": []}
        return {"status": "skipped", "passed": True, "reason": "No .embraion/decisions.yaml",
                "triggers": [], "records": [], "waivers": []}
    folder = decisions_folder(root)
    base = _git(root, "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}").strip()
    head = _git(root, "rev-parse", "--verify", "--end-of-options", f"{head_ref}^{{commit}}").strip()
    origin = _git(root, "merge-base", base, head).strip()
    changes = _changes(root, origin, head)
    fired = _fired(root, origin, head, changes, config.get("triggers") or DEFAULT_TRIGGERS)
    excluded = {config.get("index", DEFAULT_INDEX), config.get("template", DEFAULT_TEMPLATE)}
    records = sorted(item["path"] for item in changes
                     if item["change"] != "deleted" and item["path"].endswith(".md")
                     and PurePosixPath(item["path"]).parent.as_posix() == folder
                     and PurePosixPath(item["path"]).name not in excluded)
    trailers = _git(root, "log", f"--format=%(trailers:key={WAIVER_TRAILER},valueonly,unfold)%x00", f"{origin}..{head}")
    waivers = [text.strip() for text in trailers.split("\x00") if text.strip()]
    if waiver and waiver.strip():
        waivers.append(waiver.strip())
    report: dict[str, Any] = {"mode": "incremental", "base_commit": base, "head_commit": head, "merge_base": origin,
                              "folder": folder, "triggers": fired, "records": records, "waivers": waivers}
    if not fired:
        return {**report, "status": "passed", "passed": True, "outcome": "no-trigger"}
    if records:
        return {**report, "status": "passed", "passed": True, "outcome": "recorded"}
    if waivers:
        return {**report, "status": "passed", "passed": True, "outcome": "waived"}
    return {**report, "status": "failed", "passed": False, "outcome": "missing-record",
            "reason": f"Add or update a decision record in {folder}, or state why none is needed with a "
                      f"'{WAIVER_TRAILER}: <reason>' commit trailer or --waiver"}


def _template(root: Path, name: str) -> str:
    return (framework_root(root) / "templates" / "decisions" / name).read_text(encoding="utf-8")


def _existing_numbers(root: Path, folder: str, index_text: str) -> list[str]:
    """Collect every number the folder, its index, or any ref's history has used, so none is reused."""
    found = [match.group(1) for path in (root / folder).glob("*.md") for match in [NUMBERED.match(path.name)] if match]
    found += NUMBERED.findall(index_text)
    try:
        history = _git(root, "--literal-pathspecs", "log", "--all", "--name-only", "--format=", "--", folder)
    except (RuntimeError, OSError):
        history = ""  # Outside Git, or without history, the folder and index are all there is to read.
    found += [match.group(1) for line in history.splitlines()
              if PurePosixPath(line).parent.as_posix() == folder
              for match in [NUMBERED.match(PurePosixPath(line).name)] if match]
    return found


def _slug(title: str, slug: str | None) -> str:
    if slug is None:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    if not SLUG.match(slug):
        raise RuntimeError("The record needs a lowercase kebab-case file name; pass --slug when the title has no ASCII words")
    return slug


def _cell_role(header: str) -> str:
    text = header.strip().lower()
    for role, words in (("status", ("status",)), ("date", ("date",)),
                        ("title", ("title", "decision", "name", "subject")),
                        ("link", ("adr", "record", "id", "number", "#", "№", "no"))):
        if any(word == text or (len(word) > 3 and word in text) for word in words):
            return role
    return ""


def _index_with_row(text: str, row: dict[str, str]) -> str:
    """Append one record to the index's last table, matching its columns by header, or add a table."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    table: list[int] = []
    for position, line in enumerate(lines[:-1]):
        if line.lstrip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[position + 1]):
            end = position + 2
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            table = [position, end]
    if not table:
        table_text = ("| ADR | Status | Decision |", "| --- | --- | --- |",
                      f"| {row['link']} | {row['status']} | {row['title']} |")
        return text.rstrip("\r\n") + (newline * 2 if text.strip() else "") + newline.join(table_text) + newline
    headers = [cell.strip() for cell in lines[table[0]].strip().strip("|").split("|")]
    roles = [_cell_role(header) for header in headers]
    cells = [row.get(role, "") for role in roles]
    if "link" not in roles:
        merged = roles.index("title") if "title" in roles else 0
        cells[merged] = f"{row['link']} {row['title']}" if "title" in roles else row["link"]
    lines.insert(table[1], "| " + " | ".join(cells) + " |")
    return newline.join(lines) + newline


def new_decision(title: str, project: Path | None = None, *, locales: list[str] | None = None,
                 slug: str | None = None, status: str = "Proposed", day: str | None = None) -> dict[str, Any]:
    """Create the next numbered record from the project template and add it to the index."""
    title = title.strip()
    if not title or len(title) > 200 or any(ord(char) < 32 for char in title):
        raise RuntimeError("The title must be one non-empty line of at most 200 characters")
    status = status.strip()
    if not status or len(status) > 40 or any(ord(char) < 32 for char in status):
        raise RuntimeError("The status must be one non-empty line of at most 40 characters")
    locales = list(dict.fromkeys(locales or []))
    if any(not LOCALE.match(locale) for locale in locales):
        raise RuntimeError("A locale must be a lowercase language code such as ru or pt-br")
    day = date.fromisoformat(day).isoformat() if day else datetime.now(timezone.utc).date().isoformat()
    name = _slug(title, slug)
    root = project_root(project)
    config = read_decisions_config(root) or {}
    folder = decisions_folder(root)
    directory = root / folder
    index_path = directory / config.get("index", DEFAULT_INDEX)
    template_path = directory / config.get("template", DEFAULT_TEMPLATE)
    for path in (directory, index_path, template_path):
        if path.exists() and path.is_symlink():
            raise RuntimeError("The decisions folder, index and template must not be symbolic links")
    if directory.exists() and not directory.is_dir():
        raise RuntimeError("The decisions folder path is not a directory")
    index_text = index_path.read_bytes().decode("utf-8") if index_path.is_file() else ""
    numbers = _existing_numbers(root, folder, index_text)
    width = max([len(number) for number in numbers] or [4])
    number = f"{max([int(value) for value in numbers] or [0]) + 1:0{width}d}"
    stem = f"{number}-{name}"
    created: list[str] = []
    if not template_path.is_file():
        atomic_write_bytes(template_path, _template(root, "record.md").encode("utf-8"))
        created.append(template_path.relative_to(root).as_posix())
    files: dict[Path, str] = {}
    for locale in [None, *locales]:
        source = template_path.with_name(f"{template_path.stem}-{locale}{template_path.suffix}") if locale else template_path
        text = (source if source.is_file() else template_path).read_text(encoding="utf-8")
        values = {"number": number, "title": title, "status": status, "date": day}
        text = re.sub(r"\{\{(number|title|status|date)\}\}", lambda match: values[match.group(1)], text)
        files[directory / (f"{stem}-{locale}.md" if locale else f"{stem}.md")] = text
    for path in files:
        if path.exists():
            raise RuntimeError(f"{path.relative_to(root).as_posix()} already exists")
    for path, text in files.items():
        atomic_write_bytes(path, text.encode("utf-8"))
    if not index_path.is_file():
        index_text = _template(root, "index.md")
        created.append(index_path.relative_to(root).as_posix())
    link = f"[`{stem}.md`]({stem}.md)" + "".join(f" ([{locale}]({stem}-{locale}.md))" for locale in locales)
    atomic_write_bytes(index_path, _index_with_row(index_text, {"link": link, "title": title.replace("|", "\\|"),
                                                                "status": status, "date": day}).encode("utf-8"))
    return {"number": number, "status": status, "paths": [path.relative_to(root).as_posix() for path in files],
            "index": index_path.relative_to(root).as_posix(), "created": created}
