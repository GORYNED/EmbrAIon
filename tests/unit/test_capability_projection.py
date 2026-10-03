from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from embraion import __version__
from embraion.project import generate_host, init_project, install, projection_plan


SOURCE = Path(__file__).resolve().parents[2]
DESTINATIONS = {
    "codex": Path(".agents/skills/unity-asset-audit/SKILL.md"),
    "copilot": Path(".github/skills/unity-asset-audit/SKILL.md"),
    "claude-code": Path(".claude/skills/unity-asset-audit/SKILL.md"),
    "portable": Path("embraion/skills/unity-asset-audit/SKILL.md"),
}


class CapabilityProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.framework = base / "framework"
        self.framework.mkdir()
        for directory in ("core", "adapters", "schemas"):
            shutil.copytree(SOURCE / directory, self.framework / directory)
        (self.framework / "framework.yaml").write_text(
            f"version: {__version__}\n", encoding="utf-8"
        )
        self.project = base / "consumer"
        init_project(self.project, name="Consumer")
        self.extension = self.framework / "extensions/unity"
        skill = self.extension / "skills/unity-asset-audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_bytes(b"# Asset audit\r\nUse Unity.\r\n")
        self._yaml(self.extension / "manifest.yaml", {
            "schema-version": 1, "id": "unity", "version": __version__, "license": "MIT",
            "skills": {"unity-asset-audit": "skills/unity-asset-audit"},
        })
        self.bundle = {
            "id": "unity", "kind": "managed-bundle", "source": "builtin:unity",
            "version": __version__, "license": "MIT", "hosts": list(DESTINATIONS),
            "host-requirements": {}, "env-vars": [], "access": "workspace-write",
            "data-class": "PRIVATE", "selected-skills": ["unity-asset-audit"],
        }

    @staticmethod
    def _yaml(path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data), encoding="utf-8")

    def _inventory(self, *entries: dict) -> None:
        self._yaml(self.project / ".embraion/external-capabilities.yaml", {
            "schema-version": 1, "capabilities": list(entries),
        })

    def test_absent_inventory_leaves_core_only(self) -> None:
        with patch("embraion.project.framework_root", return_value=self.framework):
            for host, relative in DESTINATIONS.items():
                with self.subTest(host=host):
                    output = self.project.parent / f"generated-{host}"
                    components = ["bundle"] if host == "portable" else ["skills"]
                    generate_host(self.framework, host, output, components, project=self.project)
                    self.assertFalse((output / relative).exists())
                    core = relative.parent.parent / "code-organization/SKILL.md"
                    self.assertTrue((output / core).is_file())

    def test_selected_skill_projects_to_all_hosts_with_lf_entry(self) -> None:
        self._inventory(self.bundle)
        with patch("embraion.project.framework_root", return_value=self.framework):
            for host, relative in DESTINATIONS.items():
                with self.subTest(host=host):
                    output = self.project.parent / f"generated-{host}"
                    components = ["bundle"] if host == "portable" else ["skills"]
                    generate_host(self.framework, host, output, components, project=self.project)
                    self.assertEqual(b"# Asset audit\nUse Unity.\n", (output / relative).read_bytes())

    def test_invalid_pin_and_manifest_stop_projection(self) -> None:
        self._inventory(self.bundle)
        project_manifest = self.project / ".embraion/project.yaml"
        data = yaml.safe_load(project_manifest.read_text(encoding="utf-8"))
        data["framework"]["version"] = "0.0.1"
        self._yaml(project_manifest, data)
        with patch("embraion.project.framework_root", return_value=self.framework):
            with self.assertRaisesRegex(RuntimeError, "pin"):
                generate_host(self.framework, "codex", self.project.parent / "invalid-pin", ["skills"], project=self.project)
        data["framework"]["version"] = __version__
        self._yaml(project_manifest, data)
        manifest = self.extension / "manifest.yaml"
        details = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        details["skills"]["unity-asset-audit"] = "../../escape"
        self._yaml(manifest, details)
        with patch("embraion.project.framework_root", return_value=self.framework):
            with self.assertRaisesRegex(RuntimeError, "manifest"):
                generate_host(self.framework, "codex", self.project.parent / "invalid-manifest", ["skills"], project=self.project)

    def test_host_managed_capability_is_diagnostic_only(self) -> None:
        self._inventory({
            "id": "spec-kit", "kind": "host-managed", "source": "host:spec-kit",
            "version": "1.0.0", "license": "MIT", "hosts": ["codex", "portable"],
            "env-vars": [], "access": "read-only", "data-class": "PUBLIC",
        })
        with patch("embraion.project.framework_root", return_value=self.framework):
            for host in ("codex", "portable"):
                output = self.project.parent / f"generated-{host}"
                components = ["bundle"] if host == "portable" else ["skills"]
                generate_host(self.framework, host, output, components, project=self.project)
                self.assertFalse((output / DESTINATIONS[host]).exists())
                self.assertFalse((output / DESTINATIONS[host].parent.parent / "spec-kit").exists())

    def test_selected_skill_cannot_replace_core_skill(self) -> None:
        skill = self.extension / "skills/code-organization"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Different skill\n", encoding="utf-8")
        details = yaml.safe_load((self.extension / "manifest.yaml").read_text(encoding="utf-8"))
        details["skills"]["code-organization"] = "skills/code-organization"
        self._yaml(self.extension / "manifest.yaml", details)
        self._inventory({**self.bundle, "selected-skills": ["code-organization"]})
        with patch("embraion.project.framework_root", return_value=self.framework):
            with self.assertRaisesRegex(RuntimeError, "collides"):
                generate_host(self.framework, "codex", self.project.parent / "collision", ["skills"], project=self.project)

    def test_prune_removes_only_unchanged_owned_skill(self) -> None:
        self._inventory(self.bundle)
        relative = DESTINATIONS["codex"]
        target = self.project / relative
        with patch("embraion.project.framework_root", return_value=self.framework):
            install("codex", self.project, components=["skills"])
            self.assertTrue(target.is_file())
            state = self.project / ".embraion/state/projections/codex/root.json"
            self.assertIn(relative.as_posix(), json.loads(state.read_text(encoding="utf-8"))["files"])
            self._inventory()
            self.assertIn(relative.as_posix(), projection_plan("codex", self.project, components=["skills"])["obsolete-owned"])
            target.write_text("local edit\n", encoding="utf-8")
            plan = install("codex", self.project, components=["skills"], prune=True)
            self.assertIn(relative.as_posix(), plan["obsolete-modified"])
            self.assertEqual("local edit\n", target.read_text(encoding="utf-8"))
            target.write_bytes(b"# Asset audit\nUse Unity.\n")
            install("codex", self.project, components=["skills"], prune=True)
            self.assertFalse(target.exists())

    def test_unowned_skill_collision_is_not_overwritten(self) -> None:
        self._inventory(self.bundle)
        target = self.project / DESTINATIONS["codex"]
        target.parent.mkdir(parents=True)
        target.write_text("foreign skill\n", encoding="utf-8")
        with patch("embraion.project.framework_root", return_value=self.framework):
            plan = projection_plan("codex", self.project, components=["skills"])
            self.assertIn(DESTINATIONS["codex"].as_posix(), plan["conflict"])
            with self.assertRaisesRegex(RuntimeError, "conflicts"):
                install("codex", self.project, components=["skills"])
        self.assertEqual("foreign skill\n", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
