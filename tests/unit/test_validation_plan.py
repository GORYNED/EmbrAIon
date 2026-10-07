from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from typing import Any

from embraion.common import read_yaml, write_yaml
from embraion.policy import read_validation_config
from embraion.project import init_project


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


if __name__ == "__main__":
    unittest.main()
