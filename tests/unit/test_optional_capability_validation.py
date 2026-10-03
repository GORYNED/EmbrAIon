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
            "project-schema", "skill-eval-schema", "unity-manifest", "unity-skill-entry",
            "unity-skill-frontmatter", "unity-skill-collision",
        }]

    def _unity(self) -> Path:
        self._yaml("extensions/unity/manifest.yaml", {
            "schema-version": 1, "id": "unity", "version": "0.20.0", "license": "MIT",
            "skills": {"unity-asset-audit": "skills/unity-asset-audit"},
        })
        entry = self.root / "extensions/unity/skills/unity-asset-audit/SKILL.md"
        entry.parent.mkdir(parents=True)
        entry.write_text("---\nname: unity-asset-audit\ndescription: Audit assets.\n---\n\n# Audit\n", encoding="utf-8")
        return entry

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

    def test_unity_manifest_checks_identity_source_and_frontmatter(self) -> None:
        entry = self._unity()
        self.assertFalse(any(issue["code"].startswith("unity-") for issue in self._relevant()))
        manifest = self.root / "extensions/unity/manifest.yaml"
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        data["version"] = "0.19.2"
        data["license"] = "Proprietary"
        self._yaml("extensions/unity/manifest.yaml", data)
        self.assertIn("unity-manifest", {issue["code"] for issue in self._relevant()})
        data["version"] = "0.20.0"
        data["license"] = "MIT"
        data["skills"]["unity-asset-audit"] = "../../outside"
        self._yaml("extensions/unity/manifest.yaml", data)
        self.assertIn("unity-manifest", {issue["code"] for issue in self._relevant()})
        data["skills"]["unity-asset-audit"] = "skills/unity-asset-audit"
        self._yaml("extensions/unity/manifest.yaml", data)
        entry.write_text("# No frontmatter\n", encoding="utf-8")
        self.assertIn("unity-skill-frontmatter", {issue["code"] for issue in self._relevant()})
        entry.unlink()
        self.assertTrue(any(issue["code"] == "unity-skill-entry" and issue["path"].endswith("SKILL.md")
                            for issue in self._relevant()))

    def test_unity_missing_manifest_symlinks_and_core_collision(self) -> None:
        entry = self._unity()
        (self.root / "core/skills/unity-asset-audit").mkdir(parents=True)
        self.assertIn("unity-skill-collision", {issue["code"] for issue in self._relevant()})
        (entry.parent / "unsafe").symlink_to(self.root / "core/catalog.yaml")
        self.assertTrue(any(issue["code"] == "unity-skill-entry" and "symbolic" in issue["message"]
                            for issue in self._relevant()))
        (self.root / "extensions/unity/manifest.yaml").unlink()
        self.assertTrue(any(issue["code"] == "unity-manifest" and "Missing" in issue["message"]
                            for issue in self._relevant()))

    def test_only_direct_skill_eval_json_is_treated_as_suite(self) -> None:
        self._json("evals/skills/invalid.json", {"schema-version": 1, "skills": []})
        self._json("evals/skills/fixtures/data.json", {"fixture": "ordinary JSON"})
        paths = {issue["path"] for issue in self._relevant() if issue["code"] == "skill-eval-schema"}
        self.assertEqual({"evals/skills/invalid.json"}, paths)


if __name__ == "__main__":
    unittest.main()
