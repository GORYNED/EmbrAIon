from __future__ import annotations

import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embraion.common import read_yaml, write_yaml
from embraion.project import init_project
from embraion.security import redact_text
from embraion import project_validation, validation_process
from embraion.validation_output import capture_stream, render_output, truncation_marker
from embraion.project_validation import (
    MAX_CAPTURE_CHARS,
    MAX_CLEAN_TREE_PATHS,
    run_validation_profile,
    validation_profile_specs,
)


def _python(statement: str) -> str:
    return f'"{sys.executable}" -c "{statement}"'


def _remove_tree(path: Path) -> None:
    """Remove a tree whose files may be read-only, as Git object files are on Windows."""
    def make_writable_and_retry(function, target, _error):  # noqa: ANN001
        os.chmod(target, stat.S_IWRITE)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=make_writable_and_retry)


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

    def test_every_optional_command_blocked_is_skipped_never_a_pass(self) -> None:
        # Changed with the lead's approval: a profile whose commands are all optional
        # and none passed used to be "passed"; it now proves nothing and is "skipped".
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": "x", "required": False, "requires": {"env": ["EMBRAION_ABSENT_VARIABLE"]}}],
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EMBRAION_ABSENT_VARIABLE", None)
                record = run_validation_profile("gate", project=project)
            self.assertEqual("skipped", record["status"])
            self.assertEqual(1, record["warnings"])
            self.assertEqual("every command is optional and none passed", record["skip-reason"])
            self.assertNotIn("failure-reasons", record)

    def test_all_optional_profile_passes_when_one_command_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [
                    {"command": "x", "required": False, "requires": {"env": ["EMBRAION_ABSENT_VARIABLE"]}},
                    {"command": _python("print(1)"), "required": False},
                ],
            )
            os.environ.pop("EMBRAION_ABSENT_VARIABLE", None)
            record = run_validation_profile("gate", project=project)
            self.assertEqual("passed", record["status"])
            self.assertNotIn("skip-reason", record)

    def test_all_optional_profile_with_only_failures_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                [{"command": _python("import sys; sys.exit(3)"), "required": False}],
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("skipped", record["status"])
            self.assertEqual("failed", record["commands"][0]["status"])

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
            _remove_tree(project / ".git")
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


