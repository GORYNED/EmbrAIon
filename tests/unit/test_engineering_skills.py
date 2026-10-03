from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from embraion.project import sync


ROOT = Path(__file__).resolve().parents[2]
CORE_IDS = (
    "skill-authoring",
    "compatibility-migration",
    "test-design",
    "performance-investigation",
    "dependency-upgrade",
)
UNITY_IDS = (
    "unity-serialization-migration",
    "unity-lifecycle-review",
    "unity-player-validation",
    "unity-asset-audit",
)


def _frontmatter(path: Path) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    start, metadata, body = source.split("---", 2)
    if start or not body.strip():
        raise AssertionError(f"Invalid skill entry point: {path}")
    result = yaml.safe_load(metadata)
    if not isinstance(result, dict):
        raise AssertionError(f"Missing skill metadata: {path}")
    return result


class EngineeringSkillTests(unittest.TestCase):
    def test_core_skill_entries_are_catalogued_once_and_projected(self) -> None:
        catalog = yaml.safe_load((ROOT / "core/catalog.yaml").read_text(encoding="utf-8"))
        entries = catalog["capabilities"]
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary)
            sync("codex", generated)
            for skill_id in CORE_IDS:
                with self.subTest(skill=skill_id):
                    source = ROOT / "core/skills" / skill_id / "SKILL.md"
                    metadata = _frontmatter(source)
                    self.assertEqual(skill_id, metadata["name"])
                    self.assertTrue(metadata["description"])
                    matches = [item for item in entries if item["id"] == skill_id]
                    self.assertEqual(1, len(matches))
                    self.assertEqual("skill", matches[0]["type"])
                    self.assertEqual("conditional", matches[0]["load"])
                    self.assertEqual(f"skills/{skill_id}", matches[0]["path"])
                    projected = generated / "codex/.agents/skills" / skill_id / "SKILL.md"
                    self.assertEqual(source.read_bytes(), projected.read_bytes())

            for skill_id in UNITY_IDS:
                self.assertFalse((generated / "codex/.agents/skills" / skill_id).exists())

    def test_unity_manifest_has_one_valid_entry_per_optional_skill(self) -> None:
        extension = ROOT / "extensions/unity"
        manifest = yaml.safe_load((extension / "manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["schema-version"])
        self.assertEqual("unity", manifest["id"])
        self.assertEqual("MIT", manifest["license"])
        self.assertEqual(
            yaml.safe_load((ROOT / "framework.yaml").read_text(encoding="utf-8"))["version"],
            manifest["version"],
        )
        self.assertEqual(set(UNITY_IDS), set(manifest["skills"]))
        for skill_id, relative in manifest["skills"].items():
            with self.subTest(skill=skill_id):
                self.assertEqual(f"skills/{skill_id}", relative)
                source = extension / relative / "SKILL.md"
                self.assertEqual(skill_id, _frontmatter(source)["name"])
                self.assertTrue(source.is_file())

    def test_guides_have_both_languages_and_link_to_procedures(self) -> None:
        for name in ("engineering-skills", "unity-capabilities"):
            for suffix in (".md", ".ru.md"):
                with self.subTest(guide=name, language=suffix):
                    guide = ROOT / "docs/guides" / f"{name}{suffix}"
                    content = guide.read_text(encoding="utf-8")
                    ids = CORE_IDS if name == "engineering-skills" else UNITY_IDS
                    self.assertTrue(all(f"`{skill_id}`" in content for skill_id in ids))


if __name__ == "__main__":
    unittest.main()
