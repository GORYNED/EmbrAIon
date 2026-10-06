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
    prepare_pinned_install,
    read_framework_pin,
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
        schema: object = 1,
    ) -> Path:
        digest = digest or ("sha256:" + ("a" * 64))
        manifest = root / ".embraion" / "project.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            "framework:\n"
            "  repository: GORYNED/EmbrAIon\n"
            f"  version: {version}\n"
            "  artifact:\n"
            f"    schema: {schema}\n"
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

    def test_non_integer_schema_values_fail_closed(self) -> None:
        for value in ("true", "1.0"):
            with self.subTest(schema=value):
                with tempfile.TemporaryDirectory() as temporary:
                    manifest = self._manifest(
                        Path(temporary),
                        schema=value,
                    )
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "expected integer 1",
                    ):
                        read_project_artifact_lock(manifest)

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

    def test_noncanonical_lock_strings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(
                Path(temporary),
                digest="SHA256:" + ("A" * 64),
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "Malformed framework.artifact digest",
            ):
                read_project_artifact_lock(manifest)

        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(Path(temporary))
            text = manifest.read_text(encoding="utf-8").replace(
                "source: github-release",
                'source: " github-release"',
            )
            manifest.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "Malformed framework.artifact source",
            ):
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

    def test_framework_pin_reports_exact_version_and_optional_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            locked = read_framework_pin(self._manifest(root))
            manifest = root / ".embraion" / "project.yaml"
            manifest.write_text("framework:\n  repository: GORYNED/EmbrAIon\n  version: 1.2.3\n"
                                "project:\n  name: Demo\n", encoding="utf-8")
            unlocked = read_framework_pin(manifest)
        self.assertEqual({"version": "1.2.3", "digest": "sha256:" + "a" * 64}, locked)
        self.assertEqual({"version": "1.2.3", "digest": None}, unlocked)

    def test_framework_pin_refuses_missing_or_inexact_pins_without_echo(self) -> None:
        cases = {
            "latest": "'latest'", "ranges": "'>=1'", "partial": "'1.2'", "prerelease": "'1.2.3rc1'",
            "injected": '"1.2.3\\n::warning::injected"', "command": "'1.2.3; curl'",
            "unicode-digits": '"\\u0661.2.3"', "number": "1.2", "empty": "''", "missing": None,
        }
        for name, value in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                manifest = Path(temporary) / "project.yaml"
                version = "" if value is None else f"  version: {value}\n"
                manifest.write_text("framework:\n  repository: GORYNED/EmbrAIon\n" + version, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "framework.version") as error:
                    read_framework_pin(manifest)
                self.assertNotIn("curl", str(error.exception))
                self.assertNotIn("::warning", str(error.exception))
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "project.yaml"
            manifest.write_text("framework:\n  repository: Other/Fork\n  version: 1.2.3\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "framework.repository"):
                read_framework_pin(manifest)
            # A lock that disagrees with the pin is refused like every other artifact read.
            self._manifest(Path(temporary), release="v9.9.9")
            with self.assertRaisesRegex(RuntimeError, "mismatch"):
                read_framework_pin(Path(temporary) / ".embraion" / "project.yaml")

    def test_framework_pin_lock_errors_never_echo_lock_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._manifest(Path(temporary), asset='"x.whl\\n::warning::injected"')
            with self.assertRaisesRegex(RuntimeError, "framework.artifact") as error:
                read_framework_pin(manifest)
            self.assertNotIn("::warning", str(error.exception))
            self.assertNotIn("x.whl", str(error.exception))

    def test_framework_pin_command_prints_key_value_lines(self) -> None:
        from embraion.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._manifest(root)
            outputs = []
            for arguments in ([str(root)], [str(root), "--json"]):
                stdout = io.StringIO()
                with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                        patch("sys.stdout", stdout):
                    self.assertEqual(0, main(["framework", "pin", *arguments]))
                outputs.append(stdout.getvalue())
            (root / ".embraion" / "project.yaml").write_text(
                "framework:\n  repository: GORYNED/EmbrAIon\n  version: latest\n", encoding="utf-8")
            stderr = io.StringIO()
            with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                    patch("sys.stdout", io.StringIO()), patch("sys.stderr", stderr):
                self.assertEqual(2, main(["framework", "pin", str(root)]))
        self.assertEqual("version=1.2.3\ndigest=sha256:" + "a" * 64 + "\n", outputs[0])
        self.assertEqual({"version": "1.2.3", "digest": "sha256:" + "a" * 64}, json.loads(outputs[1]))
        self.assertIn("exact stable release", stderr.getvalue())

    def test_prepare_pinned_install_verifies_locked_wheel_or_names_exact_version(self) -> None:
        payload = b"wheel-bytes"
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self._manifest(root, digest=digest)
            with patch("embraion.artifacts.urlopen", return_value=Response(payload)) as opened:
                target = prepare_pinned_install(manifest, root / "wheel")
            self.assertEqual(payload, Path(target["wheel"]).read_bytes())
            self.assertEqual("https://github.com/GORYNED/EmbrAIon/releases/download/v1.2.3/"
                             "embraion-1.2.3-py3-none-any.whl", opened.call_args.args[0].full_url)
            self.assertEqual({"version": "1.2.3", "digest": digest},
                             {key: target[key] for key in ("version", "digest")})
            self._manifest(root, digest="sha256:" + "b" * 64)
            with patch("embraion.artifacts.urlopen", return_value=Response(payload)), \
                    self.assertRaisesRegex(RuntimeError, "digest mismatch"):
                prepare_pinned_install(manifest, root / "other")
            self.assertFalse((root / "other" / "embraion-1.2.3-py3-none-any.whl").exists())
            manifest.write_text("framework:\n  repository: GORYNED/EmbrAIon\n  version: 1.2.3\n", encoding="utf-8")
            with patch("embraion.artifacts.urlopen") as unlocked_open:
                self.assertEqual({"version": "1.2.3", "digest": "", "wheel": ""},
                                 prepare_pinned_install(manifest, root / "none"))
            unlocked_open.assert_not_called()

    def test_setup_action_is_composite_and_never_expands_inputs_in_scripts(self) -> None:
        import yaml

        root = Path(__file__).resolve().parents[2]
        action = yaml.safe_load((root / "actions" / "setup" / "action.yml").read_text(encoding="utf-8"))
        self.assertEqual("composite", action["runs"]["using"])
        steps = action["runs"]["steps"]
        self.assertTrue(steps[0]["uses"].startswith("actions/setup-python@"))
        self.assertEqual("${{ inputs.python-version }}", steps[0]["with"]["python-version"])
        scripts = [step["run"] for step in steps if "run" in step]
        self.assertTrue(scripts)
        for step in steps:
            if "run" in step:
                self.assertEqual("bash", step["shell"])
                self.assertNotIn("${{", step["run"])
        joined = "\n".join(scripts)
        self.assertIn("prepare_pinned_install", joined)
        self.assertIn("::stop-commands::", joined)
        self.assertIn('"embraion==$EMBRAION_VERSION"', joined)
        self.assertEqual({"version", "digest"}, set(action["outputs"]))


if __name__ == "__main__":
    unittest.main()
