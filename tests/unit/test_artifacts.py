from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.artifacts import (
    artifact_download_url,
    download_locked_artifact,
    read_project_artifact_lock,
    resolve_release_artifact,
    verify_project_artifact,
)


class ArtifactLockTests(unittest.TestCase):
    def _manifest(
        self,
        root: Path,
        *,
        version: str = "1.2.3",
        release: str = "v1.2.3",
        asset: str = "embraion-1.2.3-py3-none-any.whl",
        digest: str | None = None,
    ) -> Path:
        digest = digest or ("sha256:" + ("a" * 64))
        manifest = root / ".embraion" / "project.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            "framework:\n"
            "  repository: GORYNED/EmbrAIon\n"
            f"  version: {version}\n"
            "  artifact:\n"
            "    schema: 1\n"
            "    source: github-release\n"
            f"    release: {release}\n"
            f"    asset: {asset}\n"
            f"    digest: {digest}\n"
            "project:\n"
            "  name: Demo\n",
            encoding="utf-8",
        )
        return manifest

    def test_reads_valid_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = read_project_artifact_lock(self._manifest(Path(temporary)))
        self.assertEqual("1.2.3", lock.version)
        self.assertEqual("v1.2.3", lock.release)
        self.assertEqual("embraion-1.2.3-py3-none-any.whl", lock.asset)

    def test_missing_lock_is_allowed_only_for_legacy_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "framework:\n"
                "  repository: GORYNED/EmbrAIon\n"
                "  version: 1.2.3\n"
                "project:\n"
                "  name: Demo\n",
                encoding="utf-8",
            )
            self.assertIsNone(read_project_artifact_lock(manifest, required=False))
            with self.assertRaisesRegex(RuntimeError, "Missing framework.artifact"):
                read_project_artifact_lock(manifest, required=True)

    def test_version_release_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(Path(temporary), release="v1.2.4")
            with self.assertRaisesRegex(RuntimeError, "version/lock mismatch"):
                read_project_artifact_lock(manifest)

    def test_version_asset_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(
                Path(temporary),
                asset="embraion-1.2.4-py3-none-any.whl",
            )
            with self.assertRaisesRegex(RuntimeError, "version/lock mismatch"):
                read_project_artifact_lock(manifest)

    def test_malformed_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(Path(temporary), digest="sha256:not-a-digest")
            with self.assertRaisesRegex(RuntimeError, "Malformed framework.artifact digest"):
                read_project_artifact_lock(manifest)

    def test_resolve_release_uses_exact_asset_and_github_digest(self) -> None:
        version = "1.2.3"
        asset = f"embraion-{version}-py3-none-any.whl"
        digest = "sha256:" + ("b" * 64)
        payload = {
            "tag_name": f"v{version}",
            "assets": [
                {
                    "name": asset,
                    "digest": digest,
                    "browser_download_url": (
                        f"https://github.com/GORYNED/EmbrAIon/releases/download/"
                        f"v{version}/{asset}"
                    ),
                }
            ],
        }

        with patch(
            "embraion.artifacts.urlopen",
            return_value=io.BytesIO(json.dumps(payload).encode("utf-8")),
        ):
            lock = resolve_release_artifact(version)

        self.assertEqual(digest, lock["digest"])
        self.assertEqual(asset, lock["asset"])
        self.assertEqual(f"v{version}", lock["release"])

    def test_resolve_release_missing_asset_fails_closed(self) -> None:
        payload = {"tag_name": "v1.2.3", "assets": []}
        with patch(
            "embraion.artifacts.urlopen",
            return_value=io.BytesIO(json.dumps(payload).encode("utf-8")),
        ):
            with self.assertRaisesRegex(RuntimeError, "exactly one artifact"):
                resolve_release_artifact("1.2.3")

    def test_download_verifies_sha256_before_publish(self) -> None:
        payload = b"verified-wheel-bytes"
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = read_project_artifact_lock(
                self._manifest(root, digest=digest)
            )
            destination = root / lock.asset
            with patch(
                "embraion.artifacts.urlopen",
                return_value=io.BytesIO(payload),
            ):
                report = download_locked_artifact(lock, destination)

            self.assertEqual(payload, destination.read_bytes())
            self.assertEqual(digest, report["digest"])
            self.assertEqual(
                f"https://github.com/GORYNED/EmbrAIon/releases/download/"
                f"{lock.release}/{lock.asset}",
                artifact_download_url(lock),
            )

    def test_verify_project_artifact_uses_locked_digest(self) -> None:
        payload = b"verified-release-wheel"
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._manifest(root, digest=digest)
            with patch(
                "embraion.artifacts.urlopen",
                return_value=io.BytesIO(payload),
            ):
                report = verify_project_artifact(manifest)

        self.assertEqual("1.2.3", report["version"])
        self.assertEqual("v1.2.3", report["release"])
        self.assertEqual(digest, report["digest"])
        self.assertNotIn("path", report)

    def test_download_digest_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = read_project_artifact_lock(self._manifest(root))
            destination = root / lock.asset
            with patch(
                "embraion.artifacts.urlopen",
                return_value=io.BytesIO(b"wrong-wheel"),
            ):
                with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
                    download_locked_artifact(lock, destination)

            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_name(destination.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
