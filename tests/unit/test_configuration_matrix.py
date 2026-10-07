"""The configure-by-request matrix must cover the configuration surface that code and schemas define."""

from __future__ import annotations

import copy
import re
import unittest
from pathlib import Path
from typing import Any

import yaml

from embraion.cli import build_parser
from embraion.common import framework_root, read_json, read_yaml
from embraion.evals import evaluate_case
from embraion.project import PROJECT_SKILLS
from embraion.validation import PROJECT_CONFIG_SCHEMAS

ROOT = framework_root()
SKILLS = ROOT / "core/skills"
MATRIX = SKILLS / "project-bootstrap/references/configuration-matrix.yaml"
SKILLS_FIELD = "skills/"
ENTRY_KEYS = {"id", "intents", "skill", "recipe", "fields", "composes", "discover", "ask",
              "owner-decision", "verify", "generates"}
LANGUAGES = {"en", "ru"}


def _resolve(schema: Any, document: dict[str, Any]) -> Any:
    """Follow local references, keeping sibling keywords beside them."""
    for _ in range(16):
        if not isinstance(schema, dict) or not str(schema.get("$ref", "")).startswith("#/"):
            return schema
        target: Any = document
        for part in schema["$ref"][2:].split("/"):
            target = target.get(part) if isinstance(target, dict) else None
        if not isinstance(target, dict):
            return {}
        schema = {**target, **{key: value for key, value in schema.items() if key != "$ref"}}
    return {}


def configuration_surface() -> set[str]:
    """Every project file, top-level key, and declared section key, as `<file>:<dotted path>`.

    Files and keys come from the schema each file is validated with, so a new key or file
    appears here without any edit to this test. A schema that accepts user-named
    top-level entries contributes one `<entries>` field for them.
    """
    surface = {SKILLS_FIELD}
    for name, schema_name in PROJECT_CONFIG_SCHEMAS.items():
        document = read_json(ROOT / "schemas" / f"{schema_name}.schema.json")
        properties = document.get("properties") or {}
        for key, declared in properties.items():
            if declared is False:
                continue  # a key the schema forbids is not configuration
            surface.add(f"{name}:{key}")
            section = _resolve(declared, document)
            if isinstance(section, dict) and isinstance(section.get("properties"), dict):
                surface.update(f"{name}:{key}.{child}" for child, value in section["properties"].items()
                               if value is not False)
        if isinstance(document.get("additionalProperties"), dict):
            surface.add(f"{name}:<entries>")
    return surface


def covered_fields(entries: list[dict[str, Any]]) -> set[str]:
    return {field for entry in entries for field in entry.get("fields", [])}


def uncovered(surface: set[str], declared: set[str]) -> set[str]:
    """Surface fields without a matrix field; `<file>:<key>.*` covers a key and its children."""
    wildcards = {field[:-2] for field in declared if field.endswith(".*")}
    return {field for field in surface
            if field not in declared and not any(field == base or field.startswith(base + ".")
                                                 for base in wildcards)}


def unknown_fields(surface: set[str], declared: set[str]) -> set[str]:
    return {field for field in declared if (field[:-2] if field.endswith(".*") else field) not in surface}


def load_matrix() -> dict[str, Any]:
    return yaml.safe_load(MATRIX.read_text(encoding="utf-8"))


class ConfigurationMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = load_matrix()
        cls.entries = cls.matrix["requests"]

    def test_every_project_file_and_key_has_a_matrix_entry(self) -> None:
        missing = sorted(uncovered(configuration_surface(), covered_fields(self.entries)))
        self.assertEqual([], missing, "add the new file or key to the request entry that configures it, "
                                      "or add an entry, in " + MATRIX.relative_to(ROOT).as_posix())

    def test_matrix_names_only_real_files_and_keys(self) -> None:
        stale = sorted(unknown_fields(configuration_surface(), covered_fields(self.entries)))
        self.assertEqual([], stale)

    def test_the_surface_includes_the_recent_policy_sections(self) -> None:
        surface = configuration_surface()
        for field in ("policy.yaml:check", "policy.yaml:projection", "policy.yaml:merge",
                      "policy.yaml:merge.mode", "policy.yaml:privacy.sources", "policy.yaml:ceilings",
                      "decisions.yaml:triggers", "project.yaml:housekeeping", "knowledge.yaml:slots.decisions",
                      "integrations.yaml:servers", "report.yaml:sections", "claude-native.yaml:assignments",
                      "organization.yaml:filenames", "knowledge-maintenance.yaml:documents", SKILLS_FIELD,
                      "sources.yaml:sources", "validation.yaml:areas", "decisions.yaml:extra-triggers",
                      "project.yaml:worktree.lfs"):
            self.assertIn(field, surface)

    def test_gap_detection_fails_for_a_new_key(self) -> None:
        declared = covered_fields(self.entries)
        self.assertEqual({"policy.yaml:future-key"},
                         uncovered(configuration_surface() | {"policy.yaml:future-key"}, declared))
        self.assertEqual({"policy.yaml:old-key"}, unknown_fields(configuration_surface(), declared | {"policy.yaml:old-key"}))

    def test_project_skills_directory_is_the_one_the_code_reads(self) -> None:
        self.assertEqual(Path(".embraion") / "skills", PROJECT_SKILLS)

    def test_entries_have_a_known_shape(self) -> None:
        self.assertEqual(1, self.matrix["schema-version"])
        identifiers = [entry["id"] for entry in self.entries]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                self.assertRegex(entry["id"], r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
                self.assertLessEqual(set(entry), ENTRY_KEYS)
                self.assertEqual(LANGUAGES, set(entry["intents"]))
                for phrases in entry["intents"].values():
                    self.assertTrue(phrases and all(isinstance(text, str) and text.strip() for text in phrases))
                # An unquoted comma splits one phrase into two list items; the languages stay aligned.
                self.assertEqual(len(entry["intents"]["en"]), len(entry["intents"]["ru"]))
                self.assertTrue(entry.get("fields") or entry.get("composes") or entry.get("generates"))
                self.assertTrue(entry["verify"])
                self.assertIsInstance(entry.get("owner-decision", False), bool)
                for key in ("discover", "ask"):
                    self.assertIsInstance(entry[key], list)

    def test_composed_entries_exist(self) -> None:
        identifiers = {entry["id"] for entry in self.entries}
        for entry in self.entries:
            for other in entry.get("composes", []):
                with self.subTest(entry=entry["id"], composes=other):
                    self.assertIn(other, identifiers)
                    self.assertNotEqual(entry["id"], other)

    def test_verification_commands_are_real_cli_commands(self) -> None:
        subparsers = next(action for action in build_parser()._actions
                          if action.__class__.__name__ == "_SubParsersAction")
        for entry in self.entries:
            for command in entry["verify"]:
                with self.subTest(entry=entry["id"], command=command):
                    words = command.split()
                    self.assertEqual("embraion", words[0])
                    self.assertIn(words[1], subparsers.choices)

    def test_every_entry_has_a_recipe_heading_in_its_skill(self) -> None:
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                skill = SKILLS / entry["skill"]
                self.assertTrue((skill / "SKILL.md").is_file(), entry["skill"])
                recipe = skill / entry["recipe"]
                self.assertTrue(recipe.is_file(), recipe.as_posix())
                headings = re.findall(r"^## (\S+)$", recipe.read_text(encoding="utf-8"), re.MULTILINE)
                self.assertIn(entry["id"], headings)

    def test_every_recipe_heading_is_an_entry_and_every_skill_links_its_references(self) -> None:
        identifiers = {entry["id"] for entry in self.entries}
        owners: dict[Path, str] = {}
        for entry in self.entries:
            owners[(SKILLS / entry["skill"] / entry["recipe"]).resolve()] = entry["skill"]
        for recipe, skill in owners.items():
            with self.subTest(recipe=recipe.name):
                text = recipe.read_text(encoding="utf-8")
                headings = re.findall(r"^## (\S+)$", text, re.MULTILINE)
                self.assertEqual([], sorted(set(headings) - identifiers))
                body = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(f"references/{recipe.name}", body)
        self.assertIn("references/configuration-matrix.yaml",
                      (SKILLS / "project-bootstrap/SKILL.md").read_text(encoding="utf-8"))

    def test_skill_descriptions_trigger_on_plain_requests(self) -> None:
        owners = {entry["skill"] for entry in self.entries}
        for skill in sorted(owners):
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            description = yaml.safe_load(text.split("---", 2)[1])["description"]
            with self.subTest(skill=skill):
                self.assertLessEqual(len(description), 1024)

    def test_both_documentation_pages_list_every_entry(self) -> None:
        for suffix in (".md", ".ru.md"):
            page = (ROOT / "docs/configuration" / f"configure-by-asking{suffix}").read_text(encoding="utf-8")
            for entry in self.entries:
                with self.subTest(page=suffix, entry=entry["id"]):
                    self.assertIn(f"| `{entry['id']}` |", page)

    def test_intent_phrases_never_contain_a_consumer_name(self) -> None:
        text = MATRIX.read_text(encoding="utf-8")
        for forbidden in ("SensorEdge", "Unity-SDK", "MeasureX", "/home/", "/tmp/"):
            self.assertNotIn(forbidden, text)

    def test_behavioral_case_rejects_each_violated_property(self) -> None:
        case = read_yaml(ROOT / "evals/cases/configure-by-request.yaml")
        record = read_json(ROOT / "tests/fixtures/evals/configure-by-request.json")
        self.assertEqual((True, []), evaluate_case(case, record))
        self.assertFalse(case["context"]["live-host-execution"])
        for check in case["checks"]:
            with self.subTest(field=check["field"]):
                broken = copy.deepcopy(record)
                target = broken
                parts = check["field"].split(".")
                for part in parts[:-1]:
                    target = target[part]
                expected = check["value"]
                target[parts[-1]] = not expected if isinstance(expected, bool) else "unsupported"
                self.assertFalse(evaluate_case(case, broken)[0])
        self.assertFalse(evaluate_case(case, {})[0])


if __name__ == "__main__":
    unittest.main()
