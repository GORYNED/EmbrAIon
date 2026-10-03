from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root
from embraion.project import generate_host, init_project, install, projection_is_verified, projection_plan


_path_open = Path.open


def windows_text_open(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
    """Exercise Windows default text writes even on Linux CI workers."""
    if "b" not in mode and any(flag in mode for flag in "wax") and newline is None:
        newline = "\r\n"
    return _path_open(path, mode, buffering, encoding, errors, newline)


class AgentProjectionNewlineTests(unittest.TestCase):
    def _checkout(self, project: Path, host: str) -> dict[str, bytes]:
        init_project(project, name="LfCheckout")
        generate_host(framework_root(), host, project, components=["agents"], project=project)
        directory = ".claude/agents" if host == "claude-code" else ".github/agents"
        files = {}
        for path in sorted((project / directory).glob("*.md")):
            # Model tracked LF files checked out without a local ownership ledger.
            content = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(content)
            files[path.relative_to(project).as_posix()] = content
        self.assertEqual(7, len(files))
        return files

    def test_lf_checkout_verifies_under_windows_default_text_writes(self) -> None:
        for host in ("claude-code", "copilot"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                files = self._checkout(project, host)
                for opener in (_path_open, windows_text_open):
                    with self.subTest(opener=opener.__name__), patch.object(Path, "open", opener):
                        plan = projection_plan(host, project, components=["agents"])
                        self.assertTrue(projection_is_verified(plan), plan)
                        self.assertEqual(set(files), set(plan["unchanged"]))
                for relative, content in files.items():
                    self.assertEqual(content, (project / relative).read_bytes())

    def test_real_agent_edit_still_conflicts_and_install_preserves_it(self) -> None:
        for host in ("claude-code", "copilot"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                files = self._checkout(project, host)
                relative = next(name for name in files if "/reviewer." in name)
                edited = files[relative] + b"\nLocal reviewer instruction.\n"
                (project / relative).write_bytes(edited)
                with patch.object(Path, "open", windows_text_open):
                    plan = projection_plan(host, project, components=["agents"])
                    self.assertEqual([relative], plan["conflict"])
                    with self.assertRaisesRegex(RuntimeError, "Projection conflicts"):
                        install(host, project, components=["agents"])
                self.assertEqual(edited, (project / relative).read_bytes())


if __name__ == "__main__":
    unittest.main()
