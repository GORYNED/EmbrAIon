from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from embraion import __version__
from embraion.common import framework_root, read_json, write_json, read_yaml, write_yaml
from embraion.project import (
    _canonical_projection_destination, _projection_destination_id,
    _projection_state_path, _projection_recovery_path, _load_projection_state,
    _load_projection_recovery, _persist_projection_recovery_evidence, _projection_record,
    init_project, install, projection_plan, projection_is_verified, update_project,
)
from embraion.routing_authority import audit_routing_authority


class ProjectionDestinationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="Consumer")
        shutil.copytree(framework_root() / "tests/fixtures/routing-consumer", self.project, dirs_exist_ok=True)

    def root_install(self) -> Path:
        install("codex", self.project, config_mode="merge")
        return _projection_state_path(self.project, "codex")

    def legacy(self, host: str = "codex") -> Path:
        return self.project / ".embraion/state/projections" / f"{host}.json"

    def test_independent_inventories_verify_and_authority(self) -> None:
        root = self.root_install()
        original = root.read_bytes()
        self.assertEqual([], audit_routing_authority(self.project))
        for name in ("alternate-a", "alternate-b"):
            alternate = self.project / name
            install("codex", alternate, components=["config"], config_mode="merge")
            self.assertEqual(original, root.read_bytes())
            state = read_json(_projection_state_path(self.project, "codex", alternate))
            self.assertEqual(["config"], state["managed-components"])
            self.assertEqual([".codex/config.toml"], list(state["files"]))
            self.assertTrue(projection_is_verified(projection_plan("codex", alternate, components=["config"], config_mode="merge")))
        self.assertEqual(3, len(list(root.parent.glob("*.json"))))
        self.assertTrue(projection_is_verified(projection_plan("codex", self.project, config_mode="merge")))
        self.assertEqual([], audit_routing_authority(self.project))

    def test_generated_edits_fail_closed_without_cross_destination_damage(self) -> None:
        root = self.root_install()
        alternate = self.project / "alternate"
        install("codex", alternate, components=["agents"])
        other = _projection_state_path(self.project, "codex", alternate)
        originals = (root.read_bytes(), other.read_bytes())
        generated = alternate / ".codex/agents/reviewer.toml"
        generated.write_text(generated.read_text() + "# local edit\n")
        self.assertFalse(projection_is_verified(projection_plan("codex", alternate, components=["agents"])))
        self.assertTrue(projection_is_verified(projection_plan("codex", self.project, config_mode="merge")))
        generated = self.project / ".agents/skills/routing-configuration/SKILL.md"
        generated.write_text(generated.read_text() + "\n```yaml\nmodel: example-basic-v1\n```\n")
        self.assertFalse(projection_is_verified(projection_plan("codex", self.project, config_mode="merge")))
        self.assertTrue(audit_routing_authority(self.project))
        self.assertEqual(originals, (root.read_bytes(), other.read_bytes()))

    def test_components_and_hosts_keep_independent_ownership(self) -> None:
        for host, selections in (("codex", ("config", "skills", "agents", None)),
                                 ("copilot", ("skills", "agents", None)),
                                 ("claude-code", ("skills", "agents", None)),
                                 ("portable", ("bundle", None))):
            records = {}
            for index, component in enumerate(selections):
                destination = self.project / f"{host}-{index}"
                components = [component] if component else None
                install(host, destination, components=components)
                self.assertTrue(projection_is_verified(projection_plan(host, destination, components=components)))
                records[_projection_state_path(self.project, host, destination)] = read_json(_projection_state_path(self.project, host, destination))
                for path, record in records.items():
                    self.assertEqual(record, read_json(path))

    def test_selective_install_preserves_merge_evidence(self) -> None:
        state = self.root_install()
        install("codex", self.project, components=["skills"])
        record = read_json(state)
        self.assertEqual("merge", record["config-mode"])
        self.assertEqual(["agents", "config", "skills"], record["managed-components"])
        self.assertIn(".codex/config.toml", record["files"])

    def test_matching_legacy_reads_without_mutation_then_migrates(self) -> None:
        scoped = self.root_install()
        original = scoped.read_bytes()
        legacy = self.legacy()
        scoped.replace(legacy)
        self.assertEqual(read_json(legacy), _load_projection_state(self.project, "codex", self.project))
        projection_plan("codex", self.project, config_mode="merge")
        install("codex", self.project, dry_run=True, config_mode="merge")
        self.assertEqual(original, legacy.read_bytes())
        self.assertFalse(scoped.exists())
        install("codex", self.project, components=["skills"])
        self.assertFalse(legacy.exists())
        self.assertEqual("merge", read_json(scoped)["config-mode"])

    def test_nonmatching_legacy_remains_unassigned_and_unchanged(self) -> None:
        scoped = self.root_install()
        legacy = self.legacy()
        scoped.replace(legacy)
        original = legacy.read_bytes()
        alternate = self.project / "alternate"
        self.assertIsNone(_load_projection_state(self.project, "codex", alternate))
        install("codex", alternate, components=["config"], config_mode="merge")
        self.assertEqual(original, legacy.read_bytes())
        self.assertIsNotNone(_load_projection_state(self.project, "codex", self.project))

    def test_scoped_precedence_and_invalid_records_do_not_fallback(self) -> None:
        scoped = self.root_install()
        valid = read_json(scoped)
        write_json(self.legacy(), valid)
        for invalid in ({**valid, "host": "copilot"}, {**valid, "destination": str(self.project / "other")},
                        {**valid, "schema-version": 2}, {**valid, "files": []}, []):
            with self.subTest(invalid=invalid):
                write_json(scoped, invalid)
                self.assertIsNone(_load_projection_state(self.project, "codex", self.project))
        scoped.write_text("invalid json")
        self.assertIsNone(_load_projection_state(self.project, "codex", self.project))
        self.assertEqual([], audit_routing_authority(self.project))

    def test_recovery_is_destination_scoped_and_validates_pin(self) -> None:
        scoped = self.root_install()
        record = read_json(scoped)
        scoped.unlink()
        manifest = read_yaml(self.project / ".embraion/project.yaml")
        target = manifest["framework"]["version"]
        recovery = {**record, "source-framework-version": "0.15.1", "target-framework-version": target}
        _persist_projection_recovery_evidence(self.project, {"codex": recovery})
        root_recovery = _projection_recovery_path(self.project, "codex")
        original = root_recovery.read_bytes()
        alternate = self.project / "alternate"
        alternate.mkdir()
        alternate_recovery = {**recovery, "destination": str(alternate)}
        _persist_projection_recovery_evidence(self.project, {"codex": alternate_recovery})
        install("codex", alternate, components=["config"], config_mode="merge")
        self.assertEqual(original, root_recovery.read_bytes())
        self.assertFalse(_projection_recovery_path(self.project, "codex", alternate).exists())
        self.assertEqual(recovery, _load_projection_recovery(self.project, "codex", self.project))
        write_json(root_recovery, {**recovery, "target-framework-version": "invalid"})
        self.assertIsNone(_load_projection_recovery(self.project, "codex", self.project))

    def test_legacy_recovery_migration_and_damaged_state_blocks_recovery(self) -> None:
        scoped = self.root_install()
        record = read_json(scoped)
        scoped.unlink()
        record.update({"source-framework-version": "0.15.1", "target-framework-version": __version__})
        legacy = self.legacy().with_suffix(".recovery.json")
        write_json(legacy, record)
        self.assertEqual(record, _load_projection_recovery(self.project, "codex", self.project))
        self.assertIsNone(_load_projection_recovery(self.project, "codex", self.project / "other"))
        scoped.write_text("invalid json")
        self.assertIsNone(_load_projection_recovery(self.project, "codex", self.project))
        scoped.unlink()
        install("codex", self.project, config_mode="merge")
        self.assertTrue(scoped.is_file())
        self.assertFalse(legacy.exists())

    def test_invalid_recovery_survives_successful_install(self) -> None:
        scoped = self.root_install()
        record = read_json(scoped)
        record.update({"source-framework-version": "0.15.1", "target-framework-version": "invalid"})
        paths = (self.legacy().with_suffix(".recovery.json"), _projection_recovery_path(self.project, "codex"))
        for path in paths:
            write_json(path, record)
        originals = [path.read_bytes() for path in paths]
        install("codex", self.project, config_mode="merge")
        self.assertEqual(originals, [path.read_bytes() for path in paths])

    def test_write_failure_preserves_prior_evidence(self) -> None:
        scoped = self.root_install()
        legacy = self.legacy()
        scoped.replace(legacy)
        original = legacy.read_bytes()
        with patch("embraion.project.write_json", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                install("codex", self.project, config_mode="merge")
        self.assertEqual(original, legacy.read_bytes())
        with patch("embraion.project.write_json"):
            with self.assertRaisesRegex(RuntimeError, "write verification failed"):
                install("codex", self.project, config_mode="merge")
        self.assertEqual(original, legacy.read_bytes())

    def test_failed_install_preserves_legacy_and_obsolete_prune_is_local(self) -> None:
        scoped = self.root_install()
        alternate = self.project / "alternate"
        install("codex", alternate, components=["skills"])
        other = _projection_state_path(self.project, "codex", alternate).read_bytes()
        obsolete = self.project / ".codex/agents/obsolete.toml"
        obsolete.write_text("obsolete generated file\n")
        record = read_json(scoped)
        record["files"][".codex/agents/obsolete.toml"] = hashlib.sha256(obsolete.read_bytes()).hexdigest()
        write_json(scoped, record)
        install("codex", self.project, components=["agents"], prune=True)
        self.assertFalse(obsolete.exists())
        self.assertEqual(other, _projection_state_path(self.project, "codex", alternate).read_bytes())
        scoped.replace(self.legacy())
        original = self.legacy().read_bytes()
        generated = self.project / ".codex/agents/reviewer.toml"
        generated.write_text(generated.read_text() + "# modified\n")
        with self.assertRaises(RuntimeError):
            install("codex", self.project, components=["agents"])
        self.assertEqual(original, self.legacy().read_bytes())

    def test_update_preserves_root_and_alternate_ownership(self) -> None:
        scoped = self.root_install()
        alternate = self.project / "alternate"
        install("codex", alternate, components=["config"], config_mode="merge")
        paths = (scoped, _projection_state_path(self.project, "codex", alternate))
        originals = [path.read_bytes() for path in paths]
        manifest = self.project / ".embraion/project.yaml"
        data = read_yaml(manifest)
        data["framework"]["version"] = "0.15.1"
        write_yaml(manifest, data)
        with patch("embraion.project.resolve_release_artifact", return_value=None):
            update_project(self.project)
        self.assertEqual(originals, [path.read_bytes() for path in paths])
        install("codex", alternate, components=["config"], config_mode="merge")
        self.assertEqual(originals[0], scoped.read_bytes())

    def test_destination_identity_root_relative_external_and_relocation(self) -> None:
        self.assertEqual("root", _projection_destination_id(self.project, self.project / "child/.."))
        alternate = self.project / "alternate"
        expected = hashlib.sha256(b"relative:alternate").hexdigest()
        self.assertEqual(expected, _projection_destination_id(self.project, alternate))
        self.assertEqual(expected, _projection_destination_id(self.project / "relocated", self.project / "relocated/alternate"))
        external = _canonical_projection_destination(self.project.parent / "external")
        self.assertEqual(hashlib.sha256(("absolute:" + external.as_posix()).encode()).hexdigest(), _projection_destination_id(self.project, external))
        before = _projection_destination_id(self.project, alternate)
        alternate.mkdir()
        self.assertEqual(before, _projection_destination_id(self.project, alternate))
        self.assertEqual(before, _projection_destination_id(self.project, alternate / "child/.."))
        install("codex", alternate, components=["skills"])
        self.assertEqual(str(alternate), read_json(_projection_state_path(self.project, "codex", alternate))["destination"])

    def test_windows_case_sensitive_record_and_containment(self) -> None:
        scoped = self.root_install()
        with patch("embraion.project._canonical_projection_destination", side_effect=[
            PureWindowsPath("C:/Consumer/MixedCase"), PureWindowsPath("C:/Consumer/mixedcase"),
        ]):
            self.assertIsNone(_projection_record(scoped, "codex", self.project))
        project = PureWindowsPath("C:/Consumer")
        alternate = PureWindowsPath("C:/consumer/alternate")
        with patch("embraion.project._canonical_projection_destination", side_effect=[project, alternate]):
            expected = hashlib.sha256(("absolute:" + alternate.as_posix()).encode()).hexdigest()
            self.assertEqual(expected, _projection_destination_id(self.project, self.project))

    def test_cleanup_preserves_evidence_replaced_during_write(self) -> None:
        scoped = self.root_install()
        legacy = self.legacy()
        scoped.replace(legacy)
        replacement = {**read_json(legacy), "destination": str(self.project / "other")}

        def write_and_replace(path: Path, record: dict) -> None:
            write_json(path, record)
            write_json(legacy, replacement)

        with patch("embraion.project.write_json", side_effect=write_and_replace):
            install("codex", self.project, config_mode="merge")
        self.assertEqual(replacement, read_json(legacy))

    def test_native_case_semantics(self) -> None:
        destination = self.project / "MixedCase"
        destination.mkdir()
        alias = self.project / "mixedcase"
        if alias.exists():
            self.assertEqual(_projection_destination_id(self.project, destination), _projection_destination_id(self.project, alias))
        else:
            alias.mkdir()
            self.assertNotEqual(_projection_destination_id(self.project, destination), _projection_destination_id(self.project, alias))

    def test_symlink_alias_uses_single_record(self) -> None:
        destination = self.project / "alternate"
        destination.mkdir()
        alias = self.project / "alias"
        try:
            alias.symlink_to(destination, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks unavailable")
        self.assertEqual(_projection_destination_id(self.project, destination), _projection_destination_id(self.project, alias))
        install("codex", destination, components=["skills"])
        install("codex", alias, components=["agents"])
        self.assertEqual(["agents", "skills"], read_json(_projection_state_path(self.project, "codex", alias))["managed-components"])


if __name__ == "__main__":
    unittest.main()
