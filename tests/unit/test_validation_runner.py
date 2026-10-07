from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embraion.common import read_yaml, write_yaml
from embraion.project import init_project
from embraion import project_validation
from embraion.project_validation import (
    MAX_CLEAN_TREE_PATHS,
    run_validation_profile,
    validation_profile_specs,
)


def _python(statement: str) -> str:
    return f'"{sys.executable}" -c "{statement}"'


def _project(temporary: str, profile: object) -> Path:
    project = Path(temporary) / "project"
    project.mkdir()
    init_project(project, name="Consumer")
    path = project / ".embraion" / "validation.yaml"
    data = read_yaml(path)
    data["profiles"]["gate"] = profile
    write_yaml(path, data)
    return project


class BlockedAndOptionalCommandTests(unittest.TestCase):
    def test_plain_commands_keep_the_previous_record_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [_python("print(1)")])
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            for key in ("warnings", "failure-reasons"):
                self.assertNotIn(key, record)
            for key in ("required", "reason"):
                self.assertNotIn(key, record["commands"][0])
            spec = validation_profile_specs(project)["gate"]
            self.assertEqual([{"required": True, "requires": {}}], spec["entries"])

    def test_missing_executable_blocks_a_required_command_and_fails_the_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            command = "embraion-absent-tool --version"
            project = _project(
                temporary,
                [
                    {"command": command, "requires": {"executables": ["embraion-absent-tool"]}},
                    _python("print('later')"),
                ],
            )
            record = run_validation_profile("gate", project=project)
            first, second = record["commands"]
            self.assertEqual("failed", record["status"])
            self.assertEqual("blocked", first["status"])
            self.assertIsNone(first["exit-code"])
            self.assertIn("embraion-absent-tool", first["reason"])
            self.assertEqual("passed", second["status"])
            self.assertEqual(1, len(record["failure-reasons"]))
            self.assertIn("command 1 is blocked", record["failure-reasons"][0])
            log = (project / first["log-path"]).read_text(encoding="utf-8")
            self.assertIn("Not run:", log)

    def test_blocked_optional_command_is_a_warning_not_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                {
                    "commands": [
                        {
                            "command": "embraion-absent-tool",
                            "required": False,
                            "requires": {"executables": ["embraion-absent-tool"]},
                        },
                        _python("print('ok')"),
                    ]
                },
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertEqual(1, record["warnings"])
            self.assertEqual("blocked", record["commands"][0]["status"])
            self.assertIs(False, record["commands"][0]["required"])
            self.assertNotIn("failure-reasons", record)

    def test_every_optional_command_blocked_does_not_fail_the_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": "x", "required": False, "requires": {"env": ["EMBRAION_ABSENT_VARIABLE"]}}],
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EMBRAION_ABSENT_VARIABLE", None)
                record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertEqual(1, record["warnings"])

    def test_missing_environment_variable_blocks_and_present_variable_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": _python("print('ran')"), "requires": {"env": ["EMBRAION_TEST_TOKEN_NAME"]}}],
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EMBRAION_TEST_TOKEN_NAME", None)
                blocked = run_validation_profile("gate", project=project)
            self.assertEqual("blocked", blocked["commands"][0]["status"])
            self.assertIn("EMBRAION_TEST_TOKEN_NAME", blocked["commands"][0]["reason"])
            self.assertEqual("failed", blocked["status"])
            with mock.patch.dict(os.environ, {"EMBRAION_TEST_TOKEN_NAME": "1"}):
                ran = run_validation_profile("gate", project=project)
            self.assertEqual("passed", ran["status"])
            self.assertNotIn("failure-reasons", ran)

    def test_platform_list_blocks_other_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": _python("print(1)"), "requires": {"platforms": ["macos", "windows"]}}],
            )
            with mock.patch("embraion.project_validation._current_platform", return_value="linux"):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("blocked", record["commands"][0]["status"])
            self.assertIn("'linux'", record["commands"][0]["reason"])
            with mock.patch("embraion.project_validation._current_platform", return_value="macos"):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])

    def test_executable_found_on_path_is_not_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(sys.executable)
            project = _project(
                temporary,
                [{"command": _python("print(1)"), "requires": {"executables": [str(executable)]}}],
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])

    def test_optional_failure_and_timeout_are_recorded_but_do_not_fail_the_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                {
                    "commands": [
                        {"command": _python("raise SystemExit(3)"), "required": False},
                        {"command": _python("import time; time.sleep(30)"), "required": False},
                        _python("print('required')"),
                    ],
                    "timeout-seconds": [None, 0.5, None],
                },
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertEqual(2, record["warnings"])
            self.assertEqual(["failed", "timed-out", "passed"], [row["status"] for row in record["commands"]])
            self.assertEqual(3, record["commands"][0]["exit-code"])
            self.assertEqual(3, record["executed-command-count"])

    def test_required_failure_still_fails_next_to_optional_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [
                    {"command": _python("raise SystemExit(1)"), "required": False},
                    {"command": _python("raise SystemExit(2)")},
                ],
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual(1, record["warnings"])

    def test_fail_fast_ignores_optional_failures_and_stops_on_required_ones(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [
                    {"command": _python("raise SystemExit(1)"), "required": False},
                    {"command": "embraion-absent-tool", "requires": {"executables": ["embraion-absent-tool"]}},
                    _python("print('never')"),
                ],
            )
            record = run_validation_profile("gate", project=project, fail_fast=True)
            self.assertEqual("failed", record["status"])
            self.assertEqual(["failed", "blocked"], [row["status"] for row in record["commands"]])

    def test_invalid_declarations_fail_closed(self) -> None:
        invalid = [
            [{"command": "x", "unknown": True}],
            [{"required": True}],
            [{"command": "x", "required": "yes"}],
            [{"command": "x", "requires": {"platforms": ["plan9"]}}],
            [{"command": "x", "requires": {"platforms": []}}],
            [{"command": "x", "requires": {"executables": [""]}}],
            [{"command": "x", "requires": {"env": ["not valid"]}}],
            [{"command": "x", "requires": {"other": ["x"]}}],
            {"commands": [{"command": ""}]},
        ]
        for profile in invalid:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                project = _project(temporary, profile)
                with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/validation.yaml"):
                    run_validation_profile("gate", project=project)

    def test_structured_profile_keeps_parameters_with_mapping_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                {
                    "commands": [{"command": _python("import os; print(os.environ['EMBRAION_PARAM'])")}],
                    "parameters": {"value": {"environment": "EMBRAION_PARAM", "default": "seen"}},
                },
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertIn("<REDACTED:validation-parameter>", record["commands"][0]["stdout"])
            self.assertEqual(["value"], record["parameters"])


