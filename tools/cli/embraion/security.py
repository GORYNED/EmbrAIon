from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import SKIP_PARTS, framework_root, iter_text_files, read_json, read_yaml, state_root, write_json
from .policy import path_matches

SEVERITY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

# Provider-issued credentials have recognizable prefixes, so they are found even without
# a `token=` style key in front of them. Random token bodies contain digits, which keeps
# identifiers and documentation placeholders out.
_ACCESS_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:"
    r"gh[pousr]_(?=[A-Za-z]*[0-9])[A-Za-z0-9]{36,}"
    r"|github_pat_(?=[A-Za-z_]*[0-9])[A-Za-z0-9_]{60,}"
    r"|(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|sk-(?:ant-|proj-)?(?=[A-Za-z_-]*[0-9])(?=[0-9a-z_-]*[A-Z])[A-Za-z0-9_-]{32,}"
    r"|AIza(?=[A-Za-z_-]*[0-9])[0-9A-Za-z_-]{35}"
    r"|xox[abprs]-(?=[A-Za-z-]*[0-9])[A-Za-z0-9-]{20,}"
    r")(?![A-Za-z0-9_])"
)
# A home directory names a person and a machine; placeholders and CI runner homes are allowed.
_MACHINE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.])(?:/Users/|/home/|[A-Za-z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/))"
    r"(?!(?:runner|user|username|example|you|me|name|USER|USERNAME|Shared|linuxbrew|node)(?:[/\\]|$))"
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


# Patterns precise enough for source code; the keyword-based `api-key` heuristic would flag
# ordinary assignments there, so it stays on configuration and documentation files.
PRECISE_CATEGORIES = frozenset({"private-key", "access-token", "machine-path"})
_CATEGORIES_WITHOUT_MACHINE_PATH = frozenset(category for category, _, _ in SECRET_PATTERNS) - {"machine-path"}
ALL_FILES_MAX_BYTES = 2 * 1024 * 1024


# Only variables that relocate the repository are cleared; configuration such as safe.directory
# passed through the environment still applies.
_GIT_LOCATION_VARIABLES = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX",
})


def _inventory(root: Path) -> list[str]:
    """Return tracked and unignored untracked files, or every file outside tool folders without Git."""
    environment = {key: value for key, value in os.environ.items() if key not in _GIT_LOCATION_VARIABLES}
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment, check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0:
        return [name for name in result.stdout.decode("utf-8", "surrogateescape").split("\x00") if name]
    names: list[str] = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_PARTS]
        names.extend((Path(directory) / name).relative_to(root).as_posix() for name in files)
    return names


def _path_key(relative: str) -> str:
    # Git may report composed Unicode where the file system returns decomposed names, and
    # Windows paths compare case-insensitively.
    key = unicodedata.normalize("NFC", relative.replace("\\", "/"))
    return key.casefold() if os.name == "nt" else key


def _policy_sources(root: Path) -> dict[str, list[str]] | None:
    """Return the project's source globs, or None so that an absent or unusable policy skips nothing."""
    path = root / ".embraion" / "policy.yaml"
    try:
        if path.is_symlink() or not path.is_file():
            return None
        data = read_yaml(path)
    except Exception:
        return None
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, dict):
        return None
    result: dict[str, list[str]] = {}
    for key in ("canonical", "protected", "generated", "external"):
        value = sources.get(key) or []
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            return None
        result[key] = value
    try:
        path_matches("", [pattern for patterns in result.values() for pattern in patterns])
    except RuntimeError:
        return None
    return result


def _policy_skips(relative: str, sources: dict[str, list[str]] | None, categories: tuple[str, ...]) -> bool:
    """Skip vendor or generated paths, but never EmbrAIon configuration or a canonical or protected path."""
    if sources is None or Path(relative).parts[:1] == (".embraion",) or \
            path_matches(relative, sources["canonical"] + sources["protected"]):
        return False
    return any(path_matches(relative, sources[category]) for category in categories)


def _other_text_files(root: Path, seen: set[str]) -> Iterable[tuple[Path, str]]:
    for name in sorted(_inventory(root)):
        if _path_key(name) in seen or Path(name).parts[:2] == (".embraion", "state"):
            continue
        path = root / name
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > ALL_FILES_MAX_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:
            continue
        yield path, data.decode("utf-8", errors="ignore")


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


def _pattern_findings(relative: str, text: str, categories: frozenset[str] | None) -> list[dict[str, str]]:
    return [
        {
            "schema-version": 1,
            "id": f"{category}:{relative}",
            "severity": severity,
            "category": category,
            "message": f"Possible {category} material found",
            "path": relative,
        }
        for category, severity, pattern in SECRET_PATTERNS
        if (categories is None or category in categories) and pattern.search(text)
    ]


