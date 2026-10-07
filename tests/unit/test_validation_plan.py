from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from embraion.common import read_yaml, write_yaml
from embraion.policy import read_validation_config
from embraion.project import init_project
from embraion.project_validation import run_validation_profile, validation_profile_specs
from embraion.validation_plan import (
    build_plan,
    collect_changed_paths,
    compute_plan,
    explain_plan,
    resolve_run_plan,
    write_plan,
)


def plan_config() -> dict[str, Any]:
    """A neutral project: a library, its docs, and a build script."""
    return {
        "profiles": {
            "affected": ["echo affected"],
            "full": ["echo lint", "echo unit", "echo package"],
        },
        "areas": {
            "library": {"paths": ["src/**"], "commands": ["echo unit"]},
            "docs": {"paths": ["docs/**", "*.md"], "commands": ["echo docs"]},
            "build": {"paths": ["tools/build/**"], "profiles": ["full"]},
        },
        "impact": [
            {"id": "schema-change", "paths": ["src/schema/**"], "areas": ["docs"], "full": "data-migration"},
            {"id": "build-files", "paths": ["pyproject.toml"], "areas": ["build"]},
        ],
        "full-reasons": ["data-migration", "release-gate"],
    }


def write_config(project: Path, config: dict[str, Any]) -> None:
    write_yaml(project / ".embraion" / "validation.yaml", config)


class PlanConfigTests(unittest.TestCase):
    def _project(self, config: dict[str, Any]) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        init_project(project, name="Consumer")
        write_config(project, config)
        return project

    def _rejected(self, mutate: Any, fragment: str) -> None:
        config = copy.deepcopy(plan_config())
        mutate(config)
        project = self._project(config)
        with self.assertRaises(RuntimeError) as caught:
            read_validation_config(project)
        self.assertIn(fragment, str(caught.exception))

    def test_valid_plan_keys_are_accepted(self) -> None:
        project = self._project(plan_config())
        self.assertEqual(["library", "docs", "build"], list(read_validation_config(project)["areas"]))

    def test_project_without_plan_keys_is_unchanged(self) -> None:
        project = self._project({"profiles": {"fast": ["echo fast"]}})
        self.assertEqual({"profiles": {"fast": ["echo fast"]}}, read_validation_config(project))

    def test_unknown_area_in_rule_is_rejected(self) -> None:
        self._rejected(lambda c: c["impact"][0].update(areas=["nowhere"]), "unknown area(s): nowhere")

    def test_unknown_profile_in_area_is_rejected(self) -> None:
        self._rejected(lambda c: c["areas"]["build"].update(profiles=["missing"]), "unknown profile(s): missing")

    def test_reason_outside_closed_list_is_rejected(self) -> None:
        self._rejected(lambda c: c["impact"][0].update(full="because"), "not in full-reasons")

    def test_full_rule_without_declared_list_is_rejected(self) -> None:
        def mutate(config: dict[str, Any]) -> None:
            del config["full-reasons"]
        self._rejected(mutate, "(none declared)")

    def test_escalation_needs_a_full_profile(self) -> None:
        def mutate(config: dict[str, Any]) -> None:
            del config["profiles"]["full"]
            config["areas"]["build"] = {"paths": ["tools/build/**"], "commands": ["echo b"]}
        self._rejected(mutate, "requires a 'full' profile")

    def test_bad_globs_are_rejected(self) -> None:
        for pattern in (" ", "/abs/**", "src/../x", "src/[a", "/".join(["**"] * 10) + "/x"):
            with self.subTest(pattern=pattern):
                self._rejected(lambda c, p=pattern: c["areas"]["library"].update(paths=[p]), "path pattern")

    def test_duplicate_rule_ids_are_rejected(self) -> None:
        self._rejected(lambda c: c["impact"][1].update(id="schema-change"), "duplicate rule id")

    def test_unknown_default_area_is_rejected(self) -> None:
        self._rejected(lambda c: c.update({"default-area": "ghost"}), "default-area names unknown area")

    def test_impact_requires_areas(self) -> None:
        def mutate(config: dict[str, Any]) -> None:
            del config["areas"]
        self._rejected(mutate, "require 'areas'")

    def test_shape_errors_come_from_the_schema(self) -> None:
        self._rejected(lambda c: c["areas"]["library"].update(extra=1), "Additional properties")
        self._rejected(lambda c: c["areas"]["library"].pop("commands"), "is not valid under any")
        self._rejected(lambda c: c["impact"][0].pop("areas") and c["impact"][0].pop("full"), "is not valid under any")


