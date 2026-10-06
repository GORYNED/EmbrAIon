from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion import cli
from embraion.artifacts import resolve_latest_release_artifact
from embraion.versioning import update_check_report

DIGEST = "sha256:" + ("b" * 64)


def _release_payload(version: str, **extra: object) -> dict[str, object]:
    asset = f"embraion-{version}-py3-none-any.whl"
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": asset,
                "digest": DIGEST,
                "browser_download_url": (
                    "https://github.com/GORYNED/EmbrAIon/releases/download/"
                    f"v{version}/{asset}"
                ),
            }
        ],
        **extra,
    }


def _urlopen_returning(payload: dict[str, object]):
    return patch(
        "embraion.artifacts.urlopen",
        side_effect=lambda *_args, **_kwargs: io.BytesIO(
            json.dumps(payload).encode("utf-8")
        ),
    )


def _write_manifest(root: Path, version: str, *, locked: bool = True) -> Path:
    manifest = root / ".embraion" / "project.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "framework:",
        "  repository: GORYNED/EmbrAIon",
        f"  version: {version}",
    ]
    if locked:
        lines += [
            "  artifact:",
            "    schema: 1",
            "    source: github-release",
            f"    release: v{version}",
            f"    asset: embraion-{version}-py3-none-any.whl",
            f"    digest: {DIGEST}",
        ]
    lines += ["project:", "  name: Demo", ""]
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return manifest


class LatestReleaseTests(unittest.TestCase):
    def test_resolves_latest_stable_release_with_verified_asset(self) -> None:
        with _urlopen_returning(_release_payload("1.4.0")) as opened:
            version, artifact = resolve_latest_release_artifact()

        self.assertEqual("1.4.0", version)
        self.assertEqual("v1.4.0", artifact["release"])
        self.assertEqual(DIGEST, artifact["digest"])
        request = opened.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/repos/GORYNED/EmbrAIon/releases/latest"))

    def test_rejects_non_stable_latest_tag(self) -> None:
        for tag in ("1.4.0", "v1.4.0-rc.1", "", "latest"):
            with self.subTest(tag=tag):
                with _urlopen_returning(_release_payload("1.4.0", tag_name=tag)):
                    with self.assertRaisesRegex(RuntimeError, "unsupported tag"):
                        resolve_latest_release_artifact()

    def test_rejects_prerelease_or_draft_metadata(self) -> None:
        for field in ("prerelease", "draft"):
            with self.subTest(field=field):
                with _urlopen_returning(_release_payload("1.4.0", **{field: True})):
                    with self.assertRaisesRegex(RuntimeError, "not a stable"):
                        resolve_latest_release_artifact()

    def test_latest_release_without_expected_asset_fails_closed(self) -> None:
        payload = _release_payload("1.4.0")
        payload["assets"] = []
        with _urlopen_returning(payload):
            with self.assertRaisesRegex(RuntimeError, "exactly one artifact"):
                resolve_latest_release_artifact()


    def test_latest_release_with_mismatched_asset_or_digest_fails_closed(self) -> None:
        cases = {
            "url": ("browser_download_url", "https://example.invalid/embraion.whl", "URL mismatch"),
            "digest": ("digest", "sha256:not-hex", "valid GitHub SHA-256"),
            "name": ("name", "embraion-1.3.0-py3-none-any.whl", "exactly one artifact"),
        }
        for label, (field, value, message) in cases.items():
            with self.subTest(field=label):
                payload = _release_payload("1.4.0")
                payload["assets"][0][field] = value
                with _urlopen_returning(payload):
                    with self.assertRaisesRegex(RuntimeError, message):
                        resolve_latest_release_artifact()


