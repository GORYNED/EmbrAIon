from __future__ import annotations

import contextlib
import io
import os
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
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
        try:
            os.chmod(target, stat.S_IWRITE)
            function(target)
        except FileNotFoundError:
            # Git maintenance can remove a lock between enumeration and deletion.
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=make_writable_and_retry)


def _remove_terminated_child_project(path: Path) -> None:
    """Allow Windows to release a terminated child's cwd handle before fixture cleanup."""
    deadline = time.monotonic() + 5
    while True:
        try:
            _remove_tree(path)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


class TreeRemovalTests(unittest.TestCase):
    def test_file_disappearing_during_removal_is_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary) / "tree"
            tree.mkdir()
            (tree / "maintenance.lock").write_text("", encoding="utf-8")
            unlink = os.unlink

            def disappear(path, *args, **kwargs):
                unlink(path, *args, **kwargs)
                raise FileNotFoundError("lock disappeared during removal")

            with mock.patch("os.unlink", side_effect=disappear):
                _remove_tree(tree)
            self.assertFalse(tree.exists())


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
            self.assertEqual([], record["commands"])
            self.assertIn("clean-tree guard is blocked", record["failure-reasons"][0])

    def test_index_lock_blocks_before_running_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "open('generated.txt', 'w').write('x')")
            (project / ".git" / "index.lock").write_text("", encoding="utf-8")
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual([], record["commands"])
            self.assertEqual("blocked", record["clean-tree"]["status"])
            self.assertFalse((project / "generated.txt").exists())

    def test_head_change_is_detected_with_a_clean_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(
                temporary,
                "import subprocess; subprocess.run(["
                "'git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', "
                "'-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'advance'"
                "], check=True)",
            )
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertTrue(record["clean-tree"]["head-changed"])
            self.assertIn("HEAD changed", record["failure-reasons"][0])

    def test_inherited_git_dir_cannot_redirect_clean_tree_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._repository(temporary, "open('tracked.txt', 'w').write('changed again')")
            other = Path(temporary) / "other"
            other.mkdir()
            _git(other, "init", "-q")
            (other / "other.txt").write_text("other", encoding="utf-8")
            _git(other, "add", "-A")
            _git(other, "commit", "-q", "-m", "other")
            (project / "tracked.txt").write_text("changed", encoding="utf-8")
            expected_head = project_validation._git_output(project, "rev-parse", "--verify", "HEAD").strip()
            with mock.patch.dict(os.environ, {"GIT_DIR": str(other / ".git"),
                                              "GIT_WORK_TREE": str(other)}):
                snapshot = project_validation._tree_snapshot(project)
                head = project_validation._git_output(project, "rev-parse", "--verify", "HEAD").strip()
                record = run_validation_profile("gate", project=project)
            self.assertIn("tracked.txt", snapshot)
            self.assertEqual(expected_head, head)
            self.assertEqual("failed", record["status"])
            self.assertEqual(["tracked.txt"], record["clean-tree"]["changed-paths"])

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
                if arguments[-1] == "index.lock":
                    return str(project / ".git" / "index.lock").encode("utf-8")
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
        begin, end = "-----BEGIN " + "PRIVATE KEY-----", "-----END " + "PRIVATE KEY-----"
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
        begin, end = "-----BEGIN " + "PRIVATE KEY-----", "-----END " + "PRIVATE KEY-----"
        block = f"{begin}\nKEYBODY\n{end}\n"
        data = (block + "filler\n" * 500).encode("utf-8")
        captured = capture_stream(io.BytesIO(data), 600, "utf-8")
        self.assertIn(end, captured.head)
        self.assertNotIn("KEYBODY", render_output(captured, redact_text))

    def test_invalid_output_limit_fails_closed(self) -> None:
        for value in (0, 1023, -5, 1.5, "big", True):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                project = _project(temporary, {"commands": [_python("print(1)")], "output-limit-bytes": value})
                with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/validation.yaml"):
                    run_validation_profile("gate", project=project)


