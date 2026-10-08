from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embraion.project_validation import _validate_command_request, run_validation_command
from embraion.validation_process import ContainmentUnavailable
from embraion.validation_output import CapturedOutput


def _request(cwd: Path, statement: str, **extra: object) -> dict[str, object]:
    return {
        "executable": sys.executable,
        "argv": ["-c", statement],
        "cwd": str(cwd),
        "timeout_seconds": 4,
        **extra,
    }


class ValidationCommandTests(unittest.TestCase):
    def test_exact_argv_and_secret_redaction_with_logs_outside_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cwd = root / "working"
            logs = root / "logs"
            cwd.mkdir()
            logs.mkdir()
            secret = "do-not-persist-" + "unique-secret"
            statement = (
                "import os,sys; print('argv-ok' if sys.argv[1]=='x & $(echo bad)' else 'argv-bad'); "
                "print(sys.argv[1]); print(os.environ['CHECK_SECRET'])"
            )
            request = _request(
                cwd, statement,
                argv=["-c", statement, "x & $(echo bad)"],
                env={"CHECK_SECRET": secret},
                stdout_path=str(logs / "stdout.log"), stderr_path=str(logs / "stderr.log"),
            )
            result = run_validation_command(request)
            self.assertTrue(result["succeeded"], result)
            self.assertTrue(result["safe-to-continue"])
            text = (logs / "stdout.log").read_text(encoding="utf-8")
            self.assertIn("argv-ok", text)
            self.assertNotIn("x & $(echo bad)", text)
            self.assertIn("[REDACTED]", text)
            self.assertNotIn(secret, text)
            self.assertNotIn(secret, json.dumps(result))
            self.assertNotIn("argv", result)

    def test_inherited_environment_value_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "stdout.log"
            inherited = "inherited-sensitive-" + "value-unique"
            with mock.patch.dict(os.environ, {"CHECK_INHERITED_SECRET": inherited}):
                result = run_validation_command(_request(
                    root, "import os; print(os.environ['CHECK_INHERITED_SECRET'])",
                    stdout_path=str(log),
                ))
            self.assertTrue(result["succeeded"], result)
            self.assertNotIn(inherited, log.read_text(encoding="utf-8"))
            self.assertIn("[REDACTED]", log.read_text(encoding="utf-8"))
            self.assertNotIn(inherited, json.dumps(result))

    def test_linked_log_parent_is_canonicalized_and_target_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = root / "real-logs"
            logs.mkdir()
            alias = root / "log-alias"
            try:
                alias.symlink_to(logs, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            result = run_validation_command(_request(
                root, "print('ok')", stdout_path=str(alias / "stdout.log"),
            ))
            self.assertTrue(result["succeeded"], result)
            self.assertTrue((logs / "stdout.log").is_file())
            target = logs / "linked-target.log"
            target.symlink_to(logs / "stdout.log")
            blocked = run_validation_command(_request(root, "print('ok')", stdout_path=str(target)))
            self.assertEqual("invalid-request", blocked["failure-kind"])

    def test_relative_path_entry_is_resolved_before_child_cwd(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            host_bin = root / "host-bin"
            child = root / "child"
            host_bin.mkdir()
            child.mkdir()
            name = "validation-relative-probe.exe"
            host_tool = host_bin / name
            host_tool.write_bytes(b"host")
            host_tool.chmod(0o755)
            relative_bin = os.path.relpath(host_bin, Path.cwd())
            child_tool = child / relative_bin / name
            child_tool.parent.mkdir(parents=True)
            child_tool.write_bytes(b"child")
            command, *_ = _validate_command_request(_request(
                child, "", executable=name, argv=[], env={"PATH": relative_bin},
            ))
            self.assertEqual(str(host_tool.resolve()), command[0])
            self.assertNotEqual(str(child_tool.resolve()), command[0])

    @unittest.skipUnless(os.name == "nt", "Windows batch execution uses a command shell")
    def test_windows_batch_executable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = root / "probe.cmd"
            batch.write_text("echo unsafe", encoding="utf-8")
            result = run_validation_command(_request(root, "", executable=str(batch), argv=[]))
            self.assertEqual("invalid-request", result["failure-kind"])

    def test_timeout_confirms_termination_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_validation_command(_request(Path(temporary), "import time; time.sleep(20)", timeout_seconds=0.1))
            self.assertFalse(result["succeeded"])
            self.assertTrue(result["timed-out"], result)
            self.assertTrue(result["recovery-attempted"])
            self.assertTrue(result["process-tree-termination-confirmed"], result)

    def test_live_descendant_fails_even_after_root_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            statement = "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)'])"
            result = run_validation_command(_request(Path(temporary), statement))
            self.assertFalse(result["succeeded"])
            self.assertEqual("descendant-process", result["failure-kind"])
            self.assertTrue(result["descendant-processes-detected"])
            self.assertTrue(result["recovery-attempted"])

    def test_containment_uncertainty_fails_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch("embraion.project_validation._spawn_contained", side_effect=ContainmentUnavailable("unavailable", termination_confirmed=False)):
                result = run_validation_command(_request(Path(temporary), "print(1)"))
            self.assertFalse(result["safe-to-continue"])
            self.assertFalse(result["succeeded"])
            self.assertEqual("containment-unavailable", result["failure-kind"])

    def test_invalid_request_and_log_path_collision_do_not_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "existing.log"
            target.write_text("preserve", encoding="utf-8")
            with mock.patch("embraion.project_validation._spawn_contained") as spawn:
                result = run_validation_command(_request(root, "print(1)", stdout_path=str(target)))
                invalid = run_validation_command({"executable": sys.executable, "argv": "bad", "cwd": str(root), "timeout_seconds": 1})
                huge_timeout = run_validation_command(_request(root, "print(1)", timeout_seconds=10 ** 1000))
                spawn.assert_not_called()
            self.assertEqual("preserve", target.read_text(encoding="utf-8"))
            self.assertEqual("invalid-request", result["failure-kind"])
            self.assertEqual("invalid-request", invalid["failure-kind"])
            self.assertEqual("invalid-request", huge_timeout["failure-kind"])

    def test_truncated_secret_prefix_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = "sensitive-" + "value-" + "with-tail"
            log = root / "out.log"
            result = run_validation_command(_request(
                root, "import os,sys; sys.stdout.write(os.environ['CHECK_SECRET'])",
                env={"CHECK_SECRET": secret}, output_limit_bytes=8, stdout_path=str(log),
            ))
            self.assertEqual("output-truncated", result["failure-kind"])
            self.assertTrue(result["stdout-truncated"])
            self.assertNotIn(secret[:8], log.read_text(encoding="utf-8"))

    def test_truncated_unicode_secret_and_private_key_block_are_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unicode_secret = "αβγδ-secret-tail"
            unicode_log = root / "unicode.log"
            unicode_result = run_validation_command(_request(
                root, "import os,sys; sys.stdout.write(os.environ['CHECK_SECRET'])",
                env={"CHECK_SECRET": unicode_secret, "PYTHONIOENCODING": "utf-8"}, output_limit_bytes=3,
                stdout_path=str(unicode_log),
            ))
            self.assertTrue(unicode_result["stdout-truncated"])
            self.assertEqual("output-truncated", unicode_result["failure-kind"])
            self.assertNotIn("α", unicode_log.read_text(encoding="utf-8"))
            self.assertIn("content omitted", unicode_log.read_text(encoding="utf-8"))
            self.assertGreater(len(unicode_log.read_bytes()), 3)  # Short marker is outside the child-byte limit.
            self.assertLess(len(unicode_log.read_bytes()), 128)

            key_log = root / "key.log"
            begin = "-----BEGIN " + "PRIVATE " + "KEY-----"
            end = "-----END " + "PRIVATE " + "KEY-----"
            block = begin + "\n" + "A" * 1000 + "\n" + end
            key_result = run_validation_command(_request(
                root, "import sys; sys.stdout.write(sys.argv[1])", argv=["-c", "import sys; sys.stdout.write(sys.argv[1])", block],
                output_limit_bytes=40, stdout_path=str(key_log),
            ))
            self.assertTrue(key_result["stdout-truncated"])
            self.assertNotIn("BEGIN PRIVATE KEY", key_log.read_text(encoding="utf-8"))

    def test_redaction_expansion_keeps_log_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "out.log"
            result = run_validation_command(_request(
                root, "print('x' * 512)", env={"CHECK_SECRET": "x"},
                output_limit_bytes=1024, stdout_path=str(log),
            ))
            self.assertEqual("output-truncated", result["failure-kind"])
            self.assertTrue(result["stdout-truncated"])
            self.assertLess(len(log.read_bytes()), 1200)

    def test_incomplete_stream_drain_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = {
                "containment-established": True, "root-exit-confirmed": True,
                "process-tree-termination-confirmed": True, "streams-drained": False,
                "safe-to-continue": False,
            }
            with mock.patch("embraion.project_validation._run_contained", return_value=(
                0, CapturedOutput(), CapturedOutput(), "unconfirmed", "stream-drain-failure", lifecycle,
            )):
                result = run_validation_command(_request(Path(temporary), "print(1)"))
            self.assertEqual("stream-drain-failure", result["failure-kind"])
            self.assertFalse(result["safe-to-continue"])
            self.assertFalse(result["succeeded"])

    def test_partial_log_open_failure_removes_first_log_without_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "first.log", root / "second.log"
            original_open = os.open
            calls = 0

            def fail_second(path, flags, mode=0o777):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("synthetic log failure")
                return original_open(path, flags, mode)

            with mock.patch("embraion.project_validation.os.open", side_effect=fail_second), mock.patch(
                "embraion.project_validation._run_contained"
            ) as launch:
                result = run_validation_command(_request(
                    root, "print(1)", stdout_path=str(first), stderr_path=str(second),
                ))
                launch.assert_not_called()
            self.assertEqual("log-path-unavailable", result["failure-kind"])
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

    def test_cli_emits_json_only_with_nonzero_on_invalid_request(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        command = [sys.executable, "tools/source.py", "validation", "command"]
        completed = subprocess.run(
            command,
            input="{invalid", text=True, capture_output=True, cwd=repository, check=False,
            env=os.environ.copy(),
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertEqual("invalid-request", json.loads(completed.stdout)["failure-kind"])

        nested = "[" * 1100 + "0" + "]" * 1100
        deep = subprocess.run(
            command, input=nested, text=True, capture_output=True, cwd=repository,
            check=False, env=os.environ.copy(),
        )
        self.assertEqual(2, deep.returncode, deep.stderr)
        self.assertEqual("invalid-request", json.loads(deep.stdout)["failure-kind"])

        success = subprocess.run(
            command, input=json.dumps(_request(repository, "print('child-marker')")),
            text=True, capture_output=True, cwd=repository, check=False, env=os.environ.copy(),
        )
        self.assertEqual(0, success.returncode, success.stderr)
        self.assertTrue(json.loads(success.stdout)["succeeded"])
        self.assertNotIn("child-marker", success.stdout)


if __name__ == "__main__":
    unittest.main()
