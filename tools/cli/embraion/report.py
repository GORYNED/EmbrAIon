"""Project completion report contract: template generation and text validation.

The contract lives in `.embraion/report.yaml`. Validation is deterministic and
checks structure only; it cannot judge whether report content is true.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import project_root
from .policy import _validated_config_mapping
from .security import redact_text


REPORT_CONFIG = Path(".embraion") / "report.yaml"
REPORT_KINDS = ("final", "intermediate")

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_BOLD_LINE = re.compile(r"^\s{0,3}\*\*(.+?)\*\*\s*:?\s*$")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_TASK_STATUS = re.compile(r"^[\s>*_`-]*Task status[*_`]*\s*:\s*[*_`]*([A-Za-z-]+)", re.IGNORECASE)
_PULL_REQUEST = re.compile(r"https?://[^\s<>()\[\]]+/(?:pull|pulls|merge_requests)/\d+")
_ABSOLUTE_PATH = re.compile(
    r"(?<![\w.])(?:[A-Za-z]:[\\/]|\\\\[\w.-]+\\|/(?:Users|home|root|tmp|var|etc|opt|mnt|private|Volumes)/)"
)
_RAW_CONTENT = re.compile(r"```|^diff --git|@@ -\d|^[+-]{3} [ab]/")


def read_report_contract(project: Path | None = None, path: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    source = path or root / REPORT_CONFIG
    if not source.is_file():
        raise RuntimeError(f"Missing {source}; declare the completion report contract first.")
    contract = _validated_config_mapping(source, schema_name="report.schema.json", label=str(REPORT_CONFIG))
    sections = contract["sections"]
    for key in ("workers", "pull-request"):
        section = (contract.get(key) or {}).get("section")
        if section is not None and section not in sections:
            raise RuntimeError(f"Invalid {REPORT_CONFIG}: {key}.section '{section}' is not a listed section.")
    return contract


def _table_cells(line: str) -> list[str] | None:
    text = line.strip()
    if not text.startswith("|"):
        return None
    text = text[1:-1] if text.endswith("|") and len(text) > 1 else text[1:]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", text)]


def _parse(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[int, str]]]:
    """Return headings, tables, and non-fenced lines with 1-based line numbers."""
    headings: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    lines: list[tuple[int, str]] = []
    fence: str | None = None
    raw = text.splitlines()
    index = 0
    while index < len(raw):
        number, line = index + 1, raw[index]
        marker = _FENCE.match(line)
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            index += 1
            continue
        if marker:
            fence = marker.group(1)
            index += 1
            continue
        lines.append((number, line))
        heading = _HEADING.match(line)
        bold = _BOLD_LINE.match(line)
        if heading:
            headings.append({"line": number, "level": len(heading.group(1)), "text": heading.group(2).strip()})
        elif bold:
            headings.append({"line": number, "level": 7, "text": bold.group(1).strip()})
        header = _table_cells(line)
        separator = _table_cells(raw[index + 1]) if index + 1 < len(raw) else None
        if header and separator and len(separator) == len(header) and all(
            _SEPARATOR_CELL.match(cell) for cell in separator
        ):
            rows: list[list[str]] = []
            index += 2
            while index < len(raw) and (cells := _table_cells(raw[index])) is not None:
                lines.append((index + 1, raw[index]))
                rows.append(cells)
                index += 1
            tables.append({"line": number, "header": header, "rows": rows})
            continue
        index += 1
    return headings, tables, lines


def _issue(code: str, line: int | None, message: str) -> dict[str, Any]:
    return {"code": code, "line": line, "message": message}


def validate_report(
    text: str,
    contract: dict[str, Any],
    *,
    kind: str = "final",
    pull_request: bool = False,
) -> list[dict[str, Any]]:
    if kind not in REPORT_KINDS:
        raise RuntimeError(f"Unknown report kind '{kind}'. Expected one of: {', '.join(REPORT_KINDS)}.")
    headings, tables, lines = _parse(text)
    sections: list[str] = contract["sections"]
    workers = contract.get("workers") or {}
    columns = workers.get("columns")
    workers_section = workers.get("section")
    issues: list[dict[str, Any]] = []

    def is_workers_table(table: dict[str, Any]) -> bool:
        return columns is not None and [cell.lower() for cell in table["header"]] == [c.lower() for c in columns]

    if kind == "intermediate":
        for table in tables:
            if is_workers_table(table):
                issues.append(_issue("intermediate-workers-table", table["line"],
                                     "Intermediate messages must not publish the Workers table."))
        for heading in headings:
            if workers_section and heading["text"].lower() == workers_section.lower():
                issues.append(_issue("intermediate-workers-section", heading["line"],
                                     f"Intermediate messages must not contain a '{workers_section}' section."))
        return issues

    by_name = {name.lower(): name for name in sections}
    found = [heading for heading in headings if heading["text"].lower() in by_name]
    names = [by_name[heading["text"].lower()] for heading in found]
    if names != sections:
        missing = [name for name in sections if name not in names]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if duplicated:
            detail.append("repeated " + ", ".join(duplicated))
        if not detail:
            detail.append("found " + ", ".join(names))
        issues.append(_issue("report-sections", found[0]["line"] if found else None,
                             f"Report must contain exactly {', '.join(sections)} in this order; "
                             + "; ".join(detail) + "."))
    if found:
        level = found[0]["level"]
        for heading in headings:
            if heading["level"] == level and heading["text"].lower() not in by_name and heading["line"] > found[0]["line"]:
                issues.append(_issue("report-extra-section", heading["line"],
                                     f"Unexpected top-level section '{heading['text']}'."))

    # Section bodies run from one listed heading to the next listed heading.
    spans: dict[str, tuple[int, int]] = {}
    for position, heading in enumerate(found):
        end = found[position + 1]["line"] if position + 1 < len(found) else len(text.splitlines()) + 1
        spans.setdefault(by_name[heading["text"].lower()], (heading["line"], end))

    def body(name: str) -> list[tuple[int, str]]:
        start, end = spans.get(name, (0, 0))
        return [(number, line) for number, line in lines if start < number < end]

    if columns is not None:
        workers_tables = [table for table in tables if is_workers_table(table)]
        start, end = spans.get(workers_section, (0, 0))
        inside = [table for table in tables if start < table["line"] < end]
        if len(workers_tables) != 1:
            issues.append(_issue("workers-table-count", workers_tables[1]["line"] if len(workers_tables) > 1 else None,
                                 f"The final report needs exactly one Workers table; found {len(workers_tables)}."))
        for table in inside:
            if not is_workers_table(table):
                issues.append(_issue("workers-columns", table["line"],
                                     "Workers table columns must be exactly: " + ", ".join(columns) + "."))
        for table in workers_tables:
            if not start < table["line"] < end:
                issues.append(_issue("workers-table-location", table["line"],
                                     f"The Workers table belongs in the '{workers_section}' section."))
        statuses = workers.get("task-status")
        if statuses:
            status_lines = [(number, match.group(1)) for number, line in body(workers_section)
                            if (match := _TASK_STATUS.match(line))]
            if not status_lines:
                issues.append(_issue("workers-task-status", start or None,
                                     "Workers needs a 'Task status: " + "|".join(statuses) + "' line."))
            else:
                number, value = status_lines[0]
                if value.lower() not in [item.lower() for item in statuses]:
                    issues.append(_issue("workers-task-status", number,
                                         f"Task status '{value}' is not one of {', '.join(statuses)}."))
                if inside and number > inside[0]["line"]:
                    issues.append(_issue("workers-task-status", number,
                                         "The Task status line must precede the Workers table."))
        for table in workers_tables:
            for offset, row in enumerate(table["rows"], start=2):
                for cell in row:
                    line = table["line"] + offset
                    if _ABSOLUTE_PATH.search(cell):
                        issues.append(_issue("workers-absolute-path", line,
                                             "Workers table must not contain absolute machine paths."))
                    if redact_text(cell) != cell:
                        issues.append(_issue("workers-credential", line,
                                             "Workers table must not contain credential-like values."))
                    if _RAW_CONTENT.search(cell):
                        issues.append(_issue("workers-raw-content", line,
                                             "Workers table must not contain code, diffs, or raw output."))

    if pull_request:
        target = (contract.get("pull-request") or {}).get("section") or sections[0]
        content = "\n".join(line for _, line in body(target))
        if not _PULL_REQUEST.search(content):
            issues.append(_issue("pull-request-link", spans.get(target, (None,))[0],
                                 f"'{target}' must contain the full pull request URL."))
    return issues


def render_report_skeleton(contract: dict[str, Any]) -> str:
    sections: list[str] = contract["sections"]
    workers = contract.get("workers") or {}
    pull_request = (contract.get("pull-request") or {}).get("section")
    lines: list[str] = []
    for name in sections:
        lines += [f"## {name}", ""]
        if name == pull_request:
            lines += ["PR: <full pull request URL, when a pull request was created>", ""]
        if name == workers.get("section") and workers.get("columns"):
            if workers.get("task-status"):
                lines += ["Task status: " + "|".join(workers["task-status"]), ""]
            columns = workers["columns"]
            lines.append("| " + " | ".join(columns) + " |")
            lines += ["| " + " | ".join("---" for _ in columns) + " |", ""]
        else:
            lines += [f"<{name}>", ""]
    return "\n".join(lines).rstrip() + "\n"


def report_rules(contract: dict[str, Any]) -> list[str]:
    sections: list[str] = contract["sections"]
    workers = contract.get("workers") or {}
    pull_request = (contract.get("pull-request") or {}).get("section")
    rules = ["The final report contains exactly the sections "
             + ", ".join(f"`{name}`" for name in sections) + ", once each and in this order."]
    if workers.get("columns"):
        rules.append(
            f"Publish the `{workers['section']}` table only in the final report, exactly once; "
            "intermediate updates use plain language without it."
        )
        rules.append(
            "Table cells never contain prompts, source code, diffs, raw reasoning, credentials, "
            "absolute machine paths, or CONFIDENTIAL details."
        )
    if pull_request:
        rules.append(f"When a pull request was created, `{pull_request}` contains its full URL.")
    rules.extend(contract.get("guidance") or [])
    rules.append("Check a report with `embraion report validate <file>`; add `--kind intermediate` "
                 "for progress updates and `--pull-request` when a pull request was created.")
    return rules


def render_report_template(contract: dict[str, Any]) -> str:
    """Plain template for a host or a person: skeleton followed by the rules."""
    rules = "\n".join(f"- {rule}" for rule in report_rules(contract))
    return render_report_skeleton(contract) + "\nRules:\n\n" + rules + "\n"


def render_report_guidance(contract: dict[str, Any]) -> str:
    """Skill projection text; the skeleton is fenced so it does not alter skill headings."""
    rules = "\n".join(f"- {rule}" for rule in report_rules(contract))
    return (
        "## Project completion report contract\n\n"
        "Generated from `.embraion/report.yaml`. Use this skeleton for the final report of substantial work:\n\n"
        "```markdown\n" + render_report_skeleton(contract) + "```\n\n" + rules + "\n"
    )