INPUTS = {"base-ref": "main", "base-sha": "a" * 40, "head-ref": "HEAD", "head-sha": "b" * 40,
          "merge-base-sha": "a" * 40, "include-worktree": False}


def plan_for(profile: str, paths: list[str], config: dict[str, Any] | None = None,
             justification: str | None = None) -> dict[str, Any]:
    config = config or plan_config()
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        init_project(project, name="Consumer")
        write_config(project, config)
        specs = validation_profile_specs(project)
        config = read_validation_config(project)
    return compute_plan(config, specs, profile, paths, INPUTS, justification)


def commands_of(plan: dict[str, Any]) -> list[str]:
    return [item["command"] for item in plan["selected-commands"]]


class PlanRuleTests(unittest.TestCase):
    def test_area_paths_select_area_commands(self) -> None:
        plan = plan_for("affected", ["src/core/a.py"])
        self.assertEqual(["echo unit"], commands_of(plan))
        self.assertEqual(["library"], [item["area"] for item in plan["selected-areas"]])
        self.assertEqual(["docs", "build"], [item["area"] for item in plan["skipped-areas"]])
        self.assertEqual("selected", plan["status"])
        self.assertIsNone(plan["escalation"])
        self.assertIsNone(plan["fallback"])
        self.assertEqual(["echo affected"], [item["command"] for item in plan["skipped-commands"]])

    def test_area_profiles_expand_to_profile_commands(self) -> None:
        plan = plan_for("affected", ["tools/build/make.py"])
        self.assertEqual(["echo lint", "echo unit", "echo package"], commands_of(plan))
        self.assertEqual(["area:build"], plan["selected-commands"][0]["sources"])

    def test_commands_are_deduplicated_in_area_order(self) -> None:
        plan = plan_for("affected", ["tools/build/make.py", "src/a.py", "README.md"])
        self.assertEqual(["echo unit", "echo docs", "echo lint", "echo package"], commands_of(plan))
        self.assertEqual(["area:library", "area:build"], plan["selected-commands"][0]["sources"])

    def test_rule_adds_areas_and_records_matches_in_declared_order(self) -> None:
        plan = plan_for("affected", ["pyproject.toml", "src/schema/x.sql"], justification=None)
        self.assertEqual(["schema-change", "build-files"], [item["rule"] for item in plan["matched-rules"]])
        self.assertEqual(["library", "docs", "build"], [item["area"] for item in plan["selected-areas"]])
        self.assertEqual(["schema-change"], plan["selected-areas"][1]["rules"])

    def test_rule_order_decides_the_escalation_reason(self) -> None:
        config = plan_config()
        config["impact"].insert(0, {"id": "release-files", "paths": ["VERSION"], "full": "release-gate"})
        plan = plan_for("affected", ["src/schema/x.sql", "VERSION"], config)
        self.assertEqual({"reason": "release-gate", "source": "rule:release-files"}, plan["escalation"])
        self.assertEqual(["echo lint", "echo unit", "echo package", "echo docs"], commands_of(plan))
        self.assertEqual([], plan["skipped-areas"])

    def test_rule_escalation_selects_the_full_profile(self) -> None:
        plan = plan_for("affected", ["src/schema/x.sql"])
        self.assertEqual({"reason": "data-migration", "source": "rule:schema-change"}, plan["escalation"])
        self.assertEqual(["echo lint", "echo unit", "echo package", "echo docs"], commands_of(plan))

    def test_justification_escalates_and_must_be_in_the_closed_list(self) -> None:
        plan = plan_for("affected", ["src/a.py"], justification="release-gate")
        self.assertEqual({"reason": "release-gate", "source": "justification"}, plan["escalation"])
        self.assertIn("echo package", commands_of(plan))
        with self.assertRaises(RuntimeError) as caught:
            plan_for("affected", ["src/a.py"], justification="because")
        self.assertIn("not in full-reasons", str(caught.exception))

    def test_full_profile_requires_a_listed_justification(self) -> None:
        with self.assertRaises(RuntimeError) as caught:
            plan_for("full", ["src/a.py"])
        self.assertIn("--full-justification", str(caught.exception))
        plan = plan_for("full", ["src/a.py"], justification="release-gate")
        self.assertEqual(["echo lint", "echo unit", "echo package"], commands_of(plan))

    def test_unmatched_path_falls_back_to_the_whole_profile(self) -> None:
        plan = plan_for("affected", ["misc/unknown.bin", "src/a.py"])
        self.assertEqual({"reason": "unmatched-paths", "paths": ["misc/unknown.bin"]}, plan["fallback"])
        self.assertEqual(["echo affected", "echo unit"], commands_of(plan))
        self.assertEqual([], plan["skipped-areas"])

    def test_default_area_replaces_the_fallback(self) -> None:
        config = plan_config()
        config["default-area"] = "library"
        plan = plan_for("affected", ["misc/unknown.bin"], config)
        self.assertIsNone(plan["fallback"])
        self.assertEqual(["echo unit"], commands_of(plan))
        self.assertEqual(["misc/unknown.bin"], plan["selected-areas"][0]["paths"])

    def test_empty_change_is_skipped_never_a_pass(self) -> None:
        plan = plan_for("affected", [])
        self.assertEqual("skipped", plan["status"])
        self.assertEqual("no changed paths", plan["skip-reason"])
        self.assertEqual([], plan["selected-commands"])

    def test_selected_areas_without_commands_are_skipped(self) -> None:
        config = plan_config()
        config["profiles"]["empty"] = []
        config["areas"]["docs"] = {"paths": ["docs/**"], "profiles": ["empty"]}
        plan = plan_for("affected", ["docs/a.md"], config)
        self.assertEqual("skipped", plan["status"])
        self.assertIn("no commands", plan["skip-reason"])

    def test_plan_is_deterministic_and_independent_of_input_order(self) -> None:
        first = plan_for("affected", ["src/b.py", "docs/a.md", "src/a.py"])
        second = plan_for("affected", ["src/a.py", "src/b.py", "docs/a.md", "src/a.py"])
        self.assertEqual(json.dumps(first, indent=2), json.dumps(second, indent=2))
        self.assertEqual(1, first["schema-version"])
        self.assertEqual(["docs/a.md", "src/a.py", "src/b.py"], first["changed-paths"])

    def test_explain_states_why_each_decision_was_made(self) -> None:
        text = explain_plan(plan_for("affected", ["src/schema/x.sql"]))
        for fragment in (
            "Validation plan for profile 'affected'",
            "src/schema/x.sql",
            "schema-change: 1 path(s) -> areas docs; full escalation (data-migration)",
            "library: selected by 1 changed path(s)",
            "Escalation: full profile because 'data-migration' (rule:schema-change)",
            "echo package  [profile:full]",
            "Result: run the selected commands",
        ):
            self.assertIn(fragment, text)
        skipped = explain_plan(plan_for("affected", ["docs/a.md"]))
        self.assertIn("library: no changed path matched its paths or an impact rule", skipped)
        self.assertIn("echo affected: no selected area proves it", skipped)
        self.assertIn("Result: skipped - ", explain_plan(plan_for("affected", [])))