class FakeProcess:
    pid = 4242
    _handle = 100

    def __init__(self) -> None:
        self.killed = False
        self.returncode = None
        self.wait_timeout = None

    def poll(self):
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = 1

    def wait(self, timeout=None):
        self.wait_timeout = timeout
        self.returncode = 1 if self.returncode is None else self.returncode
        return self.returncode


class WindowsTerminationLogicTests(unittest.TestCase):
    """Native observations are modeled without depending on the test host OS."""

    class Api:
        def __init__(self, table=None, created=None, alive=None):
            self.table = table if table is not None else {4242: 1, 11: 4242, 12: 11}
            self.births = created if created is not None else {100: 10, 4242: 10, 11: 11, 12: 12}
            self.answers = iter(alive if alive is not None else [False, False])
            self.opened = []
            self.closed = []

        def snapshot(self):
            return self.table

        def open(self, pid):
            self.opened.append(pid)
            return pid

        def created(self, handle):
            return self.births[handle]

        def alive(self, handle):
            return next(self.answers, False)

        def close(self, handle):
            self.closed.append(handle)

    def _terminate(self, api, run=None, clock=None, root_exited=False):
        process = FakeProcess()
        if root_exited:
            process.returncode = 0
        command = []

        def taskkill(args, **options):
            command.append((args, options))
            if run is not None:
                return run(args, **options)
            return subprocess.CompletedProcess(args, 0)

        clock_patch = (mock.patch.object(validation_process.time, "monotonic", side_effect=clock)
                       if clock else contextlib.nullcontext())
        with mock.patch.object(validation_process, "_WindowsProcesses", return_value=api), \
             mock.patch.object(validation_process.subprocess, "run", side_effect=taskkill), \
             mock.patch.object(validation_process, "POLL_SECONDS", 0.001), \
             mock.patch.object(validation_process, "VERIFY_SECONDS", 0.02), \
             clock_patch:
            confirmed = validation_process._terminate_windows(process)
        self.assertEqual(["taskkill", "/T", "/F", "/PID", "4242"], command[0][0])
        self.assertLessEqual(command[0][1]["timeout"], 0.020001)
        self.assertLessEqual(process.wait_timeout, 0.020001)
        self.assertEqual(not root_exited, process.killed)
        self.assertEqual(sorted(api.opened), sorted(api.closed))
        self.wait_timeout = process.wait_timeout
        return confirmed

    def test_native_snapshot_and_held_handles_confirm_exited_tree(self) -> None:
        api = self.Api(alive=[True, False, False])
        self.assertTrue(self._terminate(api))
        self.assertEqual([11, 12], api.opened)
        self.assertTrue(self._terminate(self.Api(table={4242: 1}, created={100: 10, 4242: 10})))

    def test_snapshot_failure_is_unconfirmed_but_exited_root_can_be_confirmed(self) -> None:
        api = self.Api(table={11: 4242})
        self.assertTrue(self._terminate(api, root_exited=True))
        self.assertFalse(self._terminate(self.Api(table={})))
        api = self.Api()
        api.snapshot = mock.Mock(side_effect=OSError("snapshot failed"))
        self.assertFalse(self._terminate(api))

    def test_stale_parent_pid_is_rejected(self) -> None:
        stale = self.Api(created={100: 10, 4242: 10, 11: 9, 12: 12})
        self.assertTrue(self._terminate(stale))
        self.assertEqual([11], stale.opened)

    def test_pid_reuse_after_capture_does_not_change_held_handle_result(self) -> None:
        api = self.Api()
        api.snapshot = mock.Mock(side_effect=lambda: api.table)

        def reuse_pid(args, **options):
            api.table = {4242: 1, 11: 999, 12: 11}
            api.births[11] = 99
            return subprocess.CompletedProcess(args, 0)

        self.assertTrue(self._terminate(api, run=reuse_pid))
        api.snapshot.assert_called_once()

    def test_survivor_and_failed_wait_are_unconfirmed_with_handles_closed(self) -> None:
        self.assertFalse(self._terminate(self.Api(alive=[True] * 1000)))
        api = self.Api()
        api.alive = mock.Mock(side_effect=OSError("wait failed"))
        self.assertFalse(self._terminate(api))

    def test_failed_open_and_creation_probe_are_unconfirmed(self) -> None:
        api = self.Api()

        def denied(pid):
            if pid == 11:
                raise OSError("denied")
            api.opened.append(pid)
            return pid

        api.open = denied
        self.assertFalse(self._terminate(api))
        api = self.Api()

        def failed_creation(handle):
            if handle == 11:
                raise OSError("times failed")
            return api.births[handle]

        api.created = failed_creation
        self.assertFalse(self._terminate(api))

    def test_taskkill_timeout_still_kills_and_reaps_root(self) -> None:
        def timeout(args, **options):
            raise subprocess.TimeoutExpired(args, options["timeout"])

        self.assertFalse(self._terminate(self.Api(), run=timeout))

    def test_one_deadline_covers_taskkill_root_wait_and_descendants(self) -> None:
        seen = []

        def taskkill(args, **options):
            seen.append(options["timeout"])
            return subprocess.CompletedProcess(args, 1)

        self.assertTrue(self._terminate(self.Api(table={4242: 1}), run=taskkill,
                                        clock=iter([100.0, 100.01, 100.015]), root_exited=True))
        self.assertAlmostEqual(0.01, seen[0])
        self.assertAlmostEqual(0.005, self.wait_timeout)
        self.assertFalse(self._terminate(self.Api(), run=taskkill))
        self.assertFalse(self._terminate(self.Api(), run=taskkill, root_exited=True))


