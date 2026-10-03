from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from embraion import __version__
from embraion.project import normalize_project_config, update_project


OLD_PIN = "0.19.2"


class ManagedCapabilityUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.config = self.project / ".embraion"
        self.config.mkdir()
        self.manifest = self.config / "project.yaml"
        self.inventory = self.config / "external-capabilities.yaml"
        self._write(self.manifest, {
            "framework": {"repository": "GORYNED/EmbrAIon", "version": OLD_PIN},
            "project": {"name": "Legacy Consumer"}, "capabilities": {},
        })
        self.bundle = {
            "id": "unity", "kind": "managed-bundle", "source": "builtin:unity",
            "version": OLD_PIN, "license": "MIT", "hosts": ["codex"],
            "env-vars": [], "access": "workspace-write", "data-class": "PRIVATE",
            "selected-skills": ["unity-asset-audit"],
        }
        self.host_managed = {
            "id": "spec-kit", "kind": "host-managed", "source": "host:spec-kit",
            "version": "1.2.3", "license": "MIT", "hosts": ["codex"],
            "host-requirements": {"codex": ["plugins"]}, "env-vars": ["SPEC_KIT_TOKEN"],
            "access": "external-execution", "data-class": "PRIVATE",
        }
        self.digest_managed = {
            "id": "other-plugin", "kind": "host-managed", "source": "host:other-plugin",
            "digest": "sha256:" + "a" * 64, "license": "MIT", "hosts": ["copilot"],
            "env-vars": [], "access": "read-only", "data-class": "PUBLIC",
        }

    @staticmethod
    def _write(path: Path, value: object) -> None:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    def _inventory(self, *entries: dict) -> None:
        self._write(self.inventory, {"schema-version": 1, "capabilities": list(entries)})

    @staticmethod
    def _artifact() -> dict[str, object]:
        return {"schema": 1, "source": "github-release", "release": f"v{__version__}",
                "asset": f"embraion-{__version__}-py3-none-any.whl",
                "digest": "sha256:" + "b" * 64}

    def test_update_aligns_builtin_and_preserves_host_managed_metadata(self) -> None:
        self._inventory(self.bundle, self.host_managed, self.digest_managed)
        with patch("embraion.project.resolve_release_artifact", return_value=self._artifact()):
            previous, target = update_project(self.project)
        self.assertEqual((OLD_PIN, __version__), (previous, target))
        upgraded = yaml.safe_load(self.inventory.read_text(encoding="utf-8"))
        self.assertEqual(__version__, upgraded["capabilities"][0]["version"])
        self.assertEqual(self.host_managed, upgraded["capabilities"][1])
        self.assertEqual(self.digest_managed, upgraded["capabilities"][2])
        self.assertEqual(__version__, yaml.safe_load(self.manifest.read_text(encoding="utf-8"))["framework"]["version"])

    def test_target_version_already_prepared_is_accepted(self) -> None:
        self._inventory({**self.bundle, "version": __version__})
        changed = normalize_project_config(self.project, version=__version__)
        self.assertNotIn(self.inventory, changed)
        self.assertEqual(__version__, yaml.safe_load(self.manifest.read_text(encoding="utf-8"))["framework"]["version"])

    def test_unsupported_selected_skill_rejects_entire_update_before_writes(self) -> None:
        self._inventory({**self.bundle, "selected-skills": ["unity-unknown-skill"]})
        before = (self.manifest.read_bytes(), self.inventory.read_bytes())
        with patch("embraion.project.resolve_release_artifact", return_value=self._artifact()):
            with self.assertRaisesRegex(RuntimeError, "absent from the manifest"):
                update_project(self.project)
        self.assertEqual(before, (self.manifest.read_bytes(), self.inventory.read_bytes()))
        self.assertFalse((self.config / "routing.yaml").exists())

    def test_unrelated_builtin_version_or_unknown_source_rejects_before_writes(self) -> None:
        for entry in ({**self.bundle, "version": "0.18.0"},
                      {**self.bundle, "source": "builtin:unknown"}):
            with self.subTest(entry=entry):
                self._inventory(entry)
                before = (self.manifest.read_bytes(), self.inventory.read_bytes())
                with self.assertRaises(RuntimeError):
                    normalize_project_config(self.project, version=__version__)
                self.assertEqual(before, (self.manifest.read_bytes(), self.inventory.read_bytes()))
                self.assertFalse((self.config / "routing.yaml").exists())

    def test_invalid_inventory_is_rejected_without_echoing_secret(self) -> None:
        self._inventory({**self.bundle, "token": "sensitive-value"})
        with self.assertRaises(RuntimeError) as failure:
            normalize_project_config(self.project, version=__version__)
        self.assertNotIn("sensitive-value", str(failure.exception))
        self.assertEqual(OLD_PIN, yaml.safe_load(self.manifest.read_text(encoding="utf-8"))["framework"]["version"])

    def test_absent_inventory_is_not_created(self) -> None:
        normalize_project_config(self.project, version=__version__)
        self.assertFalse(self.inventory.exists())


if __name__ == "__main__":
    unittest.main()