def collect_findings(root: Path, all_files: bool = False,
                     skipped: list[str] | None = None) -> list[dict[str, str]]:
    """Scan configuration and documentation files; with ``all_files`` also every other text file.

    Other text files are the tracked and unignored untracked files (every file outside tool folders
    without Git) of at most ``ALL_FILES_MAX_BYTES`` without a NUL byte. They are checked only for
    ``PRECISE_CATEGORIES``.

    With ``all_files`` the project's ``.embraion/policy.yaml`` waives only the ``machine-path`` check
    for content the project cannot edit: other text files under ``sources.external`` or
    ``sources.generated``, and configuration and documentation files under ``sources.external``.
    Every secret check still runs on those files, and canonical and protected paths keep every
    check. Relative paths whose machine-path check was waived are appended to ``skipped``.
    """
    findings: list[dict[str, str]] = []
    legacy_data_class = "COMPANY" + "_SECRET"
    declared_aliases = _declared_confidential_aliases(root)
    seen: set[str] = set()
    sources = _policy_sources(root) if all_files else None

    for path in iter_text_files(root):
        relative = str(path.relative_to(root))
        seen.add(_path_key(relative))
        text = path.read_text(encoding="utf-8", errors="ignore")

        categories = None
        if _policy_skips(relative, sources, ("external",)):
            categories = _CATEGORIES_WITHOUT_MACHINE_PATH
            if skipped is not None:
                skipped.append(relative)
        findings.extend(_pattern_findings(relative, text, categories))

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

    if all_files:
        for path, text in _other_text_files(root, seen):
            relative = str(path.relative_to(root))
            categories = PRECISE_CATEGORIES
            if _policy_skips(relative, sources, ("external", "generated")):
                categories = PRECISE_CATEGORIES - {"machine-path"}
                if skipped is not None:
                    skipped.append(relative)
            findings.extend(_pattern_findings(relative, text, categories))

    findings.extend(integration_findings(root))
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


def _mcp_server_configs(project: Path) -> list[tuple[str, str, dict[str, Any], str]]:
    """Return ``(host, id, raw configuration, source)`` for each project MCP server."""
    servers: list[tuple[str, str, dict[str, Any], str]] = []

    def parse_json_config(path: Path, host: str) -> None:
        if not path.exists():
            return

        data = read_json(path) or {}
        mapping = data.get("mcpServers") or data.get("servers") or {}

        if isinstance(mapping, dict):
            for server_id, config in mapping.items():
                if isinstance(config, dict):
                    servers.append((host, str(server_id), config, str(path.relative_to(project))))

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
                    servers.append(("codex", str(server_id), config, str(codex.relative_to(project))))

    return servers


def collect_mcp_inventory(project: Path) -> dict[str, Any]:
    return {
        "schema-version": 1,
        "servers": [
            _redacted_server(host, server_id, config, source)
            for host, server_id, config, source in _mcp_server_configs(project)
        ],
    }


INTEGRATIONS_CONFIG = Path(".embraion") / "integrations.yaml"
# A drive, UNC, or root-anchored path at the start of a value or after `=`, whitespace, or a comma.
_ABSOLUTE_PATH = re.compile(r"(?:^|[=\s,])(?:/|[A-Za-z]:[\\/]|\\\\)")


def _integration_finding(kind: str, host: str, server_id: str, message: str, path: str) -> dict[str, str]:
    return {
        "schema-version": 1,
        "id": f"integration-{kind}:{host}:{server_id}",
        "severity": "high",
        "category": "integration-drift",
        "message": message,
        "path": path,
    }


def _observed_shape(config: dict[str, Any]) -> dict[str, Any]:
    command = config.get("command")
    args = config.get("args")
    environment = config.get("env") or config.get("environment") or {}
    transport = config.get("type") or config.get("transport")
    if not isinstance(transport, str):
        # Hosts default a command server to stdio and a URL server to HTTP.
        transport = "stdio" if isinstance(command, str) else "http" if config.get("url") else None
    return {
        "command": command if isinstance(command, str) else None,
        "args": [str(item) for item in args] if isinstance(args, list) else [],
        "transport": transport,
        "env-vars": sorted(str(key) for key in environment) if isinstance(environment, dict) else [],
        # Only Codex carries these keys; a declaration may set them for Codex alone.
        "cwd": config.get("cwd"),
        "required": config.get("required", False),
    }


