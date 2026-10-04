from __future__ import annotations

import json
import hashlib
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

    def test_legacy_bundle_stops_all_host_projections_before_output_writes(self) -> None:
        self._inventory(self.bundle)
        with patch("embraion.project.framework_root", return_value=self.framework):
            for host, relative in DESTINATIONS.items():
                with self.subTest(host=host):
                    output = self.project.parent / f"generated-{host}"
                    components = ["bundle"] if host == "portable" else ["skills"]
                    with self.assertRaisesRegex(RuntimeError, "Unity bundle has been removed"):
                        generate_host(self.framework, host, output, components, project=self.project)
                    self.assertFalse(output.exists())

    def test_legacy_bundle_stops_install_and_plan_before_destination_writes(self) -> None:
        self._inventory(self.bundle)
        with patch("embraion.project.framework_root", return_value=self.framework):
            with self.assertRaisesRegex(RuntimeError, "removed"):
                projection_plan("codex", self.project, components=["skills"])
            with self.assertRaisesRegex(RuntimeError, "removed"):
                install("codex", self.project, components=["skills"])
        self.assertFalse((self.project / DESTINATIONS["codex"]).exists())

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

    def test_prune_removes_only_unchanged_owned_skill(self) -> None:
        self._inventory()
        relative = DESTINATIONS["codex"]
        target = self.project / relative
        target.parent.mkdir(parents=True)
        content = b"# Previously installed Unity skill\n"
        target.write_bytes(content)
        state = self.project / ".embraion/state/projections/codex/root.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"schema-version": 1, "host": "codex",
                                     "destination": str(self.project.resolve()),
                                     "managed-components": ["skills"],
                                     "files": {relative.as_posix(): hashlib.sha256(content).hexdigest()}}), encoding="utf-8")
        with patch("embraion.project.framework_root", return_value=self.framework):
            self.assertIn(relative.as_posix(), projection_plan("codex", self.project, components=["skills"])["obsolete-owned"])
            target.write_text("local edit\n", encoding="utf-8")
            plan = install("codex", self.project, components=["skills"], prune=True)
            self.assertIn(relative.as_posix(), plan["obsolete-modified"])
            self.assertEqual("local edit\n", target.read_text(encoding="utf-8"))
            target.write_bytes(content)
            install("codex", self.project, components=["skills"], prune=True)
            self.assertFalse(target.exists())

    def test_unowned_legacy_skill_is_preserved(self) -> None:
        self._inventory()
        target = self.project / DESTINATIONS["codex"]
        target.parent.mkdir(parents=True)
        target.write_text("foreign skill\n", encoding="utf-8")
        with patch("embraion.project.framework_root", return_value=self.framework):
            install("codex", self.project, components=["skills"], prune=True)
        self.assertEqual("foreign skill\n", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