@unittest.skipUnless(os.name == "posix", "process groups are checked with POSIX signals")
class PosixGroupTests(unittest.TestCase):
    def test_detached_session_is_outside_the_supported_group(self) -> None:
        launcher = subprocess.Popen(
            [sys.executable, "-c",
             "import subprocess,sys; "
             "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
             "start_new_session=True,stdin=subprocess.DEVNULL,"
             "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
             "print(child.pid,flush=True)"],
            stdout=subprocess.PIPE, text=True, start_new_session=True,
        )
        child_pid = None
        try:
            child_pid = int(launcher.stdout.readline())
            self.assertEqual(0, launcher.wait(timeout=5))
            os.kill(child_pid, 0)  # The detached child is still running.
            self.assertFalse(validation_process.group_has_live_members(launcher.pid))
        finally:
            validation_process._kill_group(launcher.pid)
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if launcher.poll() is None:
                launcher.kill()
                launcher.wait()
            if launcher.stdout is not None:
                launcher.stdout.close()

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

    def test_termination_observation_error_records_incomplete_result_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, {
                "commands": [self._slow(), _python("print('later')")],
                "timeout-seconds": [0.2, None],
            })

            def raised_after_cleanup(process: object) -> bool:
                validation_process.terminate_tree(process)
                raise OSError("observation failed")

            with mock.patch.object(project_validation, "_terminate_tree", side_effect=raised_after_cleanup):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("unconfirmed", record["commands"][0]["termination"])
            self.assertEqual(1, record["executed-command-count"])
            self.assertEqual(2, record["command-count"])

    def test_normal_exit_with_unknown_containment_stops_before_the_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, {
                "commands": [{"command": _python("print('first')"), "required": False},
                             _python("print('later')")],
            })
            with mock.patch.object(project_validation, "containment_quiescent",
                                   side_effect=OSError("query failed")):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual(1, record["executed-command-count"])
            self.assertEqual("blocked", record["commands"][0]["status"])
            self.assertEqual("confirmed", record["commands"][0]["termination"])

    def test_normal_root_exit_with_child_fails_after_confirmed_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            command = _python(
                "import subprocess,sys; "
                "subprocess.Popen([sys.executable,'-c','import time; time.sleep(5)'],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
            )
            project = _project(temporary, [command])
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("failed", record["commands"][0]["status"])
            self.assertEqual("confirmed", record["commands"][0]["termination"])
            self.assertIn("descendants remained", record["commands"][0]["reason"])
            _remove_terminated_child_project(project)

    def test_optional_command_with_descendant_is_fail_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            command = _python(
                "import subprocess,sys; "
                "subprocess.Popen([sys.executable,'-c','import time; time.sleep(5)'],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
            )
            project = _project(temporary, {"commands": [
                {"command": command, "required": False}, _python("print('later')"),
            ]})
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual(1, record["executed-command-count"])
            self.assertEqual("confirmed", record["commands"][0]["termination"])
            self.assertIn("left descendants", record["failure-reasons"][0])

    def test_output_handle_that_does_not_close_stops_the_profile(self) -> None:
        released = threading.Event()

        class HeldStream:
            def read(self, _size: int) -> bytes:
                released.wait(5)
                return b""

            def close(self) -> None:
                pass

        process = FakeProcess()
        process.stdout = HeldStream()
        process.stderr = io.BytesIO()
        process.wait = lambda timeout=None: 0
        try:
            with tempfile.TemporaryDirectory() as temporary:
                project = _project(temporary, [_python("print('first')"), _python("print('later')")])
                with mock.patch.object(project_validation, "_spawn_contained", return_value=process), \
                     mock.patch.object(project_validation, "containment_quiescent", return_value=True), \
                     mock.patch.object(project_validation, "close_containment"), \
                     mock.patch.object(project_validation, "VERIFY_SECONDS", 0.05):
                    record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual(1, record["executed-command-count"])
            self.assertEqual("unconfirmed", record["commands"][0]["termination"])
            self.assertIn("output streams did not close", record["commands"][0]["reason"])
        finally:
            released.set()


