from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from embraion.checkpoints import create_checkpoint, resume_checkpoint
from embraion.common import write_json
from embraion.evidence import review_snapshot


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        config = self.root / ".embraion"
        config.mkdir()
        (config / "project.yaml").write_text("framework:\n  version: 1.2.3\n")
        (config / "knowledge.yaml").write_text("architecture: docs/architecture.md\n")
        (self.root / "docs").mkdir()
        (self.root / "docs/architecture.md").write_text("Architecture v1\n")
        (self.root / "acceptance.md").write_text("Acceptance ID A1\n")
        (self.root / ".gitignore").write_text(".embraion/state/\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "initial")

    def test_resume_detects_git_pin_knowledge_and_missing_anchor(self) -> None:
        create_checkpoint("cp1", task_id="T1", phase="implementing",
                          acceptance_path="acceptance.md", project=self.root)
        first = resume_checkpoint("cp1", project=self.root)
        self.assertEqual("valid", first["status"])
        state = self.root / ".embraion/state/checkpoints/cp1.json"
        original = state.read_bytes()
        self.assertEqual(first, resume_checkpoint("cp1", project=self.root))
        self.assertEqual(original, state.read_bytes())
        (self.root / "untracked.txt").write_text("new")
        self.assertIn("git-snapshot-changed", resume_checkpoint("cp1", project=self.root)["reasons"])
        (self.root / "untracked.txt").unlink()
        (self.root / "docs/architecture.md").write_text("Architecture v2\n")
        self.assertIn("docs/architecture.md", resume_checkpoint("cp1", project=self.root)["changed-anchors"])
        (self.root / "docs/architecture.md").write_text("Architecture v1\n")
        (self.root / ".embraion/project.yaml").write_text("framework:\n  version: 9.9.9\n")
        self.assertIn(".embraion/project.yaml", resume_checkpoint("cp1", project=self.root)["changed-anchors"])
        (self.root / "acceptance.md").unlink()
        self.assertEqual("missing", resume_checkpoint("cp1", project=self.root)["status"])

    def test_context_run_and_validation_evidence_are_bound(self) -> None:
        state = self.root / ".embraion/state"
        (state / "context").mkdir(parents=True)
        (state / "runs").mkdir()
        (state / "validation").mkdir()
        import hashlib
        selected_hash = hashlib.sha256((self.root / "docs/architecture.md").read_bytes()).hexdigest()
        write_json(state / "context/ctx1.json", {"context-id": "ctx1", "selected": [
            {"path": "docs/architecture.md", "sha256": selected_hash}]})
        write_json(state / "validation/val1.json", {"evidence-id": "val1", "status": "passed"})
        write_json(state / "runs/run1.json", {"run-id": "run1", "review": "passed",
                                                "review-snapshot": review_snapshot(self.root),
                                                "validation": [{"evidence-id": "val1"}]})
        create_checkpoint("cp1", task_id="T1", phase="reviewing", context_id="ctx1",
                          run_id="run1", project=self.root)
        self.assertEqual("valid", resume_checkpoint("cp1", project=self.root)["status"])
        write_json(state / "validation/val1.json", {"evidence-id": "val1", "status": "failed"})
        result = resume_checkpoint("cp1", project=self.root)
        self.assertEqual("stale", result["status"])
        self.assertIn(".embraion/state/validation/val1.json", result["changed-anchors"])
        self.assertNotIn("approved", result)

    def test_invalid_references_and_private_narrative_are_rejected(self) -> None:
        for identifier in ("../escape", "x/y", "a" * 81):
            with self.assertRaises(RuntimeError):
                create_checkpoint(identifier, task_id="T1", phase="planning", project=self.root)
        for path in ("../outside", "/tmp/private", "./acceptance.md", ".embraion/state/secret.json"):
            with self.assertRaises(RuntimeError):
                create_checkpoint("cp1", task_id="T1", phase="planning", acceptance_path=path,
                                  project=self.root)
        private = self.root / "private"
        private.mkdir()
        (private / "secret").write_text("token=abcdefgh12345678")
        (self.root / "linked").symlink_to(private, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            create_checkpoint("cp1", task_id="T1", phase="planning", acceptance_path="linked/secret",
                              project=self.root)
        record = create_checkpoint("cp1", task_id="T1", phase="planning", project=self.root)
        self.assertNotIn("token=", json.dumps(record))
        self.assertNotIn(str(self.root), json.dumps(record))

    def test_no_git_does_not_claim_freshness(self) -> None:
        (self.root / ".git").rename(self.root / "git-hidden")
        create_checkpoint("cp1", task_id="T1", phase="planning", project=self.root)
        result = resume_checkpoint("cp1", project=self.root)
        self.assertEqual("stale", result["status"])
        self.assertIn("git-snapshot-unavailable", result["reasons"])


if __name__ == "__main__":
    unittest.main()
