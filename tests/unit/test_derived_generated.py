from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from embraion.bootstrap import plan_bootstrap
from embraion.cli import main
from embraion.common import read_json, read_yaml, write_json, write_yaml
from embraion.environment import child_environment
from embraion.policy import effective_policy, path_matches
from embraion.project import (
    CLAUDE_CORE_RULES, _projection_state_path, ignored_projection_outputs, init_project, install,
    projection_ledger_outputs,
)


class DerivedGeneratedSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="DerivedSources")

    def ledger(self, host: str, files: dict[str, str], destination: Path | None = None, **extra: object) -> Path:
        destination = destination or self.project
        path = _projection_state_path(self.project, host, destination)
        write_json(path, {"schema-version": 1, "host": host, "destination": str(destination),
                          "files": files, **extra})
        return path

    def test_ledger_outputs_extend_explicit_generated_sources(self) -> None:
        policy = read_yaml(self.project / ".embraion/policy.yaml")
        policy["sources"]["generated"] = ["build/**"]
        write_yaml(self.project / ".embraion/policy.yaml", policy)
        install("claude-code", self.project, components=["skills"])
        install("codex", self.project, components=["config"], config_mode="merge")
        nested = self.project / "nested"
        install("copilot", nested, components=["agents"])

        effective = effective_policy(self.project)
        generated = effective["sources"]["generated"]
        self.assertEqual("build/**", generated[0])
        self.assertIn(CLAUDE_CORE_RULES, generated)
        self.assertIn("nested/.github/agents/worker.agent.md", generated)
        # A merged file stays partly user-owned and is never classified as generated.
        self.assertNotIn(".codex/config.toml", generated)
        self.assertEqual(generated[1:], effective["derived-sources"]["generated"])
        self.assertEqual(sorted(read_json(_projection_state_path(self.project, "claude-code"))["files"]),
                         [path for path in projection_ledger_outputs(self.project) if path.startswith(".claude/")])

        install("codex", self.project, components=["config"], force=True)
        self.assertIn(".codex/config.toml", effective_policy(self.project)["sources"]["generated"])

    def test_only_intact_ownership_records_inside_the_project_count(self) -> None:
        self.ledger("claude-code", {".claude/agents/kept.md": "a" * 64, "../outside.md": "b" * 64})
        self.ledger("copilot", {"elsewhere.md": "c" * 64}, destination=self.project.parent / "other-destination")
        damaged = _projection_state_path(self.project, "codex")
        damaged.parent.mkdir(parents=True, exist_ok=True)
        damaged.write_text("{", encoding="utf-8")
        recovery = damaged.parent.parent / "portable.recovery.json"
        write_json(recovery, {"schema-version": 1, "host": "portable", "destination": str(self.project),
                              "files": {"embraion/recovered.md": "d" * 64}})
        self.assertEqual([".claude/agents/kept.md"], projection_ledger_outputs(self.project))

    def test_derived_patterns_match_paths_literally(self) -> None:
        self.ledger("claude-code", {".claude/skills/odd[1]*.md": "a" * 64})
        generated = effective_policy(self.project)["derived-sources"]["generated"]
        self.assertTrue(path_matches(".claude/skills/odd[1]*.md", generated))
        self.assertFalse(path_matches(".claude/skills/odd1-other.md", generated))

    def test_policy_show_counts_ledger_outputs(self) -> None:
        self.ledger("claude-code", {".claude/agents/one.md": "a" * 64, ".claude/agents/two.md": "b" * 64})
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            self.assertEqual(0, main(["policy", "show"]))
        self.assertIn("Sources generated: 2 pattern(s) (2 from projection ledgers)", output.getvalue())

    def test_bootstrap_does_not_bind_a_projection_output(self) -> None:
        (self.project / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
        self.assertEqual("CONTRIBUTING.md", self.slot("engineering-workflow"))
        self.ledger("claude-code", {"CONTRIBUTING.md": "a" * 64})
        plan = plan_bootstrap(self.project)
        self.assertIsNone(self.slot("engineering-workflow", plan))
        self.assertTrue(any("engineering-workflow source ownership requires review" in item
                            for item in plan["limitations"]))

    def slot(self, name: str, plan: dict | None = None) -> str | None:
        plan = plan or plan_bootstrap(self.project)
        change = next((item for item in plan["changes"] if item["path"] == ".embraion/knowledge.yaml"), None)
        return None if change is None else change["value"]["slots"].get(name)


class IgnoredProjectionOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="IgnoredOutputs")
        install("claude-code", self.project, components=["agents"])

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.project), *args], check=True, capture_output=True,
                       env=child_environment())

    def test_without_git_no_answer_is_reported(self) -> None:
        with patch("embraion.project.subprocess.run", side_effect=OSError("missing")):
            self.assertIsNone(ignored_projection_outputs(self.project))

    def test_ignored_outputs_are_reported_as_a_validate_warning(self) -> None:
        self.git("init", "-q")
        self.assertEqual([], ignored_projection_outputs(self.project))
        (self.project / ".gitignore").write_text(".claude/agents/*\n!.claude/agents/worker.md\n", encoding="utf-8")
        ignored = ignored_projection_outputs(self.project)
        self.assertIn(".claude/agents/reviewer.md", ignored)
        self.assertNotIn(".claude/agents/worker.md", ignored)

        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            code = main(["validate", "--json"])
        issues = [item for item in json.loads(output.getvalue())["issues"] if item["code"] == "projection-ignored"]
        self.assertEqual(1, len(issues))
        self.assertEqual("warning", issues[0]["severity"])
        self.assertEqual(ignored, issues[0]["paths"])
        self.assertEqual(0, code)


if __name__ == "__main__":
    unittest.main()
