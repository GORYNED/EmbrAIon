from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from embraion.check import planned_checks
from embraion.cli import main
from embraion.contracts import PROJECT_CONTRACT_SLOTS, project_contract_status
from embraion.decisions import check_decisions, decisions_folder, new_decision
from embraion.common import framework_root
from embraion.validation import collect_project_config_issues


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class DecisionFixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        self.write("README.md", "fixture\n")

    def write(self, path: str, value: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")

    def config(self, value: dict | None = None) -> None:
        self.write(".embraion/decisions.yaml", yaml.safe_dump(value or {"triggers": []}) if value != {} else "{}\n")

    def knowledge(self, **slots: str) -> None:
        self.write(".embraion/knowledge.yaml", yaml.safe_dump({"slots": slots}))

    def commit(self, message: str = "change") -> str:
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def start(self) -> None:
        """Commit the fixture as the base and branch off it."""
        self.commit("base")
        git(self.root, "checkout", "-b", "work")

    def check(self, **options: object) -> dict:
        return check_decisions(self.root, base_ref="main", **options)


class DetectionTests(DecisionFixture):
    def test_new_package_fails_until_a_record_or_waiver_is_present(self) -> None:
        self.config({})
        self.start()
        self.write("libs/core/package.json", "{}\n")
        self.commit()
        result = self.check()
        self.assertFalse(result["passed"])
        self.assertEqual("missing-record", result["outcome"])
        self.assertEqual([{"trigger": "package-added-or-removed", "path": "libs/core/package.json", "change": "added"}],
                         result["triggers"])
        self.write("package.json", "{}\n")  # `**/` also matches the repository root
        self.commit("root package")
        self.assertIn("package.json", [item["path"] for item in self.check()["triggers"]])
        git(self.root, "reset", "--hard", "HEAD~1")
        self.write("docs/architecture/decisions/0001-core-package.md", "# 1. Core package\n")
        self.commit()
        result = self.check()
        self.assertTrue(result["passed"])
        self.assertEqual("recorded", result["outcome"])
        self.assertEqual(["docs/architecture/decisions/0001-core-package.md"], result["records"])

    def test_change_without_a_trigger_is_not_affected(self) -> None:
        self.config({})
        self.write("package.json", "{}\n")
        self.start()
        self.write("src/module.py", "print(1)\n")
        # Modifying an existing manifest is not a default trigger.
        self.write("package.json", '{"name": "x"}\n')
        self.commit()
        result = self.check()
        self.assertEqual(("no-trigger", True), (result["outcome"], result["passed"]))

    def test_index_or_template_alone_does_not_count_as_a_record(self) -> None:
        self.config({})
        self.start()
        self.write("a/package.json", "{}\n")
        self.write("docs/architecture/decisions/README.md", "# index\n")
        self.write("docs/architecture/decisions/0000-template.md", "# template\n")
        self.commit()
        self.assertEqual("missing-record", self.check()["outcome"])

    def test_commit_trailer_and_flag_waive_the_record(self) -> None:
        self.config({})
        self.start()
        self.write("a/package.json", "{}\n")
        self.commit("add package\n\nDecision-Waiver: vendored copy, no ownership change")
        result = self.check()
        self.assertTrue(result["passed"])
        self.assertEqual("waived", result["outcome"])
        self.assertEqual(["vendored copy, no ownership change"], result["waivers"])
        git(self.root, "reset", "--hard", "main")
        self.write("a/package.json", "{}\n")
        self.commit("add package")
        self.assertFalse(self.check()["passed"])
        self.assertFalse(self.check(waiver="  ")["passed"])
        self.assertEqual("waived", self.check(waiver="generated fixture")["outcome"])

    def test_declared_triggers_replace_the_defaults_and_match_paths_changes_and_patterns(self) -> None:
        self.write("Assets/Runtime/Core.asmdef", '{"references": ["A"]}\n')
        self.write("formats/a.txt", "one\ntwo\nthree\nfour\nfive\n")
        self.config({"triggers": [
            {"id": "assembly-references", "paths": ["**/*.asmdef"], "changes": ["modified"], "patterns": ['"references"']},
            {"paths": ["formats/**"], "changes": ["renamed"]},
        ]})
        self.start()
        self.write("pkg/package.json", "{}\n")  # a default trigger, replaced by the declared ones
        self.write("Assets/Runtime/Other.asmdef", "{}\n")  # added, but only modifications are declared
        self.write("Assets/Runtime/Core.asmdef", '{"name": "Core", "references": ["A", "B"]}\n')
        git(self.root, "mv", "formats/a.txt", "formats/b.txt")
        self.commit()
        self.assertEqual({("assembly-references", "Assets/Runtime/Core.asmdef", "modified"),
                          ("declared", "formats/b.txt", "renamed")},
                         {(item["trigger"], item["path"], item["change"]) for item in self.check()["triggers"]})

    def test_pattern_ignores_unrelated_changed_lines(self) -> None:
        self.write("Packages/manifest.json", '{\n  "dependencies": {"a": "1"},\n  "scopedRegistries": []\n}\n')
        self.config({"triggers": [{"paths": ["Packages/manifest.json"], "patterns": ['^\\s*"[a-z.]+": "\\d']}]})
        self.start()
        self.write("Packages/manifest.json", '{\n  "dependencies": {"a": "1"},\n  "scopedRegistries": [{}]\n}\n')
        self.commit()
        self.assertEqual("no-trigger", self.check()["outcome"])
        self.write("Packages/manifest.json", '{\n  "com.vendor.pkg": "2.0.0",\n  "scopedRegistries": [{}]\n}\n')
        self.commit()
        self.assertEqual("missing-record", self.check()["outcome"])

    def test_decisions_slot_sets_the_folder(self) -> None:
        self.config({})
        self.knowledge(decisions="docs/adr")
        self.start()
        self.write("a/package.json", "{}\n")
        self.write("docs/architecture/decisions/0001-x.md", "# x\n")  # the default folder no longer counts
        self.commit()
        self.assertEqual("missing-record", self.check()["outcome"])
        self.write("docs/adr/0001-x.md", "# x\n")
        self.commit()
        result = self.check()
        self.assertEqual(("recorded", "docs/adr"), (result["outcome"], result["folder"]))

    def test_explicit_empty_triggers_declare_none(self) -> None:
        self.config({"triggers": []})
        self.start()
        self.write("a/package.json", "{}\n")
        self.commit()
        self.assertEqual("no-trigger", self.check()["outcome"])

    def test_missing_configuration_is_skipped_or_failed_when_required(self) -> None:
        self.start()
        self.assertEqual(("skipped", True), (self.check()["status"], self.check()["passed"]))
        self.assertFalse(self.check(require_config=True)["passed"])

    def test_invalid_configuration_and_refs_fail_closed(self) -> None:
        self.start()
        for config in ({"unknown": 1}, {"triggers": [{"paths": []}]}, {"triggers": [{"paths": ["a"], "patterns": ["("]}]},
                       {"triggers": [{"paths": ["a"], "changes": ["moved"]}]}):
            with self.subTest(config=config):
                self.write(".embraion/decisions.yaml", yaml.safe_dump(config))
                with self.assertRaises(RuntimeError):
                    self.check()
        self.config({})
        with self.assertRaises(RuntimeError):
            check_decisions(self.root, base_ref="missing-ref")

    def test_unsafe_folder_is_rejected(self) -> None:
        for folder in ("../outside", "/abs", "a//b", "a\\b"):
            with self.subTest(folder=folder):
                self.knowledge(decisions=folder)
                with self.assertRaises(RuntimeError):
                    decisions_folder(self.root)

    def test_command_exit_codes_and_check_integration(self) -> None:
        self.config({})
        self.start()
        self.write("a/package.json", "{}\n")
        self.commit()
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            code = main(["decisions", "check", "--path", str(self.root), "--base-ref", "main", "--json"])
        self.assertEqual(1, code)
        self.assertEqual("missing-record", json.loads(output.getvalue())["outcome"])
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["decisions", "check", "--path", str(self.root), "--base-ref", "main",
                                      "--waiver", "fixture package"]))
        with_ref = {item["id"]: item for item in planned_checks(self.root, base_ref="origin/main")}
        self.assertEqual(["decisions", "check", "--require-config", "--path", ".", "--base-ref", "origin/main", "--json"],
                         with_ref["decisions"]["argv"])
        without_ref = {item["id"]: item for item in planned_checks(self.root)}
        self.assertIsNone(without_ref["decisions"]["argv"])
        self.assertEqual("needs --base-ref", without_ref["decisions"]["not-run"])
        (self.root / ".embraion/decisions.yaml").unlink()
        self.assertNotIn("decisions", [item["id"] for item in planned_checks(self.root)])