class BoundedOutputTests(unittest.TestCase):
    def test_capture_without_a_limit_or_within_it_keeps_everything(self) -> None:
        for limit in (None, 100, 12):
            with self.subTest(limit=limit):
                captured = capture_stream(io.BytesIO(b"one\ntwo\nlast"), limit, "utf-8")
                self.assertFalse(captured.truncated)
                self.assertEqual("one\ntwo\nlast", captured.head)
                self.assertEqual("", captured.tail)
                self.assertEqual((12, 3), (captured.total_bytes, captured.total_lines))

    def test_empty_stream(self) -> None:
        captured = capture_stream(io.BytesIO(b""), 10, "utf-8")
        self.assertEqual(("", "", 0, 0), (captured.head, captured.tail, captured.total_bytes, captured.total_lines))

    def test_capture_cuts_head_and_tail_on_line_boundaries_and_counts_the_rest(self) -> None:
        lines = [f"line-{number:03}\n" for number in range(100)]
        data = "".join(lines).encode("utf-8")
        captured = capture_stream(io.BytesIO(data), 100, "utf-8")
        self.assertTrue(captured.truncated)
        self.assertEqual((len(data), 100), (captured.total_bytes, captured.total_lines))
        self.assertTrue(captured.head.startswith("line-000\n"))
        self.assertTrue(captured.head.endswith("\n"))
        self.assertTrue(captured.tail.startswith("line-"))
        self.assertTrue(captured.tail.endswith("line-099\n"))
        self.assertLessEqual(len(captured.head), 50)
        self.assertLessEqual(len(captured.tail), 50)
        kept = captured.head.count("\n") + captured.tail.count("\n")
        self.assertEqual(100 - kept, captured.omitted_lines)
        self.assertEqual(len(data) - len(captured.head) - len(captured.tail), captured.omitted_bytes)

    def test_capture_of_a_single_long_line_still_bounds_memory(self) -> None:
        captured = capture_stream(io.BytesIO(b"x" * 10_000), 100, "utf-8")
        self.assertTrue(captured.truncated)
        self.assertEqual(100, len(captured.head) + len(captured.tail))
        self.assertEqual((10_000, 1), (captured.total_bytes, captured.total_lines))

    def test_render_marks_the_cut_and_scrubs_each_part(self) -> None:
        data = ("secret-a\n" + "filler\n" * 200 + "secret-b\n").encode("utf-8")
        captured = capture_stream(io.BytesIO(data), 200, "utf-8")
        text = render_output(captured, lambda value: value.replace("secret", "gone"))
        self.assertTrue(text.startswith("gone-a\n"))
        self.assertTrue(text.endswith("gone-b\n"))
        self.assertIn(truncation_marker(captured), text)
        self.assertNotIn("secret", text)

    def test_default_run_keeps_the_full_log_and_reports_totals_for_long_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            statement = f"print('x' * {MAX_CAPTURE_CHARS * 2})"
            project = _project(temporary, [_python(statement)])
            record = run_validation_profile("gate", project=project)
            row = record["commands"][0]
            self.assertIn("...<truncated>", row["stdout"])
            self.assertEqual(MAX_CAPTURE_CHARS, len(row["stdout-head"]))
            self.assertEqual(
                {"stdout": {"bytes": MAX_CAPTURE_CHARS * 2 + len(os.linesep), "lines": 1, "log-truncated": False}},
                row["output"],
            )
            self.assertNotIn("stderr-head", row)
            self.assertNotIn("output-limit-bytes", record)
            log = (project / row["log-path"]).read_text(encoding="utf-8")
            self.assertIn("x" * (MAX_CAPTURE_CHARS * 2), log)

    def test_short_output_adds_no_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [_python("print('short')")])
            row = run_validation_profile("gate", project=project)["commands"][0]
            self.assertEqual(
                {"index", "command", "status", "exit-code", "duration-ms", "timeout-seconds",
                 "log-path", "stdout", "stderr"},
                set(row),
            )

    def test_output_limit_bounds_the_log_and_keeps_head_tail_marker_and_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            body = (
                "print('first token=' + 'abcdefgh' + '12345678')\n"
                "for n in range(20000):\n"
                "    print(f'filler line {n}')\n"
                "print('last token=' + 'abcdefgh' + '12345678')\n"
            )
            (Path(temporary) / "emit.py").write_text(body, encoding="utf-8")
            project = _project(
                temporary,
                {"commands": [f'"{sys.executable}" {Path(temporary) / "emit.py"}'], "output-limit-bytes": 4096},
            )
            record = run_validation_profile("gate", project=project)
            row = record["commands"][0]
            self.assertEqual("passed", record["status"])
            self.assertEqual(4096, record["output-limit-bytes"])
            log = (project / row["log-path"]).read_text(encoding="utf-8")
            self.assertLess(len(log), 4096 + 512)
            self.assertIn("first token=<REDACTED>", log)
            self.assertIn("last token=<REDACTED>", log)
            self.assertNotIn("abcdefgh" + "12345678", log)
            self.assertIn("[... output truncated:", log)
            self.assertIn("filler line 19999", log)
            self.assertNotIn("filler line 10000", log)
            summary = row["output"]["stdout"]
            self.assertTrue(summary["log-truncated"])
            self.assertEqual(20002, summary["lines"])
            self.assertIn("[... output truncated:", row["stdout"])

    def test_output_limit_never_keeps_half_of_a_private_key_block(self) -> None:
        begin, end = "-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"
        data = (
            "lead\n" * 20 + begin + "\n" + "KEYBODYAAAA\n" * 50
            + "filler\n" * 400
            + "KEYBODYZZZZ\n" * 50 + end + "\n" + "trail\n" * 20
        ).encode("utf-8")
        captured = capture_stream(io.BytesIO(data), 600, "utf-8")
        self.assertTrue(captured.truncated)
        text = render_output(captured, redact_text)
        self.assertNotIn("KEYBODY", text)
        self.assertIn("lead\n", text)
        self.assertTrue(text.endswith("trail\n"))
        self.assertIn(truncation_marker(captured), text)

    def test_complete_key_block_inside_the_kept_head_is_left_for_redaction(self) -> None:
        block = "-----BEGIN PRIVATE KEY-----\nKEYBODY\n-----END PRIVATE KEY-----\n"
        data = (block + "filler\n" * 500).encode("utf-8")
        captured = capture_stream(io.BytesIO(data), 600, "utf-8")
        self.assertIn("-----END PRIVATE KEY-----", captured.head)
        self.assertNotIn("KEYBODY", render_output(captured, redact_text))

    def test_invalid_output_limit_fails_closed(self) -> None:
        for value in (0, 1023, -5, 1.5, "big", True):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                project = _project(temporary, {"commands": [_python("print(1)")], "output-limit-bytes": value})
                with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/validation.yaml"):
                    run_validation_profile("gate", project=project)


class FakeProcess:
    pid = 4242

    def __init__(self) -> None:
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = 1

    def wait(self, timeout=None):
        self.returncode = 1 if self.returncode is None else self.returncode
        return self.returncode


