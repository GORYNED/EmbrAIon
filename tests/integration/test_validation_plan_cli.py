from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


def marker(name: str) -> str:
    return f'"{sys.executable}" -c "open(\'ran.txt\', \'a\').write(\'{name}\\\\n\')"'


class ValidationPlanCliTests(unittest.TestCase):
    def _run(self, *args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "embraion.cli", *args],
            cwd=cwd, text=True, capture_output=True, check=check,
        )

    def _git(self, repo: Path, *args: str) -> None:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
            check=True, capture_output=True, env=environment,
        )

    def _project(self, validation: dict) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        self._git(repo, "init", "-q", "-b", "main")
        self._git(repo, "config", "commit.gpgsign", "false")
        self._run("init", ".", "--name", "PlanDemo", cwd=repo)
        (repo / ".embraion" / "validation.yaml").write_text(yaml.safe_dump(validation, sort_keys=False), encoding="utf-8")
        (repo / ".gitignore").write_text(".embraion/state/\nran.txt\n", encoding="utf-8")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-qm", "base")
        self._git(repo, "checkout", "-qb", "topic")
        return repo

    def _change(self, repo: Path, relative: str) -> None:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n", encoding="utf-8")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-qm", relative)

    def test_plain_project_listing_is_unchanged(self) -> None:
        repo = self._project({"profiles": {"fast": [marker("fast")]}})
        listing = json.loads(self._run("validation", "list", "--json", cwd=repo).stdout)
        self.assertEqual(["profiles"], list(listing))
        self.assertEqual({"commands": [marker("fast")], "command-count": 1, "parameters": {}}, listing["profiles"]["fast"])
        text = self._run("validation", "list", cwd=repo).stdout
        self.assertNotIn("Areas:", text)
        failed = self._run("validation", "run", "fast", "--base-ref", "main", cwd=repo, check=False)
        self.assertEqual(2, failed.returncode)
        self.assertIn("declares no validation areas", failed.stderr)
        record = json.loads(self._run("validation", "run", "fast", "--json", cwd=repo).stdout)
        self.assertEqual("passed", record["status"])
        self.assertNotIn("plan", record)

    def test_plan_explain_and_planned_run(self) -> None:
        repo = self._project({
            "profiles": {"affected": [marker("affected")], "full": [marker("lint"), marker("unit")]},
            "areas": {
                "library": {"paths": ["src/**"], "commands": [marker("unit")]},
                "docs": {"paths": ["docs/**"], "commands": [marker("docs")]},
            },
            "impact": [{"id": "schema", "paths": ["src/schema/**"], "full": "data-migration"}],
            "full-reasons": ["data-migration"],
        })
        self._change(repo, "docs/guide.md")

        listing = json.loads(self._run("validation", "list", "--json", cwd=repo).stdout)
        self.assertEqual(["library", "docs"], list(listing["areas"]))
        self.assertIn("Areas:", self._run("validation", "list", cwd=repo).stdout)

        output = repo / "plan.json"
        planned = json.loads(self._run(
            "validation", "plan", "affected", "--base-ref", "main", "--json", "--output", str(output), cwd=repo,
        ).stdout)
        self.assertEqual(planned, json.loads(output.read_text(encoding="utf-8")))
        self.assertEqual(["docs/guide.md"], planned["changed-paths"])
        again = self._run("validation", "plan", "affected", "--base-ref", "main", "--json", cwd=repo).stdout
        self.assertEqual(planned, json.loads(again))
        self.assertTrue((repo / ".embraion" / "state" / "validation" / "plan.json").is_file())

        explained = self._run("validation", "explain", "affected", "--base-ref", "main", cwd=repo).stdout
        self.assertIn("docs: selected by 1 changed path(s)", explained)
        self.assertIn("library: no changed path matched", explained)

        by_file = json.loads(self._run("validation", "run", "affected", "--plan", str(output), "--json", cwd=repo).stdout)
        by_ref = json.loads(self._run("validation", "run", "affected", "--base-ref", "main", "--json", cwd=repo).stdout)
        for record in (by_file, by_ref):
            self.assertEqual("passed", record["status"])
            self.assertEqual([marker("docs")], [item["command"] for item in record["commands"]])
            self.assertTrue((repo / record["plan-path"]).is_file())

        everything = json.loads(self._run("validation", "run", "affected", "--json", cwd=repo).stdout)
        self.assertNotIn("plan", everything)
        self.assertEqual(marker("affected"), everything["commands"][0]["command"])

        escalated = self._run(
            "validation", "explain", "affected", "--base-ref", "main", "--full-justification", "nonsense",
            cwd=repo, check=False,
        )
        self.assertEqual(2, escalated.returncode)
        self.assertIn("not in full-reasons", escalated.stderr)

    def test_empty_plan_is_skipped_not_passed(self) -> None:
        repo = self._project({
            "profiles": {"affected": [marker("affected")]},
            "areas": {"library": {"paths": ["src/**"], "commands": [marker("unit")]}},
        })
        record = json.loads(self._run("validation", "run", "affected", "--base-ref", "HEAD", "--json", cwd=repo).stdout)
        self.assertEqual("skipped", record["status"])
        text = self._run("validation", "run", "affected", "--base-ref", "HEAD", cwd=repo).stdout
        self.assertIn("The plan selects no commands: no changed paths.", text)

    def test_invalid_plan_configuration_fails_closed(self) -> None:
        repo = self._project({
            "profiles": {"affected": [marker("affected")]},
            "areas": {"library": {"paths": ["src/**"], "commands": [marker("unit")]}},
            "impact": [{"id": "bad", "paths": ["src/**"], "areas": ["ghost"]}],
        })
        result = self._run("validation", "list", cwd=repo, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown area(s): ghost", result.stderr)


if __name__ == "__main__":
    unittest.main()
