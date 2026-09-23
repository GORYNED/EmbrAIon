from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import iter_text_files, read_json, state_root, write_json

SEVERITY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

SECRET_PATTERNS = [
    (
        "private-key",
        "critical",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "api-key",
        "high",
        re.compile(
            r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*"
            r"[\"']?(?!\$\{|<|REDACTED|CHANGEME)[A-Za-z0-9_\-/.+=]{16,}"
        ),
    ),
]


def collect_findings(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    legacy_data_class = "COMPANY" + "_SECRET"

    for path in iter_text_files(root):
        relative = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8", errors="ignore")

        for category, severity, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(
                    {
                        "schema-version": 1,
                        "id": f"{category}:{relative}",
                        "severity": severity,
                        "category": category,
                        "message": f"Possible {category} material found",
                        "path": relative,
                    }
                )

        if legacy_data_class in text:
            findings.append(
                {
                    "schema-version": 1,
                    "id": f"legacy-data-class:{relative}",
                    "severity": "medium",
                    "category": "policy-drift",
                    "message": "Legacy data class found; use CONFIDENTIAL",
                    "path": relative,
                }
            )

    return findings


def _redacted_server(
    host: str,
    server_id: str,
    config: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    environment = config.get("env") or config.get("environment") or {}
    names = sorted(str(key) for key in environment.keys()) if isinstance(environment, dict) else []

    command = config.get("command")
    transport = config.get("type") or config.get("transport")

    return {
        "id": server_id,
        "host": host,
        "source": source,
        "state": "observed",
        "access": str(config.get("access", "unknown")),
        "command": command if isinstance(command, str) else None,
        "transport": transport if isinstance(transport, str) else None,
        "environment-names": names,
    }


def collect_mcp_inventory(project: Path) -> dict[str, Any]:
    servers: list[dict[str, Any]] = []

    def parse_json_config(path: Path, host: str) -> None:
        if not path.exists():
            return

        data = read_json(path) or {}
        mapping = data.get("mcpServers") or data.get("servers") or {}

        if isinstance(mapping, dict):
            for server_id, config in mapping.items():
                if isinstance(config, dict):
                    servers.append(
                        _redacted_server(
                            host,
                            str(server_id),
                            config,
                            str(path.relative_to(project)),
                        )
                    )

    parse_json_config(project / ".mcp.json", "generic")
    parse_json_config(project / ".vscode" / "mcp.json", "vscode")
    parse_json_config(project / ".claude" / "settings.json", "claude-code")
    parse_json_config(project / ".claude" / "settings.local.json", "claude-code")

    codex = project / ".codex" / "config.toml"
    if codex.exists():
        import tomllib

        data = tomllib.loads(codex.read_text(encoding="utf-8"))
        mapping = data.get("mcp_servers") or {}

        if isinstance(mapping, dict):
            for server_id, config in mapping.items():
                if isinstance(config, dict):
                    servers.append(
                        _redacted_server(
                            "codex",
                            str(server_id),
                            config,
                            str(codex.relative_to(project)),
                        )
                    )

    return {
        "schema-version": 1,
        "servers": servers,
    }


def save_mcp_inventory(project: Path, output: Path | None = None) -> dict[str, Any]:
    inventory = collect_mcp_inventory(project)
    destination = output or (state_root(project) / "mcp.json")
    write_json(destination, inventory)
    return inventory