# Optional declaration fields compared only when the declaration sets them.
_OPTIONAL_FIELDS = ("cwd", "required")


def _declared_shape(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": entry.get("command"),
        "args": list(entry.get("args") or []),
        "transport": entry["transport"],
        "env-vars": sorted(entry["env-vars"]),
        **{field: entry[field] for field in _OPTIONAL_FIELDS if field in entry},
    }


def _difference(field: str, expected: Any, actual: Any) -> str:
    if field == "args":
        # Argument values can carry credentials in any form, so only their shape is reported.
        position = next((index for index, pair in enumerate(zip(expected, actual), start=1) if pair[0] != pair[1]),
                        min(len(expected), len(actual)) + 1)
        return (f"args: expected {len(expected)} value(s), observed {len(actual)} value(s), "
                f"first difference at position {position}")
    return f"{field}: expected {redact_text(json.dumps(expected))}, observed {redact_text(json.dumps(actual))}"


def integration_findings(project: Path) -> list[dict[str, str]]:
    """Compare declared MCP integrations with observed project configuration.

    No declaration file means no expectations and no findings. Once a project declares
    integrations, missing, unexpected, and mismatched servers, an invalid declaration, and
    unreadable host configuration are high-severity findings, so the scan fails closed.
    """
    path = project / INTEGRATIONS_CONFIG
    relative = INTEGRATIONS_CONFIG.as_posix()
    if not path.is_file() and not path.is_symlink():
        return []

    def invalid(message: str) -> list[dict[str, str]]:
        return [_integration_finding("declaration", "project", "integrations", message, relative)]

    if path.is_symlink():
        return invalid("Integration declarations must not be a symbolic link")
    try:
        data = read_yaml(path)
    except Exception:
        return invalid("Integration declarations are not valid YAML")
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(read_json(framework_root() / "schemas" / "integrations.schema.json"))
    # Schema messages can echo declared values, so only the locations are reported.
    locations = sorted({".".join(str(part) for part in error.absolute_path) or "<root>"
                        for error in validator.iter_errors(data)})
    if locations:
        return invalid("Invalid integration declarations at: " + ", ".join(locations))

    declared: dict[tuple[str, str], dict[str, Any]] = {}
    findings: list[dict[str, str]] = []
    for entry in data["servers"]:
        key = (entry["host"], entry["id"])
        if key in declared:
            findings.extend(invalid(f"Integration {key[1]} is declared twice for host {key[0]}"))
        declared[key] = entry
        if entry.get("portable", True):
            where = [name for name, values in (
                ("command or arguments", [entry.get("command") or "", *(entry.get("args") or [])]),
                ("working directory", [entry.get("cwd") or ""]),
            ) if any(_ABSOLUTE_PATH.search(value) for value in values)]
            if where:
                findings.append(_integration_finding(
                    "non-portable", key[0], key[1],
                    f"Portable integration declares a machine-absolute path in its {' and '.join(where)}", relative,
                ))

    try:
        observed = _mcp_server_configs(project)
    except Exception:
        return findings + invalid("Observed MCP configuration could not be read; integration state is unknown")

    seen: set[tuple[str, str]] = set()
    for host, server_id, config, source in observed:
        # In Codex, `enabled = false` only switches a server off, such as one inherited from
        # user-level configuration, so it is not a server the project runs. Other hosts have no
        # such per-server key, so their entries are always compared.
        if host == "codex" and config.get("enabled") is False:
            continue
        key = (host, server_id)
        seen.add(key)
        entry = declared.get(key)
        if entry is None:
            findings.append(_integration_finding(
                "unexpected", host, server_id, f"Undeclared MCP server {server_id} for host {host}", source,
            ))
            continue
        expected, actual = _declared_shape(entry), _observed_shape(config)
        fields = [field for field in ("command", "args", "transport", "env-vars", *_OPTIONAL_FIELDS)
                  if field in expected and expected[field] != actual[field]]
        if fields:
            details = "; ".join(_difference(field, expected[field], actual[field]) for field in fields)
            findings.append(_integration_finding(
                "mismatch", host, server_id, f"MCP server {server_id} for host {host} differs from its declaration: {details}",
                source,
            ))

    for host, server_id in sorted(set(declared) - seen):
        # A machine-local server exists only where it is set up, such as an ignored local settings
        # file; its absence elsewhere (a clean clone, CI) is expected, but any copy found is compared.
        if not declared[(host, server_id)].get("portable", True):
            continue
        findings.append(_integration_finding(
            "missing", host, server_id, f"Declared MCP server {server_id} for host {host} is not configured", relative,
        ))
    return findings


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
