from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from embraion.artifacts import FrameworkArtifactLock
from embraion.versioning import (
    CachedRuntime,
    _check_windows_wheel_paths,
    _load_cached_runtime,
    _runtime_python,
    ensure_cached_runtime,
    find_project_manifest,
    install_project_runtime,
    package_version_for_pin,
    read_project_pin,
    resolve_project_runtime,
)


class VersioningTests(unittest.TestCase):
    def test_cached_runtime_marker_must_point_inside_installed_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = root / "versions/1.2.3"
            python = _runtime_python(environment)
            python.parent.mkdir(parents=True)
            python.touch()
            source = root / "source"
            installed = environment / "share/embraion"
            for framework in (source, installed):
                (framework / "core").mkdir(parents=True)
                (framework / "framework.yaml").write_text("name: EmbrAIon\n", encoding="utf-8")
                (framework / "core/catalog.yaml").write_text("schema-version: 1\n", encoding="utf-8")
            marker = environment / ".embraion-runtime.json"
            marker.write_text(json.dumps({"version": "1.2.3", "framework-root": str(source)}),
                              encoding="utf-8")
            self.assertIsNone(_load_cached_runtime(environment, "1.2.3"))
            marker.write_text(json.dumps({"version": "1.2.3", "framework-root": str(installed)}),
                              encoding="utf-8")
            self.assertEqual(installed.resolve(),
                             _load_cached_runtime(environment, "1.2.3").framework_root)

    def _wheel(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "embraion-1.2.3.data/data/share/embraion/" + "nested/" * 24 + "config.json",
                "{}",
            )

    def test_windows_wheel_path_preflight_accepts_short_cache_and_rejects_long_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "release.whl"
            self._wheel(wheel)
            with patch("embraion.versioning.sys.platform", "win32"):
                _check_windows_wheel_paths(Path("C:/EmbrAIonCache/versions/1.2.3"), wheel)
                with self.assertRaisesRegex(RuntimeError, "EMBRAION_CACHE_HOME"):
                    _check_windows_wheel_paths(
                        Path("C:/") / ("x" * 170) / "versions/1.2.3", wheel
                    )

    def test_windows_cache_lock_path_fails_before_creating_directories(self) -> None:
        cache = Path("C:/") / ("x" * 230)
        with patch("embraion.versioning.cache_home", return_value=cache), patch(
            "embraion.versioning.sys.platform", "win32"
        ), patch("embraion.versioning.Path.mkdir") as mkdir:
            with self.assertRaisesRegex(RuntimeError, "EMBRAION_CACHE_HOME"):
                ensure_cached_runtime("1.2.3")
        mkdir.assert_not_called()

    def test_existing_runtime_is_reused_before_windows_path_preflight(self) -> None:
        cache = Path("C:/") / ("x" * 230)
        cached = CachedRuntime(
            python=Path("C:/cached/python.exe"), framework_root=Path("C:/cached/framework")
        )
        with patch("embraion.versioning.cache_home", return_value=cache), patch(
            "embraion.versioning.sys.platform", "win32"
        ), patch("embraion.versioning._load_cached_runtime", return_value=cached), patch(
            "embraion.versioning.Path.mkdir"
        ) as mkdir:
            self.assertEqual(cached, ensure_cached_runtime("1.2.3"))
        mkdir.assert_not_called()

    def test_long_locked_cache_preserves_partial_runtime_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / ("x" * 75)
            environment = cache / "versions/1.2.3"
            environment.mkdir(parents=True)
            sentinel = environment / "partial.txt"
            sentinel.write_text("recoverable", encoding="utf-8")
            lock = FrameworkArtifactLock(
                repository="GORYNED/EmbrAIon", version="1.2.3", schema=1,
                source="github-release", release="v1.2.3",
                asset="embraion-1.2.3-py3-none-any.whl", digest="sha256:" + "a" * 64,
            )

            def download(_lock: FrameworkArtifactLock, destination: Path) -> None:
                self._wheel(destination)

            with patch("embraion.versioning.cache_home", return_value=cache), patch(
                "embraion.versioning.sys.platform", "win32"
            ), patch("embraion.versioning.download_locked_artifact", side_effect=download) as downloaded, patch(
                "embraion.versioning.venv.EnvBuilder.create"
            ) as create:
                with self.assertRaisesRegex(RuntimeError, "EMBRAION_CACHE_HOME"):
                    ensure_cached_runtime("1.2.3", artifact_lock=lock)
            downloaded.assert_called_once()
            create.assert_not_called()
            self.assertEqual("recoverable", sentinel.read_text(encoding="utf-8"))
            self.assertFalse((cache / "versions/.1.2.3.lock").exists())

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

    def test_locked_runtime_does_not_import_from_source_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._manifest(root, "0.1.0")
            cached = CachedRuntime(python=Path(sys.executable), framework_root=root / "cached")
            with patch.dict(os.environ, {"PYTHONPATH": str(root / "source")}), patch(
                "embraion.versioning.ensure_cached_runtime", return_value=cached
            ), patch("embraion.versioning.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(0, resolve_project_runtime(["validate"], "0.2.0", start=root))
            self.assertNotIn("PYTHONPATH", run.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
