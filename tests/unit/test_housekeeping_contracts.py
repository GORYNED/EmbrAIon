"""Task entry, overlay and CLI contracts; no real resources are removed."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from embraion import cli, runtime
from embraion.common import framework_root, read_json, read_yaml
from embraion.evals import evaluate_case
from embraion.project import init_project


class HousekeepingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_new_project_cleanup_is_opt_in_and_cannot_disable_ownership(self) -> None:
        init_project(self.root)
        manifest = read_yaml(self.root / ".embraion/project.yaml")
        self.assertFalse(manifest["housekeeping"]["on-task-start"])
        self.assertFalse(manifest["housekeeping"]["remote-branches"])
        schema = read_json(framework_root() / "schemas/project.schema.json")
        validator = Draft202012Validator(schema)
        self.assertEqual([], list(validator.iter_errors(manifest)))
        for unsafe in ({"ownership": "all"}, {"force": True}, {"on-task-start": "true"}):
            with self.subTest(unsafe=unsafe):
                value = {**manifest, "housekeeping": unsafe}
                self.assertTrue(list(validator.iter_errors(value)))

    def test_only_writable_independent_lead_entry_prepares(self) -> None:
        with patch.object(runtime, "project_root", return_value=self.root), \
             patch("embraion.worktree.prepare_task", return_value={"resources": []}) as prepare, \
             patch("embraion.worktree.update_task_state") as update:
            for role, access in (("lead", "plan"), ("lead", "read-only"),
                                 ("reviewer", "read-only"), ("worker", "workspace-write")):
                runtime.start_session("s", "t", role=role, access=access)
            prepare.assert_not_called()
            update.assert_not_called()
            runtime.start_session("s", "t", role="lead", access="workspace-write", independent=True)
            prepare.assert_called_once_with("t", host="codex", repo=self.root, independent=True)
            update.assert_called_once_with("t", "active", repo=self.root)

    def test_session_scope_must_be_explicit_and_subtasks_do_not_prepare(self) -> None:
        parser = cli.build_parser()
        with patch.object(runtime, "project_root", return_value=self.root), \
             patch("embraion.worktree.prepare_task", return_value={"resources": []}) as prepare, \
             patch("embraion.worktree.update_task_state"), \
             contextlib.redirect_stdout(io.StringIO()):
            for flags in ([], ["--subtask"]):
                args = parser.parse_args(["session", "start", "--session-id", "s",
                                          "--task", "sub", "--access", "workspace-write", *flags])
                self.assertEqual(0, args.func(args))
                self.assertFalse(read_json(self.root / ".embraion/state/session.json")["task"]["independent"])
            prepare.assert_not_called()
            args = parser.parse_args(["session", "start", "--session-id", "s", "--task", "t",
                                      "--access", "workspace-write", "--independent-task"])
            self.assertEqual(0, args.func(args))
            prepare.assert_called_once_with("t", host="codex", repo=self.root, independent=True)

    def test_unavailable_cleanup_is_reported_and_keeps_active_session(self) -> None:
        with patch.object(runtime, "project_root", return_value=self.root), \
             patch("embraion.worktree.update_task_state"), \
             patch("embraion.worktree.prepare_task", side_effect=RuntimeError("unavailable")):
            record = runtime.start_session("s", "t", access="workspace-write", independent=True)
            self.assertEqual("active", record["state"])
            self.assertEqual("housekeeping-unavailable", record["housekeeping"]["reason"])
            self.assertEqual(record, read_json(self.root / ".embraion/state/session.json"))

    def test_unknown_session_scope_type_fails_before_state_write(self) -> None:
        with patch.object(runtime, "project_root", return_value=self.root), \
             patch("embraion.worktree.prepare_task") as prepare:
            with self.assertRaises(ValueError):
                runtime.start_session("s", "t", access="workspace-write", independent="false")
            prepare.assert_not_called()
            self.assertFalse((self.root / ".embraion/state/session.json").exists())

    def test_completion_updates_same_task_and_failure_is_visible(self) -> None:
        with patch.object(runtime, "project_root", return_value=self.root):
            with patch("embraion.worktree.prepare_task", return_value={"resources": []}), \
                 patch("embraion.worktree.update_task_state"):
                runtime.start_session("s", "t", access="workspace-write")
            with patch("embraion.worktree.update_task_state") as update:
                runtime.update_session(state="completed")
                update.assert_called_once_with("t", "completed", repo=self.root)
            with patch("embraion.worktree.update_task_state", side_effect=RuntimeError("locked")):
                record = runtime.update_session(state="active")
                self.assertEqual("task-state-update-unavailable", record["housekeeping-warning"])

    def test_gc_json_dry_run_and_failed_operation_exit(self) -> None:
        output = io.StringIO()
        report = {"schema-version": 1, "dry-run": True, "cleanup-id": None,
                  "resources": [{"kind": "branch", "branch": "user", "status": "preserved",
                                 "reason": "unregistered"}]}
        args = cli.build_parser().parse_args(["worktree", "gc", "--json"])
        with patch.object(cli, "gc_report", return_value=report) as inspect, \
             contextlib.redirect_stdout(output):
            self.assertEqual(0, args.func(args))
        inspect.assert_called_once_with(base="origin/main", apply=False)
        self.assertEqual(report, json.loads(output.getvalue()))
        report["resources"][0]["status"] = "failed"
        with patch.object(cli, "gc_report", return_value=report), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, args.func(args))

    def test_read_only_or_reviewer_completion_cannot_complete_managed_task(self) -> None:
        with patch.object(runtime, "project_root", return_value=self.root), \
             patch("embraion.worktree.update_task_state") as update:
            for role, access in (("lead", "read-only"), ("lead", "plan"),
                                 ("reviewer", "read-only"), ("worker", "workspace-write")):
                runtime.start_session("s", "t", role=role, access=access)
                record = runtime.update_session(state="completed")
                self.assertEqual("completed", record["state"])
            update.assert_not_called()

    def test_prepare_flags_do_not_infer_writable_or_independent(self) -> None:
        args = cli.build_parser().parse_args(
            ["worktree", "prepare", "--task-id", "t", "--read-only", "--subtask", "--json"])
        with patch.object(cli, "prepare_task", return_value={"resources": []}) as prepare, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, args.func(args))
        self.assertFalse(prepare.call_args.kwargs["writable"])
        self.assertFalse(prepare.call_args.kwargs["independent"])

    def test_create_preserves_existing_mode_and_validates_new_resource_modes(self) -> None:
        parser = cli.build_parser()
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(cli, "create_worktree", return_value=self.root / "new") as create:
            args = parser.parse_args(["worktree", "create", "task/new"])
            self.assertEqual(0, args.func(args))
            create.assert_called_once_with("task/new", destination=None, base="origin/main",
                                           task_id=None, host="codex", independent=False)
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(cli, "create_branch", return_value="task/new") as branch:
            args = parser.parse_args(["worktree", "create", "task/new", "--branch-only"])
            self.assertEqual(0, args.func(args))
            branch.assert_called_once()
            self.assertFalse(branch.call_args.kwargs["independent"])
        for flag, expected in (("--subtask", False), ("--independent-task", True)):
            with contextlib.redirect_stdout(io.StringIO()), \
                 patch.object(cli, "create_worktree", return_value=self.root / "new") as create:
                args = parser.parse_args(["worktree", "create", "task/new", flag])
                self.assertEqual(0, args.func(args))
                self.assertEqual(expected, create.call_args.kwargs["independent"])
        for flags in (("--detach",), ("task/new", "--detach", "--path", str(self.root)),
                      ("task/new", "--branch-only", "--path", str(self.root))):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                parser.parse_args(["worktree", "create", *flags]).func(
                    parser.parse_args(["worktree", "create", *flags]))

    def test_publish_is_an_explicit_operation(self) -> None:
        args = cli.build_parser().parse_args(
            ["worktree", "publish", "--task-id", "t", "--branch", "task/new"])
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(cli, "publish_branch", return_value={"publish-id": "fixture"}) as publish:
            self.assertEqual(0, args.func(args))
            publish.assert_called_once_with("t", "task/new")

    def test_behavioral_grader_rejects_each_unsafe_claim(self) -> None:
        case = read_yaml(framework_root() / "evals/cases/worktree-housekeeping.yaml")
        fixture = read_json(framework_root() / "tests/fixtures/evals/worktree-housekeeping.json")
        self.assertTrue(evaluate_case(case, fixture)[0])
        for check in case["checks"]:
            changed = json.loads(json.dumps(fixture))
            path = check["field"].split(".")
            parent = changed
            for part in path[:-1]:
                parent = parent[part]
            parent[path[-1]] = None
            self.assertFalse(evaluate_case(case, changed)[0], check["field"])


if __name__ == "__main__":
    unittest.main()
