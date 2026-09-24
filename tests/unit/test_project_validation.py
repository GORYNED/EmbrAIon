from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from embraion.common import read_json, read_yaml, write_yaml
from embraion.evidence import read_run, start_run
from embraion.project import init_project
from embraion.project_validation import (
    read_validation_evidence,
    run_validation_profile,
    validation_profiles,
)


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


if __name__ == "__main__":
    unittest.main()
