"""Regression fixtures for the 0.17.0 audit; all mutations stay in temporary roots."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root, read_json, read_yaml, write_json
from embraion.enforcement import _git_changed_paths
from embraion.learning import observe, transition
from embraion.project import generate_host, init_project, install, _projection_state_path
from embraion.worktree import gc_worktrees, create_worktree, parse_worktrees


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class AuditRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def repo(self):
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        (self.root / ".gitignore").write_text(".embraion/state/\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "fixture")

    def symlink(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")

    def test_git_paths_are_lossless_in_all_change_sources(self):
        self.repo()
        base = git(self.root, "rev-parse", "HEAD")
        names = ["контракт.txt", "with space.txt"]
        if os.name != "nt":
            names += ['quote".txt', "line\nbreak.txt", "carriage\rreturn.txt"]
        expected = []
        for category in ("committed", "working", "untracked"):
            for name in names:
                relative = f"protected/{category}/{name}"
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("original")
                expected.append(relative)
            if category != "untracked":
                git(self.root, "add", ".")
                git(self.root, "commit", "-m", category)
            if category == "working":
                for name in names:
                    (self.root / f"protected/working/{name}").write_text("changed")
        self.assertEqual(sorted(expected), _git_changed_paths(self.root, base))
        self.assertEqual(sorted(path for path in expected if "/committed/" not in path),
                         _git_changed_paths(self.root, "HEAD"))

    def test_gc_preserves_active_and_unproven_user_worktrees(self):
        self.repo()
        other = self.root / "other"
        git(self.root, "worktree", "add", "-b", "task", str(other))
        with patch("embraion.worktree.project_root", return_value=self.root):
            for state in (None, "active", "completed"):
                if state:
                    write_json(other / ".embraion/state/runs/run.json", {"state": state})
                self.assertEqual([], gc_worktrees(base="main"))
                self.assertEqual([], gc_worktrees(base="main", apply=True))
                self.assertTrue(other.is_dir())

    def test_managed_gc_requires_terminal_evidence_and_no_git_operation(self):
        self.repo()
        git(self.root, "remote", "add", "origin", str(self.root))
        other = self.root / "managed"
        with patch("embraion.worktree.project_root", return_value=self.root):
            create_worktree("task", other, base="main")
            self.assertEqual([], gc_worktrees(base="main"))
            evidence = other / ".embraion/state/runs/run.json"
            for value in ({"state": "active"}, {"state": "blocked"}, {}, [], {"state": "unknown"}):
                write_json(evidence, value)
                self.assertEqual([], gc_worktrees(base="main", apply=True))
            evidence.write_text("malformed")
            self.assertEqual([], gc_worktrees(base="main"))
            write_json(evidence, {"state": "completed"})
            session = other / ".embraion/state/session.json"
            for state in ("active", "review", "incomplete", "blocked", "queued"):
                write_json(session, {"state": state})
                self.assertEqual([], gc_worktrees(base="main", apply=True))
            write_json(session, {"state": "completed"})
            metadata = Path(git(other, "rev-parse", "--absolute-git-dir"))
            for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "index.lock",
                         "rebase-merge", "rebase-apply", "sequencer"):
                marker = metadata / name
                marker.write_text("")
                self.assertEqual([], gc_worktrees(base="main", apply=True), name)
                marker.unlink()
            git(self.root, "worktree", "lock", str(other))
            self.assertEqual([], gc_worktrees(base="main"))
            git(self.root, "worktree", "unlock", str(other))
            dirty = other / "dirty"
            dirty.write_text("work")
            self.assertEqual([], gc_worktrees(base="main"))
            dirty.unlink()
            self.assertEqual(1, len(gc_worktrees(base="main")))
            self.assertEqual(1, len(gc_worktrees(base="main", apply=True)))
            self.assertFalse(other.exists())

    def test_worktree_list_preserves_quoted_and_unicode_paths(self):
        self.repo()
        other = self.root / ('ветка"\nline' if os.name != "nt" else "ветка")
        git(self.root, "worktree", "add", "-b", "task", str(other))
        # Git uses forward slashes on Windows; preserve exact spelling otherwise.
        self.assertIn(other.as_posix(),
                      [Path(item["path"]).as_posix() for item in parse_worktrees(self.root)])

    def test_portable_catalog_resolves_every_capability(self):
        generate_host(framework_root(), "portable", self.root)
        bundle = self.root / "embraion"
        catalog = read_yaml(bundle / "catalog.yaml")
        for capability in catalog["capabilities"]:
            with self.subTest(capability=capability["id"]):
                path = bundle / capability["path"]
                self.assertTrue(path.exists(), capability["path"])
                if capability["type"] == "skill":
                    self.assertTrue((path / "SKILL.md").is_file())
                else:
                    self.assertEqual((framework_root() / "core" / capability["path"]).read_bytes(), path.read_bytes())

    def test_projection_rejects_nested_escape_even_when_forced(self):
        destination = self.root / "project"
        external = self.root / "external"
        external.mkdir()
        init_project(destination, name="Fixture")
        self.symlink(destination / ".codex", external)
        for mode in ("replace", "merge"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(RuntimeError, "boundary|symlink"):
                    install("codex", destination, components=["config"], config_mode=mode, force=True)
                self.assertFalse((external / "config.toml").exists())

    def test_projection_pruning_does_not_follow_nested_escape(self):
        destination = self.root / "project"
        init_project(destination, name="Fixture")
        install("codex", destination, components=["agents"])
        folder = destination / ".codex/agents"
        obsolete = folder / "retired.toml"
        obsolete.write_text("owned")
        import hashlib
        state_path = _projection_state_path(destination, "codex")
        state = read_json(state_path)
        state["files"][".codex/agents/retired.toml"] = hashlib.sha256(obsolete.read_bytes()).hexdigest()
        write_json(state_path, state)
        external = self.root / "external"
        folder.rename(external)
        self.symlink(folder, external)
        with self.assertRaisesRegex(RuntimeError, "boundary|symlink"):
            install("codex", destination, components=["agents"], prune=True, force=True)
        self.assertEqual("owned", (external / "retired.toml").read_text())

    def test_projection_metadata_cannot_escape_project(self):
        destination = self.root / "project"
        init_project(destination, name="Fixture")
        external = self.root / "external"
        external.mkdir()
        self.symlink(destination / ".embraion/state", external)
        with self.assertRaisesRegex(RuntimeError, "boundary|symlink"):
            install("codex", destination, components=["config"], force=True, prune=True)
        self.assertEqual([], list(external.iterdir()))
        self.assertFalse((destination / ".codex/config.toml").exists())

    def test_projection_accepts_destination_alias_and_rejects_file_link(self):
        destination = self.root / "project"
        init_project(destination, name="Fixture")
        alias = self.root / "alias"
        self.symlink(alias, destination)
        install("codex", alias, components=["config"])
        target = destination / ".codex/config.toml"
        external = self.root / "external.toml"
        target.rename(external)
        original = external.read_bytes()
        self.symlink(target, external)
        with self.assertRaisesRegex(RuntimeError, "boundary|symlink"):
            install("codex", alias, components=["config"], force=True)
        self.assertEqual(original, external.read_bytes())

    def test_learning_eval_only_anonymous_and_legacy_counts(self):
        with patch("embraion.learning.project_root", return_value=self.root):
            for _ in range(4):
                item = observe("anonymous", "pattern", "skill", "review", "same")
            self.assertEqual(1, item["evidence"]["count"])
            for eval_id in ("one", "one", "two", "three", "four"):
                item = observe("evals", "pattern", "skill", "review", "same", eval_id=eval_id)
            self.assertEqual(4, item["evidence"]["count"])
            item = observe("evals", "pattern", "skill", "review", "same", run_id="independent", eval_id="one")
            # The later run identifies the same eval, not a fifth confirmation.
            self.assertEqual(4, item["evidence"]["count"])
            legacy = observe("legacy", "pattern", "skill", "review", "same", run_id="one")
            legacy["evidence"].pop("observation-ids")
            legacy["evidence"]["count"] = 4
            legacy["confidence"] = 0.8
            write_json(self.root / ".embraion/state/learning/legacy.json", legacy)
            with self.assertRaisesRegex(RuntimeError, "Insufficient"):
                transition("legacy", "propose")
            corrected = observe("legacy", "pattern", "skill", "review", "same", run_id="one")
            self.assertEqual(1, corrected["evidence"]["count"])

    def test_learning_repeated_run_is_not_independent_evidence(self):
        with patch("embraion.learning.project_root", return_value=self.root):
            for _ in range(4):
                item = observe("fixture", "pattern", "skill", "review", "same", run_id="run-1")
            self.assertEqual(1, item["evidence"]["count"])
            self.assertEqual(0.5, item["confidence"])
            with self.assertRaisesRegex(RuntimeError, "Insufficient"):
                transition("fixture", "propose")
            for i in range(2, 5):
                item = observe("fixture", "pattern", "skill", "review", "same", run_id=f"run-{i}", eval_id="shared-eval")
            self.assertEqual(4, item["evidence"]["count"])
            proposed = transition("fixture", "propose")
            self.assertEqual("proposed", proposed["state"])
            self.assertEqual(proposed, observe("fixture", "pattern", "skill", "review", "same", run_id="run-4", eval_id="shared-eval"))
