from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from embraion.common import read_json, read_yaml, write_yaml
from embraion.evidence import read_run, start_run
from embraion.project import init_project
from embraion.project_validation import (
    MAX_CAPTURE_CHARS,
    read_validation_evidence,
    run_validation_profile,
    validation_profiles,
)


# A command that starts a grandchild, records both process IDs, and then waits.
PROCESS_TREE_SCRIPT = """
import os, subprocess, sys, time
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    handle.write(f"{os.getpid()} {grandchild.pid}")
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
print("tree-started", flush=True)
time.sleep(60)
"""


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    status = Path(f"/proc/{pid}/stat")
    try:
        # An unreaped zombie no longer runs; init may reap it later in containers.
        return status.read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _wait_until_dead(pids: list[int], seconds: float = 10.0) -> list[int]:
    deadline = time.monotonic() + seconds
    alive = [pid for pid in pids if _process_alive(pid)]
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = [pid for pid in alive if _process_alive(pid)]
    return alive


class ProjectValidationTests(unittest.TestCase):
    def _command(self, statement: str) -> str:
        return f'"{sys.executable}" -c "{statement}"'

    def test_lists_and_runs_project_validation_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["fast"] = [
                self._command("print('validation-ok')")
            ]
            write_yaml(path, data)

            profiles = validation_profiles(project)
            self.assertEqual(1, len(profiles["fast"]))

            record = run_validation_profile("fast", project=project)
            self.assertEqual("passed", record["status"])
            self.assertEqual(1, record["command-count"])
            self.assertEqual(0, record["commands"][0]["exit-code"])
            self.assertIn("validation-ok", record["commands"][0]["stdout"])

            persisted = read_validation_evidence(
                record["evidence-id"],
                project,
            )
            self.assertEqual(record["evidence-id"], persisted["evidence-id"])
            self.assertTrue(
                (
                    project
                    / ".embraion"
                    / "state"
                    / "validation"
                    / f"{record['evidence-id']}.json"
                ).is_file()
            )

    def test_failed_and_empty_profiles_are_not_false_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["fast"] = [
                self._command("import sys; sys.exit(7)")
            ]
            write_yaml(path, data)

            failed = run_validation_profile("fast", project=project)
            self.assertEqual("failed", failed["status"])
            self.assertEqual(7, failed["commands"][0]["exit-code"])

            skipped = run_validation_profile("full", project=project)
            self.assertEqual("skipped", skipped["status"])
            self.assertEqual(0, skipped["executed-command-count"])

    def test_validation_output_is_redacted_and_can_attach_to_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            secret = "abcdefgh" + "12345678"
            secret_label = "to" + "ken"
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["fast"] = [
                self._command(f"print('{secret_label}={secret}')")
            ]
            write_yaml(path, data)

            start_run(
                "run-1",
                "Validate bounded change",
                "validator",
                "codex",
                "ordinary",
                "PRIVATE",
                "read",
                [],
                project=project,
            )

            record = run_validation_profile(
                "fast",
                project=project,
                run_id="run-1",
            )
            self.assertNotIn(secret, record["commands"][0]["stdout"])
            self.assertIn("<REDACTED>", record["commands"][0]["stdout"])

            run = read_run("run-1", project)
            self.assertEqual(1, len(run["validation"]))
            self.assertEqual("fast", run["validation"][0]["profile"])
            self.assertEqual("passed", run["validation"][0]["status"])
            self.assertEqual(
                record["evidence-id"],
                run["validation"][0]["evidence-id"],
            )

    def test_parameterized_profile_applies_argument_and_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["affected"] = {
                "commands": [
                    self._command(
                        "import os,sys; "
                        "print('args=' + '|'.join(sys.argv[1:])); "
                        "print('env=' + os.environ['VALIDATION_SCOPE'])"
                    )
                ],
                "parameters": {
                    "base-ref": {
                        "argument": "--base-ref",
                        "required": True,
                    },
                    "scope": {
                        "environment": "VALIDATION_SCOPE",
                        "default": "repository",
                    },
                },
            }
            write_yaml(path, data)

            record = run_validation_profile(
                "affected",
                project=project,
                parameters={"base-ref": "origin/main with space"},
            )

            self.assertEqual("passed", record["status"])
            self.assertNotIn(
                "origin/main with space",
                record["commands"][0]["stdout"],
            )
            self.assertNotIn("repository", record["commands"][0]["stdout"])
            self.assertIn(
                "<REDACTED:validation-parameter>",
                record["commands"][0]["stdout"],
            )
            self.assertNotIn(
                "origin/main with space",
                record["commands"][0]["command"],
            )
            self.assertEqual(["base-ref", "scope"], record["parameters"])

    def test_parameterized_profile_fails_closed_for_missing_or_unknown_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["full"] = {
                "commands": [self._command("print('full')")],
                "parameters": {
                    "justification": {
                        "environment": "VALIDATION_JUSTIFICATION",
                        "required": True,
                    }
                },
            }
            write_yaml(path, data)

            with self.assertRaisesRegex(
                RuntimeError,
                "Missing required validation parameter 'justification'",
            ):
                run_validation_profile("full", project=project)

            with self.assertRaisesRegex(
                RuntimeError,
                "Unknown validation parameter",
            ):
                run_validation_profile(
                    "full",
                    project=project,
                    parameters={
                        "justification": "approved",
                        "unexpected": "value",
                    },
                )

    def test_windows_argument_parameter_rejects_cmd_metacharacters(self) -> None:
        with mock.patch("embraion.project_validation.os.name", "nt"):
            with self.assertRaisesRegex(
                RuntimeError,
                "unsafe for cmd.exe",
            ):
                from embraion.project_validation import _quote_validation_argument

                _quote_validation_argument("safe&echo injected")

    def test_parameter_values_are_not_persisted_in_validation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            secret = "abcdefgh" + "12345678"
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["full"] = {
                "commands": [
                    self._command(
                        "import os; print(os.environ['VALIDATION_SECRET'])"
                    )
                ],
                "parameters": {
                    "token": {
                        "environment": "VALIDATION_SECRET",
                        "required": True,
                    }
                },
            }
            write_yaml(path, data)

            record = run_validation_profile(
                "full",
                project=project,
                parameters={"token": secret},
            )
            serialized = json.dumps(record)
            self.assertNotIn(secret, serialized)
            self.assertEqual(["token"], record["parameters"])
            self.assertIn(
                "<REDACTED:validation-parameter>",
                record["commands"][0]["stdout"],
            )

    def test_parameter_command_target_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["affected"] = {
                "commands": [self._command("print('one')")],
                "parameters": {
                    "scope": {
                        "argument": "--scope",
                        "commands": [2],
                    }
                },
            }
            write_yaml(path, data)

            with self.assertRaisesRegex(
                RuntimeError,
                r"targets command\(s\) outside 1\.\.1",
            ):
                run_validation_profile(
                    "affected",
                    project=project,
                    parameters={"scope": "all"},
                )

    def test_invalid_validation_config_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            validation_path = project / ".embraion" / "validation.yaml"
            validation = read_yaml(validation_path)
            validation["profiles"]["affected"] = "python -m unittest"
            write_yaml(validation_path, validation)

            with self.assertRaisesRegex(
                RuntimeError,
                "Invalid .embraion/validation.yaml",
            ):
                run_validation_profile("affected", project=project)

    def test_unknown_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            with self.assertRaisesRegex(RuntimeError, "Unknown validation profile"):
                run_validation_profile("missing", project=project)


