from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from embraion.cli import build_parser
from embraion.common import write_yaml
from embraion.project import init_project, install, projection_is_verified, projection_plan
from embraion.report import (
    read_report_contract, render_report_template, validate_report,
)


CONTRACT = {
    "schema-version": 1,
    "sections": ["Changed", "Architecture", "Validation", "Risks", "Workers"],
    "workers": {
        "section": "Workers",
        "task-status": ["completed", "cancelled", "incomplete"],
        "columns": ["Status", "Worker", "Role", "Billing", "Access", "Data", "Runs", "Cost", "Routing", "Validation"],
    },
    "pull-request": {"section": "Changed"},
    "guidance": ["Report each external worker attempt before it starts."],
}
TABLE = (
    "| Status | Worker | Role | Billing | Access | Data | Runs | Cost | Routing | Validation |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    "| done | reviewer | review | subscription | read-only | PRIVATE | 1 | n/a | substantial | passed |\n"
)
GOOD = (
    "Summary line before the sections.\n\n"
    "## Changed\n\nPR: https://github.com/example/app/pull/12\n\n"
    "## Architecture\n\nNo change.\n\n"
    "```text\n## Risks\n| not | a | table |\n```\n\n"
    "## Validation\n\nFast passed.\n\n"
    "## Risks\n\nNone.\n\n"
    "## Workers\n\nTask status: completed\n\n" + TABLE
)


class ReportContractTests(unittest.TestCase):
    def codes(self, text: str, **options) -> list[str]:
        return [issue["code"] for issue in validate_report(text, CONTRACT, **options)]

    def test_accepts_a_complete_final_report_and_ignores_fenced_content(self) -> None:
        self.assertEqual([], self.codes(GOOD, pull_request=True))
        bold = GOOD.replace("## ", "**").replace("Changed\n", "Changed**\n").replace("Architecture\n", "Architecture**\n")
        bold = bold.replace("Validation\n", "Validation**\n").replace("Risks\n", "Risks**\n").replace("Workers\n", "Workers**\n")
        self.assertEqual([], self.codes(bold))

    def test_rejects_missing_reordered_repeated_or_extra_sections(self) -> None:
        self.assertEqual(["report-sections"], self.codes(GOOD.replace("## Risks\n\nNone.\n\n", "")))
        reordered = GOOD.replace("## Architecture\n\nNo change.", "## Tmp\n\nx").replace(
            "## Validation\n\nFast passed.", "## Validation\n\nFast passed.\n\n## Architecture\n\nNo change.")
        self.assertIn("report-sections", self.codes(reordered))
        self.assertIn("report-extra-section", self.codes(reordered))
        self.assertEqual(["report-sections"], self.codes(GOOD.replace("## Risks\n\nNone.", "## Risks\n\nNone.\n\n## Risks\n\nAgain.")))

    def test_workers_status_columns_location_and_count(self) -> None:
        self.assertEqual(["workers-task-status"], self.codes(GOOD.replace("Task status: completed\n\n", "")))
        self.assertEqual(["workers-task-status"], self.codes(GOOD.replace("completed\n", "finished\n")))
        moved = GOOD.replace("Task status: completed\n\n" + TABLE, TABLE + "\nTask status: completed\n")
        self.assertEqual(["workers-task-status"], self.codes(moved))
        self.assertEqual(["workers-columns", "workers-table-count"],
                         sorted(self.codes(GOOD.replace("| Cost | Routing", "| Spend | Routing"))))
        twice = GOOD.replace("## Risks\n\nNone.", "## Risks\n\n" + TABLE)
        self.assertEqual(["workers-table-count", "workers-table-location"], sorted(self.codes(twice)))

    def test_table_cells_reject_paths_credentials_and_raw_content(self) -> None:
        for value, code in (("/home/user/run.log", "workers-absolute-path"),
                            ("C:\\\\work\\\\run.log", "workers-absolute-path"),
                            ("api_key=abcdef0123456789", "workers-credential"),
                            ("```diff```", "workers-raw-content")):
            with self.subTest(value=value):
                self.assertEqual([code], self.codes(GOOD.replace("| passed |", f"| {value} |")))

    def test_pull_request_link_is_required_only_when_requested(self) -> None:
        without = GOOD.replace("PR: https://github.com/example/app/pull/12", "Branch pushed.")
        self.assertEqual([], self.codes(without))
        self.assertEqual(["pull-request-link"], self.codes(without, pull_request=True))

    def test_intermediate_updates_reject_workers_table_or_section(self) -> None:
        self.assertEqual([], self.codes("Reviewing the parser now.\n", kind="intermediate"))
        self.assertEqual(["intermediate-workers-table"], self.codes("Progress.\n\n" + TABLE, kind="intermediate"))
        self.assertEqual(["intermediate-workers-section", "intermediate-workers-table"],
                         sorted(self.codes("## Workers\n\n" + TABLE, kind="intermediate")))

    def test_template_cli_and_skill_projection_follow_the_project_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="ReportContract")
            write_yaml(project / ".embraion/report.yaml", CONTRACT)
            contract = read_report_contract(project)
            template = render_report_template(contract)
            self.assertEqual([], [issue["code"] for issue in validate_report(
                template.split("\nRules:")[0].replace("|incomplete", "") + TABLE.splitlines()[2] + "\n", contract)])
            self.assertIn("Report each external worker attempt before it starts.", template)

            report = project / "report.md"
            report.write_text(GOOD.replace("## Risks\n\nNone.\n\n", ""), encoding="utf-8")
            parsed = build_parser().parse_args(["report", "validate", str(report), "--json",
                                                "--contract", str(project / ".embraion/report.yaml")])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(1, parsed.func(parsed))
            self.assertFalse(json.loads(output.getvalue())["valid"])

            install("claude-code", project, components=["skills"])
            skill = (project / ".claude/skills/orchestration/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Project completion report contract", skill)
            self.assertIn("| Status | Worker | Role |", skill)
            self.assertTrue(projection_is_verified(projection_plan("claude-code", project, components=["skills"])))
            contract["guidance"] = ["Changed rule."]
            write_yaml(project / ".embraion/report.yaml", contract)
            self.assertIn(".claude/skills/orchestration/SKILL.md",
                          projection_plan("claude-code", project, components=["skills"])["update"])

    def test_invalid_contract_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="BrokenContract")
            with self.assertRaisesRegex(RuntimeError, "Missing"):
                read_report_contract(project)
            write_yaml(project / ".embraion/report.yaml",
                       {**CONTRACT, "workers": {**CONTRACT["workers"], "section": "Team"}})
            with self.assertRaisesRegex(RuntimeError, "not a listed section"):
                read_report_contract(project)
            write_yaml(project / ".embraion/report.yaml", {**CONTRACT, "extra": True})
            with self.assertRaisesRegex(RuntimeError, "Invalid"):
                read_report_contract(project)


if __name__ == "__main__":
    unittest.main()
