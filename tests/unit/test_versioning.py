from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.artifacts import FrameworkArtifactLock
from embraion.versioning import (
    CachedRuntime,
    find_project_manifest,
    install_project_runtime,
    package_version_for_pin,
    read_project_pin,
    resolve_project_runtime,
)


class VersioningTests(unittest.TestCase):
    def _manifest(self, root: Path, version: str = "0.1.0") -> Path:
        manifest = root / ".embraion" / "project.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            "framework:\n"
            "  repository: GORYNED/EmbrAIon\n"
            f"  version: {version}\n"
            "project:\n"
            "  name: Demo\n",
            encoding="utf-8",
        )
        return manifest

    def test_finds_nearest_project_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._manifest(root)
            nested = root / "src" / "feature"
            nested.mkdir(parents=True)

            self.assertEqual(manifest.resolve(), find_project_manifest(nested))

    def test_legacy_release_pin_maps_to_published_package(self) -> None:
        self.assertEqual("0.1.0", package_version_for_pin("0.1.0-dev"))

    def test_reads_canonical_project_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(Path(temporary), "1.2.3")
            self.assertEqual("1.2.3", read_project_pin(manifest))

    def test_framework_install_passes_exact_project_lock_to_cache_installer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                "framework:\n"
                "  repository: GORYNED/EmbrAIon\n"
                "  version: 1.2.3\n"
                "  artifact:\n"
                "    schema: 1\n"
                "    source: github-release\n"
                "    release: v1.2.3\n"
                "    asset: embraion-1.2.3-py3-none-any.whl\n"
                f"    digest: sha256:{'a' * 64}\n"
                "project:\n"
                "  name: Demo\n",
                encoding="utf-8",
            )
            cached = CachedRuntime(
                python=Path(sys.executable),
                framework_root=root / "framework",
            )

            with patch(
                "embraion.versioning.ensure_cached_runtime",
                return_value=cached,
            ) as ensure:
                result = install_project_runtime(manifest)

            self.assertEqual(cached, result)
            args, kwargs = ensure.call_args
            self.assertEqual(("1.2.3",), args)
            lock = kwargs["artifact_lock"]
            self.assertIsInstance(lock, FrameworkArtifactLock)
            self.assertEqual("v1.2.3", lock.release)
            self.assertEqual("sha256:" + ("a" * 64), lock.digest)

    def test_same_version_does_not_delegate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._manifest(root, "0.2.0.dev0")
            with patch("embraion.versioning.ensure_cached_runtime") as ensure:
                result = resolve_project_runtime(
                    ["validate"],
                    "0.2.0.dev0",
                    start=root,
                )

            self.assertIsNone(result)
            ensure.assert_not_called()

    def test_same_version_lock_delegates_to_digest_bound_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                "framework:\n"
                "  repository: GORYNED/EmbrAIon\n"
                "  version: 1.2.3\n"
                "  artifact:\n"
                "    schema: 1\n"
                "    source: github-release\n"
                "    release: v1.2.3\n"
                "    asset: embraion-1.2.3-py3-none-any.whl\n"
                f"    digest: sha256:{'a' * 64}\n"
                "project:\n"
                "  name: Locked\n",
                encoding="utf-8",
            )
            framework = root / "cached-framework"
            framework.mkdir()
            cached = CachedRuntime(
                python=Path(sys.executable),
                framework_root=framework,
            )
            completed = subprocess.CompletedProcess(args=[], returncode=0)

            with patch(
                "embraion.versioning.ensure_cached_runtime",
                return_value=cached,
            ) as ensure:
                with patch(
                    "embraion.versioning.subprocess.run",
                    return_value=completed,
                ):
                    result = resolve_project_runtime(
                        ["validate"],
                        "1.2.3",
                        start=root,
                    )

            self.assertEqual(0, result)
            args, kwargs = ensure.call_args
            self.assertEqual(("1.2.3",), args)
            self.assertEqual("sha256:" + ("a" * 64), kwargs["artifact_lock"].digest)

    def test_update_bypasses_pinned_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._manifest(root, "0.1.0")
            with patch("embraion.versioning.ensure_cached_runtime") as ensure:
                result = resolve_project_runtime(
                    ["update"],
                    "0.2.0.dev0",
                    start=root,
                )

            self.assertIsNone(result)
            ensure.assert_not_called()

    def test_mismatched_pin_delegates_to_cached_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._manifest(root, "0.1.0")
            framework = root / "cached-framework"
            framework.mkdir()

            cached = CachedRuntime(
                python=Path(sys.executable),
                framework_root=framework,
            )
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=7,
            )

            with patch.dict(os.environ, {}, clear=False):
                with patch(
                    "embraion.versioning.ensure_cached_runtime",
                    return_value=cached,
                ) as ensure:
                    with patch(
                        "embraion.versioning.subprocess.run",
                        return_value=completed,
                    ) as run:
                        result = resolve_project_runtime(
                            ["validate"],
                            "0.2.0.dev0",
                            start=root,
                        )

            self.assertEqual(7, result)
            ensure.assert_called_once_with(
                "0.1.0",
                artifact_lock=None,
            )
            command = run.call_args.args[0]
            environment = run.call_args.kwargs["env"]
            self.assertEqual(
                [str(cached.python), "-m", "embraion.cli", "validate"],
                command,
            )
            self.assertEqual("1", environment["EMBRAION_VERSION_RESOLVED"])
            self.assertEqual("0.1.0", environment["EMBRAION_RESOLVED_VERSION"])
            self.assertEqual(
                str(manifest.resolve()),
                environment["EMBRAION_RESOLVED_PROJECT"],
            )
            self.assertEqual(str(framework), environment["EMBRAION_HOME"])


if __name__ == "__main__":
    unittest.main()