def git(repo: Path, *arguments: str) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *arguments],
        check=True, capture_output=True, text=True, env=environment,
    ).stdout.strip()


class PlanGitTests(unittest.TestCase):
    def _repo(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "commit.gpgsign", "false")
        init_project(repo, name="Consumer")
        write_config(repo, plan_config())
        (repo / ".gitignore").write_text(".embraion/state/\n", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src" / "a.py").write_text("a\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "base")
        git(repo, "checkout", "-qb", "topic")
        return repo

    def test_changed_paths_cover_commits_renames_deletions_and_worktree(self) -> None:
        repo = self._repo()
        (repo / "docs").mkdir()
        (repo / "docs" / "guide.md").write_text("g\n", encoding="utf-8")
        git(repo, "mv", "src/a.py", "src/b.py")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "change")
        (repo / "src" / "c.py").write_text("c\n", encoding="utf-8")
        state = repo / ".embraion" / "state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "noise.json").write_text("{}", encoding="utf-8")

        committed, inputs = collect_changed_paths(repo, base_ref="main", head_ref=None, include_worktree=False)
        self.assertEqual(["docs/guide.md", "src/a.py", "src/b.py"], committed)
        self.assertEqual(git(repo, "rev-parse", "main"), inputs["base-sha"])
        self.assertEqual(git(repo, "rev-parse", "HEAD"), inputs["head-sha"])

        with_worktree, _ = collect_changed_paths(repo, base_ref="main", head_ref=None, include_worktree=True)
        self.assertEqual(["docs/guide.md", "src/a.py", "src/b.py", "src/c.py"], with_worktree)

        only_local, _ = collect_changed_paths(repo, base_ref=None, head_ref=None, include_worktree=True)
        self.assertEqual(["src/c.py"], only_local)

    def test_merge_base_ignores_changes_made_on_the_base_branch(self) -> None:
        repo = self._repo()
        (repo / "src" / "topic.py").write_text("t\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "topic")
        git(repo, "checkout", "-q", "main")
        (repo / "src" / "main-only.py").write_text("m\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "main moves")
        git(repo, "checkout", "-q", "topic")
        paths, _ = collect_changed_paths(repo, base_ref="main", head_ref="HEAD", include_worktree=False)
        self.assertEqual(["src/topic.py"], paths)

    def test_unknown_ref_and_missing_base_fail_closed(self) -> None:
        repo = self._repo()
        with self.assertRaises(RuntimeError):
            collect_changed_paths(repo, base_ref="no-such-ref", head_ref=None, include_worktree=False)
        with self.assertRaises(RuntimeError) as caught:
            collect_changed_paths(repo, base_ref=None, head_ref=None, include_worktree=False)
        self.assertIn("--base-ref or --include-worktree", str(caught.exception))

    def test_build_plan_end_to_end_is_reproducible(self) -> None:
        repo = self._repo()
        (repo / "src" / "a.py").write_text("changed\n", encoding="utf-8")
        git(repo, "commit", "-qam", "edit")
        first = build_plan("affected", project=repo, base_ref="main")
        second = build_plan("affected", project=repo, base_ref="main")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(["echo unit"], commands_of(first))
        self.assertEqual(["src/a.py"], first["changed-paths"])


def marker(name: str) -> str:
    """A command that appends its name to a marker file in the project root."""
    code = f"open('ran.txt', 'a').write('{name}\\n')"
    return f'"{sys.executable}" -c "{code}"'


def run_config() -> dict[str, Any]:
    return {
        "profiles": {
            "affected": {
                "commands": [marker("affected")],
                "parameters": {"mode": {"environment": "PLAN_MODE", "default": "x"}},
            },
            "full": {"commands": [marker("lint"), marker("unit"), marker("package")], "timeout-seconds": [30, 40, 50]},
        },
        "areas": {
            "library": {"paths": ["src/**"], "commands": [marker("unit")]},
            "docs": {"paths": ["docs/**"], "commands": [marker("docs")]},
        },
        "impact": [{"id": "schema", "paths": ["src/schema/**"], "full": "data-migration"}],
        "full-reasons": ["data-migration"],
    }


class PlanRunTests(unittest.TestCase):
    def _repo(self, config: dict[str, Any] | None = None) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "commit.gpgsign", "false")
        init_project(repo, name="Consumer")
        write_config(repo, config or run_config())
        (repo / ".gitignore").write_text(".embraion/state/\nran.txt\n", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src" / "a.py").write_text("a\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "base")
        git(repo, "checkout", "-qb", "topic")
        return repo

    def _change(self, repo: Path, relative: str) -> None:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", f"change {relative}")

    def _ran(self, repo: Path) -> list[str]:
        path = repo / "ran.txt"
        return path.read_text(encoding="utf-8").split() if path.is_file() else []

    def test_base_ref_runs_only_the_selected_commands_and_stores_the_plan(self) -> None:
        repo = self._repo()
        self._change(repo, "docs/guide.md")
        plan = resolve_run_plan("affected", project=repo, base_ref="main")
        record = run_validation_profile("affected", project=repo, plan=plan)
        self.assertEqual("passed", record["status"])
        self.assertEqual(["docs"], self._ran(repo))
        self.assertEqual(1, record["command-count"])
        self.assertEqual(plan, record["plan"])
        stored = read_yaml(repo / record["plan-path"])
        self.assertEqual(plan, stored)
        self.assertTrue(record["plan-path"].endswith(f"{record['evidence-id']}/plan.json"))

    def test_run_without_refs_keeps_the_full_profile_commands(self) -> None:
        repo = self._repo()
        self.assertIsNone(resolve_run_plan("affected", project=repo))
        record = run_validation_profile("affected", project=repo, plan=None)
        self.assertEqual(["affected"], self._ran(repo))
        self.assertNotIn("plan", record)

    def test_empty_plan_is_skipped_and_runs_nothing(self) -> None:
        repo = self._repo()
        plan = resolve_run_plan("affected", project=repo, base_ref="HEAD")
        record = run_validation_profile("affected", project=repo, plan=plan)
        self.assertEqual("skipped", record["status"])
        self.assertEqual(0, record["executed-command-count"])
        self.assertEqual([], self._ran(repo))
        self.assertEqual("no changed paths", record["plan"]["skip-reason"])

    def test_unknown_path_runs_the_whole_profile(self) -> None:
        repo = self._repo()
        self._change(repo, "misc/new.bin")
        plan = resolve_run_plan("affected", project=repo, base_ref="main")
        run_validation_profile("affected", project=repo, plan=plan)
        self.assertEqual(["affected"], self._ran(repo))

    def test_escalation_runs_the_full_profile_with_its_timeouts(self) -> None:
        repo = self._repo()
        self._change(repo, "src/schema/model.sql")
        plan = resolve_run_plan("affected", project=repo, base_ref="main")
        record = run_validation_profile("affected", project=repo, plan=plan)
        self.assertEqual(["lint", "unit", "package"], self._ran(repo))
        self.assertEqual([30, 40, 50], [item["timeout-seconds"] for item in record["commands"]])

    def test_plan_file_round_trip_and_fail_closed_checks(self) -> None:
        repo = self._repo()
        self._change(repo, "src/b.py")
        plan = build_plan("affected", project=repo, base_ref="main")
        path = repo / "plan.json"
        write_plan(plan, path)
        self.assertEqual(plan, resolve_run_plan("affected", project=repo, plan_file=str(path)))

        with self.assertRaises(RuntimeError) as caught:
            resolve_run_plan("full", project=repo, plan_file=str(path))
        self.assertIn("is for profile 'affected'", str(caught.exception))

        forged = copy.deepcopy(plan)
        forged["selected-commands"].append({"command": "echo injected", "sources": ["area:library"]})
        write_plan(forged, path)
        with self.assertRaises(RuntimeError) as caught:
            resolve_run_plan("affected", project=repo, plan_file=str(path))
        self.assertIn("not declared", str(caught.exception))

        write_plan(plan, path)
        config = run_config()
        config["areas"]["docs"]["paths"] = ["documents/**"]
        write_config(repo, config)
        with self.assertRaises(RuntimeError) as caught:
            resolve_run_plan("affected", project=repo, plan_file=str(path))
        self.assertIn("stale", str(caught.exception))

    def test_plan_options_are_rejected_when_inputs_conflict(self) -> None:
        repo = self._repo()
        with self.assertRaises(RuntimeError):
            resolve_run_plan("affected", project=repo, plan_file="x.json", base_ref="main")
        with self.assertRaises(RuntimeError):
            resolve_run_plan("affected", project=repo, head_ref="HEAD")

    def test_parameters_are_remapped_to_the_selected_commands(self) -> None:
        config = run_config()
        config["profiles"]["full"]["parameters"] = {
            "only-lint": {"argument": "--lint", "commands": [1]},
            "everywhere": {"environment": "PLAN_ALL", "default": "1"},
        }
        repo = self._repo(config)
        self._change(repo, "src/a.py")
        plan = resolve_run_plan("full", project=repo, base_ref="main", full_justification="data-migration")
        self.assertEqual(3, len(plan["selected-commands"]))
        record = run_validation_profile("full", project=repo, plan=plan, parameters={"only-lint": "1"})
        self.assertEqual("passed", record["status"])
        self.assertEqual(["lint", "unit", "package"], self._ran(repo))

    def test_parameter_for_an_unselected_command_is_ignored_not_an_error(self) -> None:
        config = run_config()
        config["profiles"]["affected"]["parameters"]["target"] = {"environment": "PLAN_TARGET", "commands": [1]}
        repo = self._repo(config)
        self._change(repo, "docs/guide.md")
        plan = resolve_run_plan("affected", project=repo, base_ref="main")
        record = run_validation_profile("affected", project=repo, plan=plan, parameters={"target": "1"})
        self.assertEqual("passed", record["status"])
        self.assertEqual(["docs"], self._ran(repo))
        with self.assertRaises(RuntimeError):
            run_validation_profile("affected", project=repo, plan=plan, parameters={"unknown": "1"})

    def test_projects_without_plan_keys_keep_their_behavior(self) -> None:
        config = {"profiles": {"fast": [marker("fast")], "empty": []}}
        repo = self._repo(config)
        with self.assertRaises(RuntimeError) as caught:
            resolve_run_plan("fast", project=repo, base_ref="main")
        self.assertIn("declares no validation areas", str(caught.exception))
        self.assertIsNone(resolve_run_plan("fast", project=repo))
        record = run_validation_profile("fast", project=repo)
        self.assertEqual(
            {"schema-version", "evidence-id", "evidence-path", "profile", "status", "command-count",
             "executed-command-count", "fail-fast", "timeout-seconds", "run-id", "parameters", "commands",
             "started-utc", "completed-utc"},
            set(record),
        )
        self.assertEqual(["fast"], self._ran(repo))
        self.assertEqual("skipped", run_validation_profile("empty", project=repo)["status"])


if __name__ == "__main__":
    unittest.main()
