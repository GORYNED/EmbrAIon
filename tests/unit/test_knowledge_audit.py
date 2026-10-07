from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from embraion.knowledge_audit import audit_knowledge, snapshot_knowledge


class KnowledgeAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".embraion").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "src").mkdir()
        (self.root / "docs/architecture.md").write_text("v1\n")
        (self.root / "src/app.py").write_text("version = 1\n")
        (self.root / ".embraion/knowledge-maintenance.yaml").write_text(
            "documents:\n  - id: architecture\n    path: docs/architecture.md\n"
            "    sources:\n      - src/app.py\n")

    def test_baseline_and_source_document_changes(self) -> None:
        self.assertEqual("needs-review", audit_knowledge(project=self.root)["status"])
        baseline = snapshot_knowledge(project=self.root)
        self.assertNotIn(str(self.root), str(baseline))
        current = audit_knowledge(project=self.root)
        self.assertEqual("current", current["status"])
        self.assertFalse(current["documents"][0]["external-version-known"])
        baseline_path = self.root / ".embraion/state/knowledge-audit/baseline.json"
        before = baseline_path.read_bytes()
        self.assertEqual(current, audit_knowledge(project=self.root))
        self.assertEqual(before, baseline_path.read_bytes())
        (self.root / "src/app.py").write_text("version = 2\n")
        result = audit_knowledge(project=self.root)
        self.assertEqual("needs-review", result["status"])
        self.assertEqual(["src/app.py"], result["documents"][0]["changed-paths"])
        (self.root / "docs/architecture.md").unlink()
        self.assertEqual("missing", audit_knowledge(project=self.root)["status"])

    def test_dangerous_paths_and_symlinks(self) -> None:
        config = self.root / ".embraion/knowledge-maintenance.yaml"
        for path in ("../secret", "/tmp/secret", ".embraion/state/secret", "./src/app.py"):
            config.write_text("documents:\n  - id: architecture\n    path: docs/architecture.md\n"
                              f"    sources: [{path}]\n")
            with self.assertRaises(RuntimeError):
                snapshot_knowledge(project=self.root)
        try:
            (self.root / "linked.py").symlink_to(self.root / "src/app.py")
        except OSError as error:
            if getattr(error, "winerror", None) != 1314:
                raise
            self.skipTest("Windows symlink privilege unavailable")
        config.write_text("documents:\n  - id: architecture\n    path: docs/architecture.md\n"
                          "    sources: [linked.py]\n")
        with self.assertRaises(RuntimeError):
            audit_knowledge(project=self.root)

    def test_observed_version_and_configuration_change_require_review(self) -> None:
        config = self.root / ".embraion/knowledge-maintenance.yaml"
        config.write_text(config.read_text() + "    observed-version: release-1\n")
        snapshot_knowledge(project=self.root)
        self.assertTrue(audit_knowledge(project=self.root)["documents"][0]["external-version-known"])
        config.write_text(config.read_text().replace("release-1", "release-2"))
        result = audit_knowledge(project=self.root)
        self.assertEqual("needs-review", result["status"])
        self.assertIn("source-or-document-changed", result["documents"][0]["reasons"])

    def test_invalid_config_does_not_echo_values(self) -> None:
        config = self.root / ".embraion/knowledge-maintenance.yaml"
        sensitive = "token=" + "not-a-real-secret-" * 2
        for payload in (
            "documents:\n  - id: architecture\n    path: [" + sensitive + "]\n    sources: [src/app.py]\n",
            "documents: [" + sensitive,
            "x" * (1024 * 1024 + 1),
        ):
            config.write_text(payload)
            with self.assertRaises(RuntimeError) as caught:
                audit_knowledge(project=self.root)
            self.assertNotIn(sensitive, str(caught.exception))
        for path in ("C:/private.txt", "D:private.txt", "src/name\x00.py"):
            config.write_text("documents:\n  - id: architecture\n    path: docs/architecture.md\n"
                              f"    sources: [{path!r}]\n")
            with self.assertRaises(RuntimeError):
                audit_knowledge(project=self.root)

    def test_invalid_baseline_never_reports_current(self) -> None:
        snapshot_knowledge(project=self.root)
        path = self.root / ".embraion/state/knowledge-audit/baseline.json"
        sensitive = "token=" + "not-a-real-secret-" * 2
        for payload in ("[1]", "{" + sensitive, "x" * (1024 * 1024 + 1),
                        '{"schema-version": 1, "config-hash": "bad", "documents": []}'):
            path.write_text(payload)
            with self.assertRaisesRegex(RuntimeError, "Invalid knowledge baseline") as caught:
                audit_knowledge(project=self.root)
            self.assertNotIn(sensitive, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
