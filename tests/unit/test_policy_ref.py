from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from embraion.cli import main
from embraion.policy import read_policy_config_at_ref


class PolicyRefTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / ".embraion").mkdir()

    def git(self, *args: str) -> str:
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True,
                                text=True, env=self.env, check=True)
        return result.stdout.strip()

    def write_policy(self, protected: list[str]) -> None:
        policy = {
            "sources": {"canonical": [], "protected": protected, "generated": [], "external": []},
            "review": {"substantial-required": True},
            "privacy": {"default-class": "PRIVATE"},
            "enforcement": {"enabled": False, "validation-profile": "fast", "require-review": True},
        }
        (self.root / ".embraion/policy.yaml").write_text(yaml.safe_dump(policy), encoding="utf-8")

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_ref_is_structured_validated_and_independent_of_worktree(self) -> None:
        self.write_policy(["Assets/Vendor/*.cs"])
        original = self.commit()
        self.write_policy(["Assets/New/*.dll"])
        before = self.git("status", "--porcelain")
        result = read_policy_config_at_ref(self.root, "HEAD")
        self.assertEqual(original, result["commit"])
        self.assertEqual(["Assets/Vendor/*.cs"], result["policy"]["sources"]["protected"])
        output = io.StringIO()
        with redirect_stdout(output), patch("embraion.cli.resolve_project_runtime", return_value=None):
            self.assertEqual(0, main(["policy", "show", "--path", str(self.root), "--ref", "HEAD", "--json"]))
        self.assertEqual(result, json.loads(output.getvalue()))
        self.assertEqual(before, self.git("status", "--porcelain"))
        updated = self.commit()
        self.assertEqual(["Assets/Vendor/*.cs"],
                         read_policy_config_at_ref(self.root, original)["policy"]["sources"]["protected"])
        self.assertEqual(["Assets/New/*.dll"],
                         read_policy_config_at_ref(self.root, updated)["policy"]["sources"]["protected"])

    def test_missing_invalid_and_ambiguous_committed_policy_fail_closed(self) -> None:
        (self.root / "README.md").write_text("fixture", encoding="utf-8")
        missing = self.commit()
        with self.assertRaisesRegex(RuntimeError, "missing"):
            read_policy_config_at_ref(self.root, missing)
        with self.assertRaisesRegex(RuntimeError, "resolve"):
            read_policy_config_at_ref(self.root, "not-a-ref")
        self.write_policy(["Assets/Vendor/*.cs"])
        path = self.root / ".embraion/policy.yaml"
        path.write_text(path.read_text(encoding="utf-8") + "sources: {}\n", encoding="utf-8")
        duplicate = self.commit()
        with self.assertRaisesRegex(RuntimeError, "invalid YAML"):
            read_policy_config_at_ref(self.root, duplicate)
        self.write_policy(["Assets/Vendor/*.cs"])
        text = path.read_text(encoding="utf-8").replace("default-class: PRIVATE", "default-class: UNKNOWN")
        path.write_text(text, encoding="utf-8")
        invalid = self.commit()
        with self.assertRaisesRegex(RuntimeError, "policy schema"):
            read_policy_config_at_ref(self.root, invalid)

    def test_symlinked_policy_is_not_read(self) -> None:
        outside = self.root / "outside.yaml"
        outside.write_text("sources: {}", encoding="utf-8")
        try:
            (self.root / ".embraion/policy.yaml").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        commit = self.commit()
        with self.assertRaisesRegex(RuntimeError, "regular file"):
            read_policy_config_at_ref(self.root, commit)