class UpdateCheckReportTests(unittest.TestCase):
    def test_reports_outdated_launcher_and_project_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_manifest(root, "1.2.0")
            before = manifest.read_bytes()

            with _urlopen_returning(_release_payload("1.10.0")):
                report = update_check_report("1.2.0", start=root)

            self.assertEqual(before, manifest.read_bytes())
            self.assertEqual(
                [".embraion/project.yaml"],
                sorted(
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*")
                    if path.is_file()
                ),
            )

        self.assertEqual("outdated", report["launcher-status"])
        self.assertEqual("outdated", report["project-status"])
        self.assertEqual("1.10.0", report["latest-version"])
        self.assertTrue(report["update-available"])
        self.assertTrue(report["artifact-locked"])
        self.assertEqual(2, len(report["actions"]))
        self.assertIn("pipx upgrade embraion", report["actions"][0])
        self.assertIn("embraion update", report["actions"][1])

    def test_current_launcher_with_outdated_project_suggests_only_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "1.3.0")
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.4.0", start=root)

        self.assertEqual("current", report["launcher-status"])
        self.assertEqual("outdated", report["project-status"])
        self.assertEqual(1, len(report["actions"]))
        self.assertIn("embraion update", report["actions"][0])

    def test_up_to_date_project_has_no_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "1.4.0")
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.4.0", start=root)

        self.assertEqual("current", report["project-status"])
        self.assertFalse(report["update-available"])
        self.assertEqual([], report["actions"])

    def test_current_unlocked_project_suggests_recording_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "1.4.0", locked=False)
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.4.0", start=root)

        self.assertFalse(report["artifact-locked"])
        self.assertFalse(report["update-available"])
        self.assertEqual(1, len(report["actions"]))
        self.assertIn("artifact lock", report["actions"][0])

    def test_without_project_reports_launcher_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.5.0", start=Path(temporary))

        self.assertIsNone(report["project"])
        self.assertIsNone(report["project-status"])
        self.assertIsNone(report["artifact-locked"])
        self.assertEqual("ahead", report["launcher-status"])
        self.assertFalse(report["update-available"])
        self.assertEqual([], report["actions"])

    def test_legacy_dev_pin_is_compared_by_its_release_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "1.3.0-dev", locked=False)
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.4.0", start=root)

        self.assertEqual("1.3.0-dev", report["project-pin"])
        self.assertEqual("outdated", report["project-status"])

    def test_unparseable_launcher_version_is_not_comparable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.4.0rc1", start=Path(temporary))

        self.assertEqual("not-comparable", report["launcher-status"])
        self.assertFalse(report["update-available"])


    def test_project_ahead_of_latest_has_no_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "1.5.0")
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.4.0", start=root)

        self.assertEqual("ahead", report["project-status"])
        self.assertFalse(report["update-available"])
        self.assertEqual([], report["actions"])

    def test_unlocked_current_project_with_outdated_launcher_names_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "1.4.0", locked=False)
            with _urlopen_returning(_release_payload("1.4.0")):
                report = update_check_report("1.3.0", start=root)

        self.assertEqual(2, len(report["actions"]))
        self.assertIn("1.4.0 launcher", report["actions"][1])

    def test_malformed_manifest_fails_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("framework: [unclosed\n", encoding="utf-8")
            with patch("embraion.artifacts.urlopen") as opened:
                with self.assertRaisesRegex(RuntimeError, "Could not read EmbrAIon project manifest"):
                    update_check_report("1.4.0", start=root)
            opened.assert_not_called()


class UpdateCheckCliTests(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_output_reports_available_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_manifest(root, "0.0.1")
            before = manifest.read_bytes()
            with _urlopen_returning(_release_payload("999.0.0")):
                code, stdout, _ = self._run(["update", str(root), "--check", "--json"])
            self.assertEqual(before, manifest.read_bytes())

        self.assertEqual(0, code)
        report = json.loads(stdout)
        self.assertEqual("999.0.0", report["latest-version"])
        self.assertTrue(report["update-available"])

    def test_text_output_lists_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "0.0.1")
            with _urlopen_returning(_release_payload("999.0.0")):
                code, stdout, _ = self._run(["update", str(root), "--check"])

        self.assertEqual(0, code)
        self.assertIn("Latest release: 999.0.0", stdout)
        self.assertIn("Next steps:", stdout)

    def test_text_output_does_not_claim_up_to_date_when_ahead(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_manifest(root, "999.0.0")
            with _urlopen_returning(_release_payload("0.0.1")):
                code, stdout, _ = self._run(["update", str(root), "--check"])

        self.assertEqual(0, code)
        self.assertIn("(ahead, locked)", stdout)
        self.assertNotIn("Up to date.", stdout)

    def test_check_rejects_framework_version(self) -> None:
        with patch("embraion.artifacts.urlopen") as opened:
            code, _, stderr = self._run(
                ["update", "--check", "--framework-version", "1.0.0"]
            )
        self.assertEqual(2, code)
        self.assertIn("--check cannot be combined", stderr)
        opened.assert_not_called()

    def test_json_requires_check(self) -> None:
        with patch("embraion.project.resolve_release_artifact") as resolve:
            code, _, stderr = self._run(["update", "--json"])
        self.assertEqual(2, code)
        self.assertIn("--json is only supported", stderr)
        resolve.assert_not_called()

    def test_network_failure_fails_without_writing(self) -> None:
        from urllib.error import URLError

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_manifest(root, "0.0.1")
            before = manifest.read_bytes()
            with patch("embraion.artifacts.urlopen", side_effect=URLError("offline")):
                code, _, stderr = self._run(["update", str(root), "--check"])
            self.assertEqual(before, manifest.read_bytes())

        self.assertEqual(2, code)
        self.assertIn("Could not resolve EmbrAIon release metadata", stderr)


if __name__ == "__main__":
    unittest.main()
