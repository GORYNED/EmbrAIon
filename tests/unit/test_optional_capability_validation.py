from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from embraion.validation import collect_issues


SOURCE = Path(__file__).resolve().parents[2]


class OptionalCapabilityValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(SOURCE / "schemas", self.root / "schemas")
        self._yaml("framework.yaml", {"version": "0.20.0"})
        self._yaml("core/catalog.yaml", {"capabilities": []})
        self._yaml("templates/project-overlay/.embraion/project.yaml", {
            "framework": {"repository": "GORYNED/EmbrAIon", "version": "0.20.0"},
            "project": {"name": "Fixture"},
        })

    def _yaml(self, relative: str, data: object) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data), encoding="utf-8")

    def _json(self, relative: str, data: object) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _relevant(self) -> list[dict[str, str]]:
        return [issue for issue in collect_issues(self.root) if issue["code"] in {
            "project-schema", "skill-eval-schema",
        }]

    def test_optional_project_files_are_validated_when_present(self) -> None:
        base = "templates/project-overlay/.embraion/"
        self._yaml(base + "external-capabilities.yaml", {"schema-version": 1, "capabilities": [{"id": "bad"}]})
        self._yaml(base + "organization.yaml", {"unknown": True})
        self._yaml(base + "knowledge-maintenance.yaml", {"documents": []})
        paths = {issue["path"] for issue in self._relevant() if issue["code"] == "project-schema"}
        self.assertTrue({base + name for name in (
            "external-capabilities.yaml", "organization.yaml", "knowledge-maintenance.yaml"
        )} <= paths)
        self._yaml(base + "external-capabilities.yaml", {"schema-version": 1, "capabilities": []})
        self._yaml(base + "organization.yaml", {})
        self._yaml(base + "knowledge-maintenance.yaml", {
            "documents": [{"id": "guide", "path": "README.md", "sources": ["core/catalog.yaml"]}]
        })
        paths = {issue["path"] for issue in self._relevant() if issue["code"] == "project-schema"}
        self.assertFalse(any(name in paths for name in (
            base + "external-capabilities.yaml", base + "organization.yaml", base + "knowledge-maintenance.yaml"
        )))

    def test_example_optional_file_uses_same_schema(self) -> None:
        self._yaml("examples/sample/.embraion/project.yaml", {
            "framework": {"repository": "GORYNED/EmbrAIon", "version": "0.20.0"},
            "project": {"name": "Sample"},
        })
        self._yaml("examples/sample/.embraion/organization.yaml", {"unknown": 1})
        self.assertTrue(any(issue["path"] == "examples/sample/.embraion/organization.yaml"
                            and issue["code"] == "project-schema" for issue in self._relevant()))

    def test_external_schema_error_does_not_echo_metadata_values(self) -> None:
        base = "templates/project-overlay/.embraion/"
        self._yaml(base + "external-capabilities.yaml", {
            "schema-version": 1, "capabilities": [{"id": "secret", "token": "sensitive-value"}],
        })
        issues = [issue for issue in self._relevant() if issue["path"] == base + "external-capabilities.yaml"]
        self.assertTrue(issues)
        self.assertNotIn("sensitive-value", json.dumps(issues))

    def test_only_direct_skill_eval_json_is_treated_as_suite(self) -> None:
        self._json("evals/skills/invalid.json", {"schema-version": 1, "skills": []})
        self._json("evals/skills/fixtures/data.json", {"fixture": "ordinary JSON"})
        paths = {issue["path"] for issue in self._relevant() if issue["code"] == "skill-eval-schema"}
        self.assertEqual({"evals/skills/invalid.json"}, paths)


if __name__ == "__main__":
    unittest.main()