@unittest.skipUnless(os.name == "posix", "process-group containment is exercised with POSIX signals")
class ValidationContainmentTests(unittest.TestCase):
    def _project(self, temporary: str, profile: object) -> Path:
        project = Path(temporary) / "project"
        project.mkdir()
        init_project(project, name="Consumer")
        (project / "tree.py").write_text(PROCESS_TREE_SCRIPT, encoding="utf-8")
        path = project / ".embraion" / "validation.yaml"
        data = read_yaml(path)
        data["profiles"]["full"] = profile
        write_yaml(path, data)
        return project

    def _tree_command(self) -> str:
        return f'"{sys.executable}" tree.py pids.txt'

    def _pids(self, project: Path) -> list[int]:
        return [int(value) for value in (project / "pids.txt").read_text(encoding="utf-8").split()]

    def test_configured_timeout_terminates_child_and_grandchild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(temporary, {"commands": [self._tree_command()], "timeout-seconds": 1})
            began = time.monotonic()
            record = run_validation_profile("full", project=project)
            self.assertLess(time.monotonic() - began, 30)
            row = record["commands"][0]
            self.assertEqual("failed", record["status"])
            self.assertEqual("timed-out", row["status"])
            self.assertIsNone(row["exit-code"])
            self.assertEqual(1.0, row["timeout-seconds"])
            self.assertIn("tree-started", row["stdout"])
            self.assertEqual([], _wait_until_dead(self._pids(project)))

    def test_interrupt_terminates_the_process_tree_and_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(temporary, [self._tree_command()])
            pid_file = project / "pids.txt"

            def interrupt(process: object, timeout: float | None) -> int:
                deadline = time.monotonic() + 20
                while not pid_file.is_file() and time.monotonic() < deadline:
                    time.sleep(0.05)
                raise KeyboardInterrupt

            with mock.patch("embraion.project_validation._wait_for", side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    run_validation_profile("full", project=project)
            self.assertEqual([], _wait_until_dead(self._pids(project)))

    def test_per_command_timeouts_and_cli_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            quick = f'"{sys.executable}" -c "print(1)"'
            slow = f'"{sys.executable}" -c "import time; time.sleep(30)"'
            project = self._project(temporary, {"commands": [quick, slow], "timeout-seconds": [None, 0.5]})
            record = run_validation_profile("full", project=project)
            self.assertEqual(["passed", "timed-out"], [row["status"] for row in record["commands"]])
            self.assertEqual([None, 0.5], [row["timeout-seconds"] for row in record["commands"]])

            overridden = run_validation_profile("full", project=project, timeout=0.25)
            self.assertEqual([0.25, 0.25], [row["timeout-seconds"] for row in overridden["commands"]])

            path = project / ".embraion" / "validation.yaml"
            data = read_yaml(path)
            data["profiles"]["full"]["timeout-seconds"] = [1]
            write_yaml(path, data)
            with self.assertRaisesRegex(RuntimeError, "timeout-seconds lists 1 value"):
                run_validation_profile("full", project=project)
            data["profiles"]["full"]["timeout-seconds"] = 0
            write_yaml(path, data)
            with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/validation.yaml"):
                run_validation_profile("full", project=project)

    def test_full_redacted_log_artifact_and_run_id_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret = "abcdefgh" + "12345678"
            statement = (
                "import os; print('x' * " + str(MAX_CAPTURE_CHARS * 2) + "); "
                "print('run=' + os.environ.get('EMBRAION_RUN_ID', 'none')); "
                "print('to' + 'ken=' + 'abcdefgh' + '12345678')"
            )
            project = self._project(temporary, [f'"{sys.executable}" -c "{statement}"'])
            start_run("run-7", "Validate", "validator", "codex", "ordinary", "PRIVATE", "read", [], project=project)
            with mock.patch.dict(os.environ, {"EMBRAION_RUN_ID": "outer"}):
                attached = run_validation_profile("full", project=project, run_id="run-7")
                detached = run_validation_profile("full", project=project)

            row = attached["commands"][0]
            self.assertIn("...<truncated>", row["stdout"])
            self.assertEqual(
                f".embraion/state/validation/{attached['evidence-id']}/command-1.log",
                row["log-path"],
            )
            log = (project / row["log-path"]).read_text(encoding="utf-8")
            self.assertTrue("x" * (MAX_CAPTURE_CHARS * 2) in log)
            self.assertIn("run=run-7", log)
            self.assertIn("<REDACTED>", log)
            self.assertFalse(secret in log)
            self.assertIn("--- stderr ---", log)
            detached_log = (project / detached["commands"][0]["log-path"]).read_text(encoding="utf-8")
            self.assertIn("run=none", detached_log)


if __name__ == "__main__":
    unittest.main()
