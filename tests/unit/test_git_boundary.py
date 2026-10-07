from __future__ import annotations

import re
import unittest
from pathlib import Path

from embraion.common import framework_root
from embraion.decisions import decisions_folder

ROOT = framework_root()
WORKFLOWS = ROOT / "core/workflows"
LINK = re.compile(r"\]\(git\.md#([a-z0-9-]+)\)")


def anchors(path: Path) -> set[str]:
    return {
        re.sub(r"[^a-z0-9 -]", "", line.lstrip("# ").strip().lower()).replace(" ", "-")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


class GitBoundaryTests(unittest.TestCase):
    def test_git_mechanics_live_in_one_workflow_reference(self) -> None:
        text = (WORKFLOWS / "git.md").read_text(encoding="utf-8")
        for required in (
            "Serialize mutation per Git common directory",
            "Delete a remote ref only when its expected SHA still matches",
            "A proved squash merge is the only exception to ordinary local branch deletion",
            "create-only lease",
            "Squash integration requires exact PR head evidence; patch similarity is insufficient",
            "The squash commit receives a new SHA after merge",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_workflows_keep_universal_rules_and_link_the_mechanics(self) -> None:
        for name in ("worktree", "delivery"):
            text = (WORKFLOWS / f"{name}.md").read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("(git.md)", text)
                self.assertIn("Git is a stated prerequisite", text)
        worktree = (WORKFLOWS / "worktree.md").read_text(encoding="utf-8")
        for moved in ("Git common directory", "create-only lease", "squash\nmerge", "merge commit\nancestry"):
            self.assertNotIn(moved, worktree)
        for kept in (
            "Cleanup is fail-closed",
            "A local receipt or\nan external push never grants remote deletion authority",
            "never overwrite conflicting paths or refs during restore",
            "never similarity of content",
        ):
            self.assertIn(kept, worktree)
        delivery = (WORKFLOWS / "delivery.md").read_text(encoding="utf-8")
        self.assertNotIn("receives a new SHA", delivery)
        self.assertIn("Any candidate content or commit change requires renewed review", delivery)
        self.assertIn("confirm the PR source HEAD and reviewed diff are unchanged", delivery)

    def test_workflow_links_target_existing_git_sections(self) -> None:
        available = anchors(WORKFLOWS / "git.md")
        for name in ("worktree", "delivery"):
            text = (WORKFLOWS / f"{name}.md").read_text(encoding="utf-8")
            for anchor in LINK.findall(text):
                with self.subTest(workflow=name, anchor=anchor):
                    self.assertIn(anchor, available)

    def test_prerequisite_is_stated_in_both_installation_pages(self) -> None:
        for name in ("installation.md", "installation.ru.md"):
            text = (ROOT / "docs/getting-started" / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertIn("git worktree list --porcelain -z", text)
                self.assertIn("core/workflows/git.md", text)

    def test_self_host_binds_the_decision_records(self) -> None:
        self.assertEqual("docs/architecture/decisions", decisions_folder(ROOT))
        folder = ROOT / "docs/architecture/decisions"
        record = next(path for path in folder.glob("0001-*.md") if not path.name.endswith(".ru.md"))
        for name in (record.name, record.name.removesuffix(".md") + ".ru.md", "README.md", "README.ru.md"):
            self.assertTrue((folder / name).is_file(), name)
        self.assertIn("Status: Accepted", record.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
