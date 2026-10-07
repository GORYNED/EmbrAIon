from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.cli import main
from embraion.common import framework_root
from embraion.pr_template import install_pr_template
from embraion.project import init_project

SOURCE = framework_root() / "templates" / "pull-request" / "pull-request-template.md"
REQUIRED_HEADINGS = (
    "## Changed", "## Architecture", "## Compatibility", "## Validation", "## Not run", "## Risks",
    "## Workers", "## Independent review",
)


def _run(*arguments: str) -> tuple[int, str]:
    output = io.StringIO()
    with patch("embraion.cli.resolve_project_runtime", return_value=None), contextlib.redirect_stdout(output):
        code = main(list(arguments))
    return code, output.getvalue()


class PullRequestTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def files(self) -> set[str]:
        return {path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_file()}

    def test_template_covers_the_completion_review_and_compatibility_sections(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        for heading in REQUIRED_HEADINGS:
            self.assertIn(heading, text)
        for line in ("Exact final head SHA confirmed", "Base and diff reviewed", "Source and API compatibility",
                     "Persisted-data compatibility"):
            self.assertIn(line, text)

    def test_default_init_does_not_create_a_pull_request_template(self) -> None:
        init_project(self.root, name="Fixture")
        self.assertFalse(any("pull_request_template" in name.lower() for name in self.files()))
        self.assertFalse((self.root / ".github").exists())

    def test_install_writes_the_template_once(self) -> None:
        report = install_pr_template(self.root)
        self.assertEqual({"status": "created", "path": ".github/pull_request_template.md"}, report)
        self.assertEqual({".github/pull_request_template.md"}, self.files())
        self.assertEqual(SOURCE.read_bytes(), (self.root / ".github/pull_request_template.md").read_bytes())

    def test_install_never_overwrites_an_existing_template(self) -> None:
        for relative in (".github/pull_request_template.md", "pull_request_template.md", "docs/PULL_REQUEST_TEMPLATE.md",
                         ".github/PULL_REQUEST_TEMPLATE/default.md"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                existing = root / relative
                existing.parent.mkdir(parents=True, exist_ok=True)
                existing.write_text("mine\n", encoding="utf-8")
                before = {path.relative_to(root).as_posix() for path in root.rglob("*")}
                report = install_pr_template(root)
                self.assertEqual("exists", report["status"])
                self.assertEqual("mine\n", existing.read_text(encoding="utf-8"))
                self.assertEqual(before, {path.relative_to(root).as_posix() for path in root.rglob("*")})

    def test_install_leaves_a_symbolic_link_alone(self) -> None:
        (self.root / ".github").mkdir()
        outside = self.root / "outside.md"
        outside.write_text("kept\n", encoding="utf-8")
        link = self.root / ".github/pull_request_template.md"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links are unavailable")
        self.assertEqual("exists", install_pr_template(self.root)["status"])
        self.assertEqual("kept\n", outside.read_text(encoding="utf-8"))

    def test_install_rejects_a_missing_directory(self) -> None:
        with self.assertRaises(RuntimeError):
            install_pr_template(self.root / "missing")

    def test_command_creates_then_reports_existing(self) -> None:
        code, output = _run("pr-template", "--path", str(self.root))
        self.assertEqual((0, "Created .github/pull_request_template.md\n"), (code, output))
        code, output = _run("pr-template", "--path", str(self.root))
        self.assertEqual(0, code)
        self.assertIn("already exists; left unchanged", output)
        code, output = _run("pr-template", "--path", str(self.root), "--json")
        self.assertEqual({"status": "exists", "path": ".github/pull_request_template.md"}, json.loads(output))

    def test_command_works_in_an_initialized_project(self) -> None:
        init_project(self.root, name="Fixture")
        before = self.files()
        self.assertEqual(0, _run("pr-template", "--path", str(self.root))[0])
        self.assertEqual(before | {".github/pull_request_template.md"}, self.files())


if __name__ == "__main__":
    unittest.main()