@unittest.skipUnless(os.name == "nt", "Windows Job Object containment is Windows-specific")
class WindowsContainmentTests(unittest.TestCase):
    def test_assignment_failure_never_releases_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [_python("open('launched.txt','w').write('x')")])
            with mock.patch.object(validation_process._WindowsJob, "assign", side_effect=OSError("denied")):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("blocked", record["commands"][0]["status"])
            self.assertFalse((project / "launched.txt").exists())

    def test_assignment_failure_with_unreaped_bootstrap_records_unconfirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(temporary, [_python("print('never released')")])
            process = mock.Mock()
            process.stdin = io.BytesIO()
            process.stdout = io.BytesIO()
            process.stderr = io.BytesIO()
            process.poll.return_value = None
            process.kill.side_effect = OSError("cannot kill")
            job = mock.Mock()
            job.assign.side_effect = OSError("cannot assign")
            with mock.patch.object(validation_process, "_WindowsJob", return_value=job), \
                 mock.patch.object(validation_process.subprocess, "Popen", return_value=process):
                record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("unconfirmed", record["commands"][0]["termination"])
            self.assertEqual("blocked", record["commands"][0]["status"])

    def test_root_exit_with_detached_descendant_is_recovered_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            child = "import time; time.sleep(60)"
            command = _python(
                "import subprocess,sys; "
                f"subprocess.Popen([sys.executable,'-c','{child}'],"
                "creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
            )
            project = _project(temporary, [command])
            record = run_validation_profile("gate", project=project)
            self.assertEqual("failed", record["status"])
            self.assertEqual("failed", record["commands"][0]["status"])
            self.assertEqual("confirmed", record["commands"][0]["termination"])
            self.assertIn("descendants remained", record["commands"][0]["reason"])
            _remove_terminated_child_project(project)


if __name__ == "__main__":
    unittest.main()