class WindowsTerminationLogicTests(unittest.TestCase):
    """The Windows branch is exercised with fake process tables on every platform."""

    def _completed(self, output: str, returncode: int = 0) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess([], returncode, stdout=output.encode("utf-8"))

    def test_descendants_are_found_from_the_process_table(self) -> None:
        table = "10,1\n11,10\n12,11\n13,1\nnoise\n4242,1\n"
        with mock.patch.object(validation_process.subprocess, "run", return_value=self._completed(table)):
            self.assertEqual([11, 12], validation_process.windows_descendants(10))
            self.assertEqual([], validation_process.windows_descendants(12))

    def test_unreadable_process_table_is_none(self) -> None:
        with mock.patch.object(validation_process.subprocess, "run", return_value=self._completed("", 1)):
            self.assertIsNone(validation_process.windows_descendants(10))
        with mock.patch.object(validation_process.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(validation_process.windows_descendants(10))
        with mock.patch.object(validation_process.subprocess, "run", return_value=self._completed("garbage\n")):
            self.assertIsNone(validation_process.windows_descendants(10))

    def test_tasklist_answer_decides_whether_a_pid_is_alive(self) -> None:
        listed = '"python.exe","11","Console","1","10,000 K"\n'
        with mock.patch.object(validation_process.subprocess, "run", return_value=self._completed(listed)):
            self.assertTrue(validation_process.windows_pid_alive(11))
            self.assertFalse(validation_process.windows_pid_alive(12))
        none = "INFO: No tasks are running which match the specified criteria.\n"
        with mock.patch.object(validation_process.subprocess, "run", return_value=self._completed(none)):
            self.assertFalse(validation_process.windows_pid_alive(11))
        with mock.patch.object(validation_process.subprocess, "run", return_value=self._completed("", 1)):
            self.assertTrue(validation_process.windows_pid_alive(11))
        with mock.patch.object(validation_process.subprocess, "run", side_effect=OSError):
            self.assertTrue(validation_process.windows_pid_alive(11))

    def _terminate(self, descendants, alive_answers) -> bool:
        answers = iter(alive_answers)
        calls: list[list[str]] = []

        def run(command, **options):
            calls.append(command)
            return self._completed("")

        process = FakeProcess()
        with mock.patch.object(validation_process, "windows_descendants", return_value=descendants), \
             mock.patch.object(validation_process, "windows_pid_alive", side_effect=lambda pid: next(answers, False)), \
             mock.patch.object(validation_process.subprocess, "run", side_effect=run), \
             mock.patch.object(validation_process, "POLL_SECONDS", 0.01), \
             mock.patch.object(validation_process, "VERIFY_SECONDS", 0.2):
            confirmed = validation_process._terminate_windows(process)
        self.assertEqual(["taskkill", "/T", "/F", "/PID", "4242"], calls[0])
        self.assertTrue(process.killed)
        return confirmed

    def test_termination_is_confirmed_when_every_descendant_is_gone(self) -> None:
        self.assertTrue(self._terminate([11, 12], [True, True, False, False]))
        self.assertTrue(self._terminate([], []))

    def test_termination_is_unconfirmed_for_a_surviving_or_unlisted_tree(self) -> None:
        self.assertFalse(self._terminate([11], [True] * 1000))
        self.assertFalse(self._terminate(None, []))


@unittest.skipUnless(os.name == "posix", "process groups are checked with POSIX signals")
class PosixGroupTests(unittest.TestCase):
    def test_group_membership_is_seen_and_a_reaped_group_is_gone(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            self.assertTrue(validation_process.group_has_live_members(process.pid))
        finally:
            self.assertTrue(validation_process.terminate_tree(process))
        self.assertFalse(validation_process.group_has_live_members(process.pid))

    def test_a_member_that_keeps_running_leaves_termination_unconfirmed(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            with mock.patch.object(validation_process, "group_has_live_members", return_value=True), \
                 mock.patch.object(validation_process, "VERIFY_SECONDS", 0.2), \
                 mock.patch.object(validation_process, "POLL_SECONDS", 0.02):
                self.assertFalse(validation_process.terminate_tree(process))
        finally:
            validation_process._kill_group(process.pid)
            process.wait()


class TerminationRecordTests(unittest.TestCase):
    def _slow(self) -> str:
        return _python("import time; time.sleep(5)")

    def test_a_timeout_records_confirmed_termination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, {"commands": [self._slow()], "timeout-seconds": 0.5})
            record = run_validation_profile("gate", project=project)
            row = record["commands"][0]
            self.assertEqual("timed-out", row["status"])
            self.assertEqual("confirmed", row["termination"])
            self.assertEqual("failed", record["status"])
            self.assertNotIn("failure-reasons", record)

    def test_commands_that_finish_in_time_record_no_termination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [_python("print(1)")])
            self.assertNotIn("termination", run_validation_profile("gate", project=project)["commands"][0])

    def test_unconfirmed_termination_fails_the_profile_even_for_an_optional_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(
                temporary,
                {
                    "commands": [{"command": self._slow(), "required": False}, _python("print('later')")],
                    "timeout-seconds": [0.5, None],
                },
            )

            def ended_but_unproven(process: object) -> bool:
                validation_process.terminate_tree(process)
                return False

            with mock.patch.object(project_validation, "_terminate_tree", side_effect=ended_but_unproven):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("unconfirmed", record["commands"][0]["termination"])
            self.assertEqual(1, len(record["commands"]))
            self.assertEqual(2, record["command-count"])
            self.assertIn("could not be confirmed terminated", record["failure-reasons"][0])
            self.assertIn("command 1", record["failure-reasons"][0])


if __name__ == "__main__":
    unittest.main()