def _git(project: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *arguments],
        cwd=str(project),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _write_script(project: Path, body: str) -> str:
    (project / "act.py").write_text(body, encoding="utf-8")
    return f'"{sys.executable}" act.py'


@unittest.skipUnless(shutil.which("git"), "the clean-tree guard needs the git executable")
class CleanTreeGuardTests(unittest.TestCase):
    def _repository(self, temporary: str, body: str, **profile: object) -> Path:
        project = Path(temporary) / "project"
        project.mkdir()
        init_project(project, name="Consumer")
        command = _write_script(project, body)
        path = project / ".embraion" / "validation.yaml"
        data = read_yaml(path)
        data["profiles"]["gate"] = {"commands": [command], "clean-tree": True, **profile}
        write_yaml(path, data)
        (project / "tracked.txt").write_text("one\n", encoding="utf-8")
        _git(project, "init", "-q")
        _git(project, "add", "-A")
        _git(project, "commit", "-q", "-m", "base")
        return project

    def test_unchanged_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "print('read only')")
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertEqual(
                {"status": "passed", "baseline-dirty": False, "changed-count": 0, "changed-paths": []},
                record["clean-tree"],
            )
            self.assertEqual(0, record["warnings"])
            self.assertNotIn("failure-reasons", record)

    def test_new_untracked_file_fails_the_profile_with_a_distinct_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "open('generated.txt', 'w').write('x')")
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("passed", record["commands"][0]["status"])
            self.assertEqual("failed", record["clean-tree"]["status"])
            self.assertEqual(["generated.txt"], record["clean-tree"]["changed-paths"])
            self.assertIn("clean-tree guard failed", record["failure-reasons"][0])
            self.assertIn("generated.txt", record["failure-reasons"][0])

    def test_modified_tracked_file_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "open('tracked.txt', 'w').write('two\\n')")
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual(["tracked.txt"], record["clean-tree"]["changed-paths"])

    def test_dirty_baseline_fails_only_on_new_differences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "print('read only')")
            (project / "tracked.txt").write_text("edited before\n", encoding="utf-8")
            (project / "scratch.txt").write_text("untracked before\n", encoding="utf-8")
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertTrue(record["clean-tree"]["baseline-dirty"])
            self.assertEqual(0, record["clean-tree"]["changed-count"])

    def test_dirty_baseline_names_new_paths_and_further_edits_of_dirty_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            body = (
                "open('tracked.txt', 'a').write('more\\n'); "
                "open('created.txt', 'w').write('x')"
            )
            project = self._repository(temporary, body)
            (project / "tracked.txt").write_text("edited before\n", encoding="utf-8")
            (project / "scratch.txt").write_text("untracked before\n", encoding="utf-8")
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual(["created.txt", "tracked.txt"], record["clean-tree"]["changed-paths"])

    def test_changed_paths_are_capped_but_counted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            body = f"[open(f'file-{{n:03}}.txt', 'w').close() for n in range({MAX_CLEAN_TREE_PATHS + 5})]"
            project = self._repository(temporary, body)
            record = run_validation_profile("gate", project=project)
            block = record["clean-tree"]
            self.assertEqual(MAX_CLEAN_TREE_PATHS + 5, block["changed-count"])
            self.assertEqual(MAX_CLEAN_TREE_PATHS, len(block["changed-paths"]))
            self.assertIn("(and 5 more)", record["failure-reasons"][0])

    def test_outside_a_git_work_tree_the_guard_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "print('ok')")
            shutil.rmtree(project / ".git")
            with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(Path(temporary).parent)}):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("blocked", record["clean-tree"]["status"])
            self.assertEqual("failed", record["status"])
            self.assertEqual("passed", record["commands"][0]["status"])
            self.assertIn("clean-tree guard is blocked", record["failure-reasons"][0])

    def test_guard_is_off_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "open('generated.txt', 'w').write('x')", **{"clean-tree": False})
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertNotIn("clean-tree", record)
            self.assertNotIn("warnings", record)

    def test_invalid_clean_tree_value_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "print(1)", **{"clean-tree": "yes"})
            with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/validation.yaml"):
                run_validation_profile("gate", project=project)


class StatusParsingTests(unittest.TestCase):
    def test_nul_separated_status_handles_renames_spaces_and_the_evidence_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / ".embraion").mkdir()
            top = str(project.resolve()).encode("utf-8")
            status = (
                b"R  new name.txt\0old name.txt\0"
                b"?? other.txt\0"
                b"?? .embraion/state/validation/run-1/command-1.log\0"
            )

            def fake(root: Path, *arguments: str) -> bytes:
                return top if arguments[0] == "rev-parse" else status

            with mock.patch.object(project_validation, "_git_output", side_effect=fake):
                snapshot = project_validation._tree_snapshot(project)
            self.assertEqual({"new name.txt", "other.txt"}, set(snapshot))
            self.assertTrue(snapshot["new name.txt"].startswith("R |old name.txt|"))


if __name__ == "__main__":
    unittest.main()
