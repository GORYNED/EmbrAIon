from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "embraion.cli", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _project(temporary: str, profile: object) -> Path:
    project = Path(temporary) / "project"
    project.mkdir()
    assert _run("init", ".", "--name", "RunnerSemantics", cwd=project).returncode == 0
    path = project / ".embraion" / "validation.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["profiles"]["gate"] = profile
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return project


def _python(statement: str) -> str:
    return f'"{sys.executable}" -c "{statement}"'


class ValidationRunnerCliTests(unittest.TestCase):
    def test_blocked_required_command_fails_the_run_and_is_explained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": "embraion-absent-tool", "requires": {"executables": ["embraion-absent-tool"]}}],
            )
            text = _run("validation", "run", "gate", cwd=project)
            self.assertEqual(1, text.returncode, text.stderr)
            self.assertIn("Status: failed", text.stdout)
            self.assertIn("[BLOCKED]", text.stdout)
            self.assertIn("reason: executable 'embraion-absent-tool' was not found on PATH", text.stdout)
            self.assertIn("Failure: command 1 is blocked", text.stdout)

            as_json = json.loads(_run("validation", "run", "gate", "--json", cwd=project).stdout)
            self.assertEqual("blocked", as_json["commands"][0]["status"])

    def test_optional_failure_keeps_exit_code_zero_and_shows_the_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": _python("raise SystemExit(4)"), "required": False}, _python("print(1)")],
            )
            result = _run("validation", "run", "gate", cwd=project)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("Status: passed", result.stdout)
            self.assertIn("[FAIL]", result.stdout)
            self.assertIn("optional: a failure here is a warning", result.stdout)
            self.assertIn("Warnings: 1 optional command(s) did not pass", result.stdout)

    def test_list_keeps_command_strings_for_mapping_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, {"commands": [{"command": "tool --check", "required": False}, "other"]})
            listed = json.loads(_run("validation", "list", "--json", cwd=project).stdout)
            self.assertEqual(["tool --check", "other"], listed["profiles"]["gate"]["commands"])
            self.assertEqual(2, listed["profiles"]["gate"]["command-count"])

    def test_unused_features_leave_the_record_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [_python("print(1)")])
            record = json.loads(_run("validation", "run", "gate", "--json", cwd=project).stdout)
            self.assertEqual(
                {"schema-version", "evidence-id", "evidence-path", "profile", "status", "command-count",
                 "executed-command-count", "fail-fast", "timeout-seconds", "run-id", "parameters",
                 "commands", "started-utc", "completed-utc"},
                set(record),
            )

    def test_unknown_key_in_a_command_mapping_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [{"command": "x", "optional": True}])
            result = _run("validation", "run", "gate", cwd=project)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Invalid .embraion/validation.yaml", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