class ScaffoldTests(DecisionFixture):
    def new(self, title: str = "Use a shared library", **options: object) -> dict:
        return new_decision(title, self.root, day="2026-10-07", **options)

    def test_empty_project_gets_folder_template_index_and_first_record(self) -> None:
        result = self.new()
        folder = "docs/architecture/decisions"
        self.assertEqual("0001", result["number"])
        self.assertEqual([f"{folder}/0001-use-a-shared-library.md"], result["paths"])
        self.assertEqual([f"{folder}/0000-template.md", f"{folder}/README.md"], result["created"])
        record = (self.root / result["paths"][0]).read_text(encoding="utf-8")
        self.assertTrue(record.startswith("# ADR 0001: Use a shared library\n"))
        self.assertIn("- Status: Proposed\n- Date: 2026-10-07\n", record)
        self.assertNotIn("{{", record)
        index = (self.root / folder / "README.md").read_text(encoding="utf-8")
        self.assertTrue(index.endswith("| [`0001-use-a-shared-library.md`](0001-use-a-shared-library.md) | Proposed | Use a shared library |\n"))

    def test_numbers_continue_and_are_never_reused(self) -> None:
        self.new("First")
        self.new("Second")
        folder = self.root / "docs/architecture/decisions"
        (folder / "0002-second.md").unlink()  # the index still remembers 0002
        self.assertEqual("0003", self.new("Third")["number"])
        self.commit()
        (folder / "0003-third.md").unlink()
        self.commit("remove")
        self.assertEqual("0004", self.new("Fourth")["number"], "history keeps a deleted number reserved")

    def test_number_reserved_on_another_branch_is_not_reused(self) -> None:
        self.new("First")
        self.start()
        git(self.root, "checkout", "-b", "other")
        self.new("Elsewhere")
        self.commit("other")
        git(self.root, "checkout", "work")
        self.assertEqual("0003", self.new("Third")["number"])

    def test_localized_pair_status_slug_and_existing_numbering_width(self) -> None:
        self.knowledge(decisions="docs/decisions")
        self.write("docs/decisions/012-old.md", "# old\n")
        result = self.new("Ограничить зависимости", locales=["ru"], slug="limit-dependencies", status="Accepted")
        self.assertEqual("013", result["number"])
        self.assertEqual(["docs/decisions/013-limit-dependencies.md", "docs/decisions/013-limit-dependencies-ru.md"],
                         result["paths"])
        self.assertIn("(013-limit-dependencies.md) ([ru](013-limit-dependencies-ru.md))",
                      (self.root / "docs/decisions/README.md").read_text(encoding="utf-8"))
        localized = (self.root / result["paths"][1]).read_text(encoding="utf-8")
        self.assertIn("# ADR 013: Ограничить зависимости", localized)
        self.assertIn("- Status: Accepted", localized)

    def test_locale_template_is_preferred_when_present(self) -> None:
        self.write("docs/architecture/decisions/0000-template.md", "{{number}} {{title}} en\n")
        self.write("docs/architecture/decisions/0000-template-ru.md", "{{number}} {{title}} ru\n")
        result = self.new("Layers", locales=["ru"])
        self.assertEqual(["0001 Layers en\n", "0001 Layers ru\n"],
                         [(self.root / path).read_text(encoding="utf-8") for path in result["paths"]])

    def test_existing_index_table_gets_a_row_matching_its_columns(self) -> None:
        self.write("docs/architecture/decisions/README.md",
                   "# Decisions\n\n| № | Decision | Date | Status | Owner |\n| --- | --- | --- | --- | --- |\n"
                   "| [0001](0001-a.md) | A | 2026-01-01 | Accepted | team |\n\nTrailing notes.\n")
        self.write("docs/architecture/decisions/0001-a.md", "# a\n")
        self.new("B")
        text = (self.root / "docs/architecture/decisions/README.md").read_text(encoding="utf-8")
        self.assertIn("| [0001](0001-a.md) | A | 2026-01-01 | Accepted | team |\n"
                      "| [`0002-b.md`](0002-b.md) | B | 2026-10-07 | Proposed |  |\n\nTrailing notes.", text)

    def test_pipe_in_title_and_crlf_index_are_preserved(self) -> None:
        self.write("docs/architecture/decisions/README.md", "# D\r\n\r\n| ADR | Decision |\r\n| --- | --- |\r\n")
        self.new("A | B")
        data = (self.root / "docs/architecture/decisions/README.md").read_bytes()
        self.assertEqual(b"# D\r\n\r\n| ADR | Decision |\r\n| --- | --- |\r\n| [`0001-a-b.md`](0001-a-b.md) | A \\| B |\r\n", data)

    def test_title_text_is_not_expanded_as_a_template_token(self) -> None:
        self.assertIn("# ADR 0001: {{status}}", (self.root / self.new("{{status}}", slug="token")["paths"][0]).read_text(encoding="utf-8"))

    def test_index_without_a_table_gets_one(self) -> None:
        self.write("docs/architecture/decisions/README.md", "# Decisions\n")
        self.new("B")
        text = (self.root / "docs/architecture/decisions/README.md").read_text(encoding="utf-8")
        self.assertEqual("# Decisions\n\n| ADR | Status | Decision |\n| --- | --- | --- |\n"
                         "| [`0001-b.md`](0001-b.md) | Proposed | B |\n", text)

    def test_same_inputs_give_the_same_files(self) -> None:
        self.new("One", locales=["ru"])
        first = {path: path.read_bytes() for path in sorted((self.root / "docs").rglob("*.md"))}
        git(self.root, "clean", "-fdq")
        self.new("One", locales=["ru"])
        self.assertEqual(first, {path: path.read_bytes() for path in sorted((self.root / "docs").rglob("*.md"))})

    def test_invalid_input_is_rejected_before_writing(self) -> None:
        for title, options in (("", {}), ("A\nB", {}), ("Только русский", {}), ("Ok", {"locales": ["RU"]}),
                               ("Ok", {"status": ""}), ("Ok", {"slug": "Not Kebab"}), ("Ok", {"day": "yesterday"})):
            with self.subTest(title=title, options=options):
                with self.assertRaises((RuntimeError, ValueError)):
                    new_decision(title, self.root, **options)
        self.assertFalse((self.root / "docs").exists())

    def test_symbolic_link_index_is_refused(self) -> None:
        folder = self.root / "docs/architecture/decisions"
        folder.mkdir(parents=True)
        (self.root / "elsewhere.md").write_text("| a | b |\n", encoding="utf-8")
        (folder / "README.md").symlink_to(self.root / "elsewhere.md")
        with self.assertRaises(RuntimeError):
            self.new()

    def test_folder_slot_does_not_break_checkpoints_or_context(self) -> None:
        from embraion.checkpoints import create_checkpoint
        from embraion.context import build_context
        from embraion.project import init_project
        init_project(self.root, name="Fixture")
        (self.root / "docs/adr").mkdir(parents=True)
        self.knowledge(decisions="docs/adr")
        report = create_checkpoint("cp", task_id="t", phase="planning", project=self.root)
        self.assertNotIn("docs/adr", str(report))
        context = build_context("architecture decision", "lead", "PRIVATE", project=self.root, persist=False)
        self.assertIn({"id": "slot:decisions", "reason": "directory"}, context["excluded"])

    def test_command_creates_a_record(self) -> None:
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            code = main(["adr", "new", "Split the runtime", "--path", str(self.root), "--locale", "ru",
                         "--date", "2026-10-07", "--json"])
        self.assertEqual(0, code)
        self.assertEqual("0001", json.loads(output.getvalue())["number"])


class SlotTests(DecisionFixture):
    def test_decisions_slot_is_a_known_contract_slot_that_binds_a_folder(self) -> None:
        self.assertIn("decisions", PROJECT_CONTRACT_SLOTS)
        self.knowledge(decisions="docs/adr")
        row = lambda: next(item for item in project_contract_status(yaml.safe_load(
            (self.root / ".embraion/knowledge.yaml").read_text(encoding="utf-8")), self.root)["slots"]
            if item["id"] == "decisions")
        self.assertFalse(row()["exists"])
        (self.root / "docs/adr").mkdir(parents=True)
        self.assertTrue(row()["exists"])

    def test_project_config_validation_accepts_a_folder_slot_and_reads_the_decisions_file(self) -> None:
        self.knowledge(decisions="docs/adr")
        self.config({})
        (self.root / "docs/adr").mkdir(parents=True)
        self.assertEqual([], collect_project_config_issues(self.root, framework_root()))
        (self.root / "docs/adr").rmdir()
        self.assertEqual([("config-path", ".embraion/knowledge.yaml")],
                         [(item["code"], item["path"]) for item in collect_project_config_issues(self.root, framework_root())])


if __name__ == "__main__":
    unittest.main()
