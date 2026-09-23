from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion import __version__
from embraion.common import framework_root, read_yaml
from embraion.evals import evaluate_case
from embraion.project import sync
from embraion.runtime import route
from embraion.security import collect_findings
from embraion.validation import collect_issues


class CoreTests(unittest.TestCase):
    def test_framework_validation_is_clean(self) -> None:
        issues = collect_issues(framework_root())
        errors = [item for item in issues if item["severity"] == "error"]
        self.assertEqual([], errors)

    def test_version_contract_is_aligned(self) -> None:
        root = framework_root()
        framework = read_yaml(root / "framework.yaml") or {}
        with (root / "pyproject.toml").open("rb") as handle:
            package = tomllib.load(handle)

        self.assertEqual(__version__, str(framework["version"]))
        self.assertEqual(__version__, str(package["project"]["version"]))

    def test_project_templates_track_framework_version(self) -> None:
        root = framework_root()
        framework = read_yaml(root / "framework.yaml") or {}
        expected = str(framework["version"])

        manifests = [
            root / "templates/project-overlay/.embraion/project.yaml",
            *sorted((root / "examples").glob("*/.embraion/project.yaml")),
        ]

        self.assertGreaterEqual(len(manifests), 4)
        for manifest in manifests:
            with self.subTest(manifest=manifest):
                data = read_yaml(manifest) or {}
                self.assertEqual(
                    "GORYNED/EmbrAIon",
                    data["framework"]["repository"],
                )
                self.assertEqual(expected, str(data["framework"]["version"]))

    def test_codex_confidential_route_is_explicit(self) -> None:
        result = route("codex", "strong", "CONFIDENTIAL")
        self.assertEqual("gpt-6-sol", result["model"])

    def test_claude_code_confidential_route_is_denied(self) -> None:
        with self.assertRaises(RuntimeError):
            route("claude-code", "strong", "CONFIDENTIAL")

    def test_sync_generates_all_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            generated = sync("all", output, force=True)
            self.assertEqual(4, len(generated))
            self.assertTrue((output / "codex/.codex/config.toml").is_file())
            self.assertTrue((output / "copilot/.github/agents/reviewer.agent.md").is_file())
            self.assertTrue((output / "claude-code/.claude/agents/reviewer.md").is_file())
            self.assertTrue((output / "portable/embraion/plugin.json").is_file())

    def test_security_scanner_detects_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = "a" * 24
            (root / "bad.txt").write_text(
                "api_key=" + secret,
                encoding="utf-8",
            )
            findings = collect_findings(root)
            self.assertTrue(any(item["severity"] == "high" for item in findings))

    def test_eval_checks_are_deterministic(self) -> None:
        case = {
            "checks": [
                {
                    "type": "changed-paths-within",
                    "field": "changed-paths",
                    "patterns-field": "owned-paths",
                }
            ]
        }
        passed, failures = evaluate_case(
            case,
            {
                "changed-paths": ["src/owned/a.cs"],
                "owned-paths": ["src/owned/**"],
            },
        )
        self.assertTrue(passed)
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
