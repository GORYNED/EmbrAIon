from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from embraion import __version__
from embraion.project import update_project


def _artifact(version: str, digest_char: str = "a") -> dict[str, object]:
    return {
        "schema": 1,
        "source": "github-release",
        "release": f"v{version}",
        "asset": f"embraion-{version}-py3-none-any.whl",
        "digest": "sha256:" + (digest_char * 64),
    }


class ProjectUpdateArtifactLockTests(unittest.TestCase):
    def _legacy_manifest(self, root: Path, version: str = "0.8.1") -> Path:
        manifest = root / ".embraion" / "project.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            "framework:\n"
            "  repository: GORYNED/EmbrAIon\n"
            f"  version: {version}\n"
            "project:\n"
            "  name: LegacyOnlyManifest\n"
            "capabilities: {}\n",
            encoding="utf-8",
        )
        return manifest

    def test_version_only_project_upgrades_without_manual_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._legacy_manifest(root)
            expected_artifact = _artifact(__version__)

            with mock.patch(
                "embraion.project.resolve_release_artifact",
                return_value=expected_artifact,
            ) as resolve:
                previous, current = update_project(root)

            self.assertEqual("0.8.1", previous)
            self.assertEqual(__version__, current)
            resolve.assert_called_once_with(__version__)

            upgraded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            self.assertEqual(__version__, upgraded["framework"]["version"])
            self.assertEqual(expected_artifact, upgraded["framework"]["artifact"])

            for name in (
                "routing.yaml",
                "deployments.yaml",
                "policy.yaml",
                "knowledge.yaml",
                "validation.yaml",
                "agents.yaml",
            ):
                self.assertTrue((root / ".embraion" / name).is_file(), name)

    def test_release_resolution_failure_does_not_change_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._legacy_manifest(root)
            before = manifest.read_bytes()

            with mock.patch(
                "embraion.project.resolve_release_artifact",
                side_effect=RuntimeError("release asset missing"),
            ):
                with self.assertRaisesRegex(RuntimeError, "release asset missing"):
                    update_project(root)

            self.assertEqual(before, manifest.read_bytes())
            self.assertFalse((root / ".embraion" / "routing.yaml").exists())
            self.assertFalse((root / ".embraion" / "deployments.yaml").exists())

    def test_lock_changes_atomically_with_framework_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._legacy_manifest(root, version=__version__)
            stale_artifact = _artifact(__version__, digest_char="b")
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            data["framework"]["artifact"] = stale_artifact
            manifest.write_text(
                yaml.safe_dump(data, sort_keys=False),
                encoding="utf-8",
            )
            expected_artifact = _artifact(__version__, digest_char="c")

            with mock.patch(
                "embraion.project.resolve_release_artifact",
                return_value=expected_artifact,
            ):
                update_project(root)

            upgraded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            self.assertEqual(__version__, upgraded["framework"]["version"])
            self.assertEqual(expected_artifact, upgraded["framework"]["artifact"])
            self.assertNotEqual(
                stale_artifact["digest"],
                upgraded["framework"]["artifact"]["digest"],
            )


if __name__ == "__main__":
    unittest.main()
