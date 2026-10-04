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
                    projected_bytes = projected.read_bytes()
                    self.assertEqual(
                        source.read_text(encoding="utf-8").encode("utf-8"),
                        projected_bytes,
                    )
                    self.assertNotIn(b"\r\n", projected_bytes)

            expected = {item["id"] for item in entries if item["type"] == "skill"}
            actual = {path.parent.name for path in (generated / "codex/.agents/skills").glob("*/SKILL.md")}
            self.assertEqual(expected, actual)

    def test_guides_have_both_languages_and_link_to_procedures(self) -> None:
        for suffix in (".md", ".ru.md"):
            with self.subTest(language=suffix):
                guide = ROOT / "docs/guides" / f"engineering-skills{suffix}"
                content = guide.read_text(encoding="utf-8")
                self.assertTrue(all(f"`{skill_id}`" in content for skill_id in CORE_IDS))


if __name__ == "__main__":
    unittest.main()
