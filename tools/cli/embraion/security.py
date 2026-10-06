from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import iter_text_files, read_json, read_yaml, state_root, write_json

SEVERITY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

# Provider-issued credentials have recognizable prefixes, so they are found
# even without a `token=` style key in front of them.
_ACCESS_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"gh[pousr]_[A-Za-z0-9]{36,}"
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|sk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}"
    r"|AIza[0-9A-Za-z_-]{35}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"
    r")(?![A-Za-z0-9_])"
)
# A home directory names a person and a machine; placeholders and CI runner homes are allowed.
_MACHINE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.])(?:/Users/|/home/|[A-Za-z]:\\Users\\)"
    r"(?!(?:runner|user|username|example|you|me|name|USER|USERNAME)(?:[/\\]|$))"
    r"(?![<$%{])[A-Za-z0-9._-]+[/\\]"
)

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
            r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|secret|token|password)\s*[:=]\s*"
            r"[\"']?(?!\$\{|<|REDACTED|CHANGEME)[A-Za-z0-9_\-/.+=]{16,}"
        ),
    ),
    ("access-token", "high", _ACCESS_TOKEN),
    ("machine-path", "medium", _MACHINE_PATH),
]


def _declared_confidential_aliases(root: Path) -> set[str]:
    path = root / ".embraion" / "execution.yaml"
    if not path.is_file():
        return set()

    try:
        config = read_yaml(path) or {}
    except Exception:
        return set()
    if not isinstance(config, dict):
        return set()

    bindings = config.get("bindings")
    if not isinstance(bindings, dict):
        return set()

    aliases: set[str] = set()
    for binding in bindings.values():
        if not isinstance(binding, dict):
            continue
        mapping = binding.get("dataClassAliases")
        if not isinstance(mapping, dict):
            continue
        alias = mapping.get("CONFIDENTIAL")
        if (
            isinstance(alias, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]*", alias)
        ):
            aliases.add(alias)
    return aliases


def collect_findings(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    legacy_data_class = "COMPANY" + "_SECRET"
    declared_aliases = _declared_confidential_aliases(root)

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

        if legacy_data_class in text and legacy_data_class not in declared_aliases:
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


_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.DOTALL,
)
_KEY_VALUE_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)\b"
    r"(\s*[:=]\s*)"
    r"([\"']?)(?!\$\{|<|REDACTED|CHANGEME)"
    r"[A-Za-z0-9_\-/.+=]{8,}\3"
)
_BEARER_SECRET = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9_\-/.+=]{8,}"
)


def redact_text(value: str) -> str:
    value = _PRIVATE_KEY_BLOCK.sub("<REDACTED:private-key>", value)
    value = _BEARER_SECRET.sub("Bearer <REDACTED>", value)
    value = _ACCESS_TOKEN.sub("<REDACTED:access-token>", value)

    def replace_secret(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}<REDACTED>"

    return _KEY_VALUE_SECRET.sub(replace_secret, value)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(key): redact_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [redact_value(child) for child in value]
    if isinstance(value, tuple):
        return [redact_value(child) for child in value]
    return value


DEFAULT_ENVIRONMENT_ALLOWLIST = frozenset(
    {
        "CI",
        "COMSPEC",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "WINDIR",
    }
)


def allowlisted_environment(
    environment: Mapping[str, str],
    *,
    extra: Iterable[str] = (),
) -> dict[str, str]:
    allowed = set(DEFAULT_ENVIRONMENT_ALLOWLIST)
    allowed.update(str(name) for name in extra)
    return {
        name: str(environment[name])
        for name in sorted(allowed)
        if name in environment
    }


def redact_child_output(
    stdout: str | None,
    stderr: str | None,
) -> dict[str, str]:
    return {
        "stdout": redact_text(stdout or ""),
        "stderr": redact_text(stderr or ""),
    }
