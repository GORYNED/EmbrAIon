"""Execute the check action's Bash entrypoint against real Git histories."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


@unittest.skipIf(os.name == "nt", "GitHub runs this Bash action on Unix; Git Bash is not reliable in Windows sandbox")
@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "bash and git are required")
class CheckActionBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "project"
        self.repository.mkdir()
        self._git("init", "--quiet", "--initial-branch=main")
        (self.repository / "one.txt").write_text("one\n", encoding="utf-8")
        self._git("add", "one.txt")
        self._git("-c", "user.name=CI", "-c", "user.email=ci@example.com", "commit", "--quiet", "-m", "one")
        self.first = self._git("rev-parse", "HEAD")
        (self.repository / "two.txt").write_text("two\n", encoding="utf-8")
        self._git("add", "two.txt")
        self._git("-c", "user.name=CI", "-c", "user.email=ci@example.com", "commit", "--quiet", "-m", "two")
        self._git("checkout", "--quiet", "--orphan", "unrelated")
        self._git("rm", "--quiet", "-rf", ".")
        (self.repository / "other.txt").write_text("other\n", encoding="utf-8")
        self._git("add", "other.txt")
        self._git("-c", "user.name=CI", "-c", "user.email=ci@example.com", "commit", "--quiet", "-m", "unrelated")
        self.unrelated = self._git("rev-parse", "HEAD")
        self._git("checkout", "--quiet", "main")

        action = yaml.safe_load((Path(__file__).resolve().parents[2] / "actions/check/action.yml").read_text(encoding="utf-8"))
        self.script = self.root / "action.sh"
        self.script.write_text(action["runs"]["steps"][0]["run"], encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        launcher = bin_dir / "embraion"
        launcher.write_text(
            '#!/usr/bin/env bash\n'
            'if [[ "$1 $2" == "framework pin" ]]; then echo "version=0.1.0"; exit 0; fi\n'
            'printf "%s\\n" "$*" >> "$EMBRAION_ACTION_LOG"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        self.bin_dir = bin_dir

    def _git(self, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=self.repository, text=True).strip()

    def _run_action(self, *, event: str, before: str = "", pr_base: str = "") -> str:
        log = self.root / "calls.txt"
        log.unlink(missing_ok=True)
        env = os.environ.copy()
        env.update({
            "PATH": str(self.bin_dir) + os.pathsep + env.get("PATH", ""),
            "EMBRAION_ACTION_LOG": str(log),
            "EMBRAION_BASE_REF": "",
            "EMBRAION_PR_BASE": pr_base,
            "EMBRAION_EVENT_NAME": event,
            "EMBRAION_PUSH_BEFORE": before,
        })
        subprocess.run(["bash", str(self.script)], cwd=self.repository, env=env, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return log.read_text(encoding="utf-8").strip()

    def test_pull_request_uses_target_branch(self) -> None:
        self.assertEqual("check --base-ref origin/main --require-base-ref",
                         self._run_action(event="pull_request", pr_base="main"))

    def test_push_uses_existing_ancestor_from_event(self) -> None:
        self.assertEqual(f"check --base-ref {self.first} --require-base-ref",
                         self._run_action(event="push", before=self.first))

    def test_initial_push_has_no_base(self) -> None:
        self.assertEqual("check --require-base-ref",
                         self._run_action(event="push", before="0" * 40))

    def test_missing_previous_commit_has_no_base(self) -> None:
        self.assertEqual("check --require-base-ref",
                         self._run_action(event="push", before="f" * 40))

    def test_nonancestor_history_has_no_base(self) -> None:
        self.assertEqual("check --require-base-ref",
                         self._run_action(event="push", before=self.unrelated))


if __name__ == "__main__":
    unittest.main()
