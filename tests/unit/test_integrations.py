from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from embraion.cli import build_parser
from embraion.common import write_yaml
from embraion.security import collect_findings, integration_findings


SECRET = "abcdefgh" + "12345678"


def _scan(root: Path) -> int:
    args = build_parser().parse_args(["security", "scan", "--path", str(root)])
    return int(args.func(args))


def _declaration(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": "docs",
        "host": "generic",
        "command": "npx",
        "args": ["-y", "docs-server"],
        "transport": "stdio",
        "access": "read-only",
        "env-vars": ["DOCS_TOKEN"],
    }
    entry.update(overrides)
    return entry


class DeclaredIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        (self.root / ".embraion").mkdir()

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _observe(self, servers: dict[str, object]) -> None:
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")

    def _declare(self, *entries: dict[str, object]) -> None:
        write_yaml(self.root / ".embraion/integrations.yaml", {"schema-version": 1, "servers": list(entries)})

    def _kinds(self) -> set[tuple[str, str]]:
        return {(item["id"].split(":", 1)[0], item["severity"]) for item in integration_findings(self.root)}

    def test_without_declarations_nothing_is_checked(self) -> None:
        self._observe({"anything": {"command": "/opt/tool", "env": {"KEY": SECRET}}})
        self.assertEqual([], integration_findings(self.root))
        self.assertFalse([item for item in collect_findings(self.root) if item["category"] == "integration-drift"])

    def test_matching_declarations_pass_across_hosts(self) -> None:
        self._observe({"docs": {"command": "npx", "args": ["-y", "docs-server"], "env": {"DOCS_TOKEN": SECRET}}})
        (self.root / ".codex").mkdir()
        (self.root / ".codex/config.toml").write_text(
            '[mcp_servers.search]\nurl = "https://search.example/mcp"\n', encoding="utf-8",
        )
        self._declare(
            _declaration(),
            _declaration(id="search", host="codex", command=None, args=[], transport="http", **{"env-vars": []}),
        )
        # An explicit null command is invalid; a URL server omits the command instead.
        self.assertIn(("integration-declaration", "high"), self._kinds())
        self._declare(
            _declaration(),
            {"id": "search", "host": "codex", "transport": "http", "access": "external-execution", "env-vars": []},
        )
        self.assertEqual([], integration_findings(self.root))

    def test_missing_unexpected_and_mismatched_servers_fail_closed(self) -> None:
        self._observe({
            "docs": {"command": "uvx", "args": ["docs-server", f"--token={SECRET}"], "type": "sse",
                     "env": {"OTHER": SECRET}},
            "extra": {"command": "npx"},
        })
        self._declare(_declaration(), _declaration(id="absent"))
        findings = integration_findings(self.root)
        by_kind = {item["id"]: item for item in findings}
        self.assertEqual(
            {"integration-mismatch:generic:docs", "integration-unexpected:generic:extra",
             "integration-missing:generic:absent"},
            set(by_kind),
        )
        self.assertTrue(all(item["severity"] == "high" and item["category"] == "integration-drift"
                            for item in findings))
        mismatch = by_kind["integration-mismatch:generic:docs"]["message"]
        for field in ("command:", "transport:", "env-vars:"):
            self.assertIn(field, mismatch)
        self.assertIn("args: expected 2 value(s), observed 2 value(s), first difference at position 1", mismatch)
        self.assertNotIn("docs-server", mismatch)
        self.assertNotIn(SECRET, json.dumps(findings))
        self.assertEqual(".mcp.json", by_kind["integration-unexpected:generic:extra"]["path"])
        self.assertEqual(".embraion/integrations.yaml", by_kind["integration-missing:generic:absent"]["path"])

    def test_invalid_declaration_never_echoes_values(self) -> None:
        self._observe({})
        self._declare(_declaration(**{"env-vars": [f"DOCS_TOKEN={SECRET}"]}))
        findings = integration_findings(self.root)
        self.assertEqual(["integration-declaration:project:integrations"], [item["id"] for item in findings])
        self.assertIn("servers.0.env-vars.0", findings[0]["message"])
        self.assertNotIn(SECRET, json.dumps(findings))

        self._declare(_declaration(), _declaration())
        self._observe({"docs": {"command": "npx", "args": ["-y", "docs-server"], "env": {"DOCS_TOKEN": "x"}}})
        self.assertEqual({("integration-declaration", "high")}, self._kinds())

    def test_portable_declarations_reject_machine_absolute_paths(self) -> None:
        for command, args in (("/usr/local/bin/docs", []), ("npx", ["--root=C:\\work"]), ("npx", ["\\\\share\\docs"])):
            with self.subTest(command=command, args=args):
                self._observe({"docs": {"command": command, "args": args, "env": {"DOCS_TOKEN": "x"}}})
                self._declare(_declaration(command=command, args=args))
                self.assertEqual({("integration-non-portable", "high")}, self._kinds())
                self._declare(_declaration(command=command, args=args, portable=False))
                self.assertEqual([], integration_findings(self.root))
        self._observe({"docs": {"command": "npx", "args": ["./server", "https://docs.example/x"],
                                "env": {"DOCS_TOKEN": "x"}}})
        self._declare(_declaration(args=["./server", "https://docs.example/x"]))
        self.assertEqual([], integration_findings(self.root))

    def test_machine_local_declarations_are_not_missing_where_unconfigured(self) -> None:
        self._observe({})
        self._declare(_declaration(command="/opt/local/docs", portable=False))
        self.assertEqual([], integration_findings(self.root))
        self._observe({"docs": {"command": "/opt/other/docs", "args": [], "env": {"DOCS_TOKEN": "x"}}})
        self.assertEqual({("integration-mismatch", "high")}, self._kinds())
        self._declare(_declaration(command="npx"))
        self._observe({})
        self.assertEqual({("integration-missing", "high")}, self._kinds())

    def test_disabled_entries_are_not_running_servers(self) -> None:
        (self.root / ".codex").mkdir()
        (self.root / ".codex/config.toml").write_text(
            '[mcp_servers.legacy]\nenabled = false\n', encoding="utf-8"
        )
        self._observe({})
        self._declare(_declaration())
        self.assertEqual({("integration-missing", "high")}, self._kinds())
        self._observe({"docs": {"command": "npx", "args": ["-y", "docs-server"], "env": {"DOCS_TOKEN": "x"}}})
        self.assertEqual([], integration_findings(self.root))
        self._declare(_declaration(), _declaration(id="legacy", host="codex"))
        self.assertEqual({("integration-missing", "high")}, self._kinds())

    def test_enabled_key_is_ignored_outside_codex(self) -> None:
        self._declare(_declaration())
        self._observe({
            "docs": {"command": "npx", "args": ["-y", "docs-server"], "env": {"DOCS_TOKEN": "x"}},
            "extra": {"command": "npx", "args": ["extra-server"], "enabled": False},
        })
        self.assertEqual({("integration-unexpected", "high")}, self._kinds())

    def _observe_codex(self, text: str) -> None:
        (self.root / ".codex").mkdir(exist_ok=True)
        (self.root / ".codex/config.toml").write_text(text, encoding="utf-8")

    def _codex_declaration(self, **overrides: object) -> dict[str, object]:
        return _declaration(host="codex", **overrides)

    def test_omitted_cwd_and_required_are_not_compared(self) -> None:
        self._observe_codex(
            '[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs-server"]\ncwd = "tools/docs"\n'
            'required = true\nenv = { DOCS_TOKEN = "x" }\n'
        )
        self._declare(self._codex_declaration())
        self.assertEqual([], integration_findings(self.root))

    def test_codex_cwd_is_compared_when_declared(self) -> None:
        self._declare(self._codex_declaration(cwd="tools/docs"))
        self._observe_codex(
            '[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs-server"]\ncwd = "tools/docs"\n'
            'env = { DOCS_TOKEN = "x" }\n'
        )
        self.assertEqual([], integration_findings(self.root))
        for observed in ('cwd = "tools/other"\n', ""):
            with self.subTest(observed=observed):
                self._observe_codex(
                    '[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs-server"]\n'
                    + observed + 'env = { DOCS_TOKEN = "x" }\n'
                )
                findings = integration_findings(self.root)
                self.assertEqual(["integration-mismatch:codex:docs"], [item["id"] for item in findings])
                self.assertEqual("high", findings[0]["severity"])
                self.assertEqual("integration-drift", findings[0]["category"])
                self.assertIn('cwd: expected "tools/docs", observed', findings[0]["message"])
                self.assertNotIn("required:", findings[0]["message"])

    def test_codex_required_is_compared_when_declared(self) -> None:
        base = '[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs-server"]\nenv = { DOCS_TOKEN = "x" }\n'
        self._declare(self._codex_declaration(required=True))
        self._observe_codex(base + "required = true\n")
        self.assertEqual([], integration_findings(self.root))
        for observed in ("required = false\n", ""):
            with self.subTest(observed=observed):
                self._observe_codex(base + observed)
                findings = integration_findings(self.root)
                self.assertEqual(["integration-mismatch:codex:docs"], [item["id"] for item in findings])
                self.assertIn("required: expected true, observed false", findings[0]["message"])
        # An absent key means not required, so declaring `required: false` matches it.
        self._declare(self._codex_declaration(required=False))
        self._observe_codex(base)
        self.assertEqual([], integration_findings(self.root))
        self._observe_codex(base + "required = true\n")
        self.assertEqual({("integration-mismatch", "high")}, self._kinds())

    def test_cwd_mismatch_does_not_print_credential_like_values(self) -> None:
        self._declare(self._codex_declaration(cwd="tools/docs"))
        self._observe_codex(
            '[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs-server"]\n'
            f'cwd = "token={SECRET}"\nenv = {{ DOCS_TOKEN = "x" }}\n'
        )
        self.assertNotIn(SECRET, json.dumps(integration_findings(self.root)))

    def test_disabled_codex_server_stays_skipped_with_cwd_and_required(self) -> None:
        self._observe_codex('[mcp_servers.docs]\nenabled = false\ncwd = "x"\nrequired = true\n')
        self._declare(self._codex_declaration(cwd="tools/docs", required=True))
        self.assertEqual({("integration-missing", "high")}, self._kinds())

    def test_cwd_and_required_are_codex_only_and_validated(self) -> None:
        self._observe({"docs": {"command": "npx", "args": ["-y", "docs-server"], "env": {"DOCS_TOKEN": "x"}}})
        for host in ("generic", "vscode", "claude-code"):
            for field, value in (("cwd", "tools/docs"), ("required", True)):
                with self.subTest(host=host, field=field):
                    self._declare(_declaration(host=host, **{field: value}))
                    findings = integration_findings(self.root)
                    self.assertEqual(["integration-declaration:project:integrations"], [item["id"] for item in findings])
                    self.assertIn(f"servers.0.{field}", findings[0]["message"])
        for field, value in (("cwd", ""), ("cwd", 7), ("required", "yes"), ("required", 1)):
            with self.subTest(field=field, value=value):
                self._declare(self._codex_declaration(**{field: value}))
                findings = integration_findings(self.root)
                self.assertEqual(["integration-declaration:project:integrations"], [item["id"] for item in findings])
                self.assertIn(f"servers.0.{field}", findings[0]["message"])

    def test_portable_declaration_rejects_machine_absolute_cwd(self) -> None:
        self._observe_codex(
            '[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs-server"]\ncwd = "/opt/docs"\n'
            'env = { DOCS_TOKEN = "x" }\n'
        )
        self._declare(self._codex_declaration(cwd="/opt/docs"))
        self.assertEqual({("integration-non-portable", "high")}, self._kinds())
        self._declare(self._codex_declaration(cwd="/opt/docs", portable=False))
        self.assertEqual([], integration_findings(self.root))

    def test_security_scan_fails_on_drift_and_passes_when_aligned(self) -> None:
        self._observe({"docs": {"command": "npx", "args": ["-y", "docs-server"], "env": {"DOCS_TOKEN": "x"}}})
        self._declare(_declaration())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, _scan(self.root))
        self._declare(_declaration(transport="http"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(1, _scan(self.root))
        self.assertIn("integration-drift", output.getvalue())

        (self.root / ".mcp.json").write_text("{not json", encoding="utf-8")
        self.assertEqual({("integration-declaration", "high")}, self._kinds())


if __name__ == "__main__":
    unittest.main()
