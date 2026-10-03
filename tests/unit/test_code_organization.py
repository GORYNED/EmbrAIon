from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root, read_yaml
from embraion.project import generate_host, init_project, install, projection_is_verified, projection_plan


SKILL_PATHS = {
    "codex": ".agents/skills/code-organization/SKILL.md",
    "copilot": ".github/skills/code-organization/SKILL.md",
    "claude-code": ".claude/skills/code-organization/SKILL.md",
    "portable": "embraion/skills/code-organization/SKILL.md",
}


class CodeOrganizationContractTests(unittest.TestCase):
    def test_catalog_skill_installs_and_is_owned_on_every_host(self) -> None:
        root = framework_root()
        canonical = (root / "core/skills/code-organization/SKILL.md").read_text(encoding="utf-8")
        catalog = read_yaml(root / "core/catalog.yaml")
        entries = [item for item in catalog["capabilities"] if item["id"] == "code-organization"]
        self.assertEqual(1, len(entries))
        self.assertEqual("skill", entries[0]["type"])
        self.assertEqual("skills/code-organization", entries[0]["path"])

        with tempfile.TemporaryDirectory() as temporary:
            for host, relative in SKILL_PATHS.items():
                with self.subTest(host=host):
                    project = Path(temporary) / host
                    init_project(project)
                    install(host, project)
                    installed = project / relative
                    self.assertEqual(canonical, installed.read_text(encoding="utf-8"))
                    self.assertTrue(projection_is_verified(projection_plan(host, project)))

                    bundle = Path(temporary) / f"bundle-{host}"
                    generate_host(root, host, bundle)
                    self.assertEqual(canonical, (bundle / relative).read_text(encoding="utf-8"))

                    installed.write_text(canonical + "\nlocal change\n", encoding="utf-8")
                    self.assertFalse(projection_is_verified(projection_plan(host, project)))

    def test_normal_entrypoints_deliver_placement_trigger(self) -> None:
        root = framework_root()
        for host, relative in SKILL_PATHS.items():
            with self.subTest(host=host), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                init_project(project)
                install(host, project)
                skills_root = (project / relative).parent.parent
                implementation = (skills_root / "implementation/SKILL.md").read_text(encoding="utf-8")
                orchestration = (skills_root / "orchestration/SKILL.md").read_text(encoding="utf-8")
                review = (skills_root / "review/SKILL.md").read_text(encoding="utf-8")
                for text in (implementation, orchestration, review):
                    self.assertIn("code-organization", text)

        lead = read_yaml(root / "core/agents/lead.yaml")
        worker = read_yaml(root / "core/agents/worker.yaml")
        reviewer = read_yaml(root / "core/agents/reviewer.yaml")
        self.assertTrue(any("code-organization" in item for item in lead["responsibilities"]))
        self.assertTrue(any("code-organization" in item for item in worker["responsibilities"]))
        self.assertTrue(any("namespace placement" in item for item in reviewer["responsibilities"]))


if __name__ == "__main__":
    unittest.main()
