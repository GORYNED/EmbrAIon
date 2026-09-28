from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ProjectionDestinationCliTests(unittest.TestCase):
    def test_root_authority_survives_alternate_config_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            environment = os.environ.copy()
            environment["EMBRAION_DISABLE_VERSION_RESOLUTION"] = "1"
            steps = []

            def cli(label: str, *arguments: str) -> dict:
                result = subprocess.run([sys.executable, "-m", "embraion.cli", *arguments],
                                        cwd=project, env=environment, text=True, capture_output=True)
                self.assertEqual(0, result.returncode, result.stderr + result.stdout)
                data = json.loads(result.stdout)
                steps.append({"step": label, "exit-code": result.returncode,
                              **({"findings": len(data["findings"])} if "findings" in data else {}),
                              **({"verified": data["verified"]} if "verified" in data else {})})
                return data

            result = subprocess.run([sys.executable, "-m", "embraion.cli", "init", "--name", "Consumer"],
                                    cwd=project, env=environment, text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            fixture = Path(__file__).resolve().parents[1] / "fixtures/routing-consumer"
            shutil.copytree(fixture, project, dirs_exist_ok=True)
            cli("root-install", "install", "--host", "codex", "--destination", ".", "--config-mode", "merge", "--force", "--json")
            root_state = project / ".embraion/state/projections/codex/root.json"
            original = root_state.read_bytes()
            self.assertEqual([], cli("root-audit-before", "route", "--audit-authority")["findings"])
            cli("alternate-install", "install", "--host", "codex", "--component", "config", "--config-mode", "merge", "--destination", "alternate", "--json")
            self.assertEqual(original, root_state.read_bytes())
            self.assertTrue(cli("root-verify", "projection", "verify", "--host", "codex", "--destination", ".", "--config-mode", "merge", "--json")["verified"])
            self.assertEqual([], cli("root-audit-after", "route", "--audit-authority")["findings"])
            self.assertTrue(cli("alternate-verify", "projection", "verify", "--host", "codex", "--component", "config", "--destination", "alternate", "--config-mode", "merge", "--json")["verified"])
            records = []
            for path in sorted(root_state.parent.glob("*.json")):
                record = json.loads(path.read_text(encoding="utf-8"))
                records.append({"state-file": path.name, "managed-components": record["managed-components"],
                                "config-mode": record["config-mode"], "files": record["files"]})
            evidence = {"schema-version": 1, "steps": steps, "root-state-unchanged": True, "records": records}
            output = os.getenv("EMBRAION_PROJECTION_EVIDENCE_DIR")
            if output:
                directory = Path(output)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "projection-destinations.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
