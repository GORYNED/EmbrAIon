from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from embraion.capabilities import (
    diagnose_external_capabilities,
    observation_scope,
    projected_skills,
    read_external_capabilities,
)


SCHEMA = Path(__file__).resolve().parents[2] / "schemas/external-capabilities.schema.json"
NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


class ExternalCapabilitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary_root = Path(self.temporary.name).resolve()
        self.root = temporary_root / "framework"
        self.project = temporary_root / "project"
        (self.root / "schemas").mkdir(parents=True)
        shutil.copyfile(SCHEMA, self.root / "schemas/external-capabilities.schema.json")
        (self.root / "framework.yaml").write_text("version: 0.20.0\n", encoding="utf-8")
        (self.project / ".embraion").mkdir(parents=True)
        self._yaml(self.project / ".embraion/project.yaml", {
            "framework": {"repository": "GORYNED/EmbrAIon", "version": "0.20.0"},
            "project": {"name": "Consumer"},
        })
        self.unity = {
            "id": "unity", "kind": "managed-bundle", "source": "builtin:unity",
            "version": "0.20.0", "license": "MIT", "hosts": ["codex"],
            "env-vars": [], "access": "workspace-write", "data-class": "PRIVATE",
            "selected-skills": ["unity-asset-audit"],
        }
        self.external = {
            "id": "spec-kit", "kind": "host-managed",
            "source": "https://github.com/github/spec-kit", "version": "1.2.3",
            "license": "MIT", "hosts": ["codex"], "env-vars": ["SPEC_KIT_TOKEN"],
            "access": "external-execution", "data-class": "PRIVATE",
        }

    @staticmethod
    def _yaml(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value), encoding="utf-8")

    def _inventory(self, *entries: dict) -> None:
        self._yaml(self.project / ".embraion/external-capabilities.yaml", {
            "schema-version": 1, "capabilities": list(entries),
        })

    def _manifest(self) -> Path:
        extension = self.root / "extensions/unity"
        skill = extension / "skills/unity-asset-audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Audit\n", encoding="utf-8")
        self._yaml(extension / "manifest.yaml", {
            "schema-version": 1, "id": "unity", "version": "0.20.0", "license": "MIT",
            "skills": {"unity-asset-audit": "skills/unity-asset-audit"},
        })
        return skill

    def test_absent_inventory_is_empty(self) -> None:
        self.assertEqual([], read_external_capabilities(self.root, self.project)["capabilities"])
        self.assertEqual([], diagnose_external_capabilities(self.root, self.project, "codex", now=NOW)["capabilities"])
        self.assertEqual({}, projected_skills(self.root, self.project, "codex"))

    def test_builtin_projection_requires_manifest_and_exact_pin(self) -> None:
        skill = self._manifest()
        self._inventory(self.unity)
        self.assertEqual({"unity-asset-audit": skill}, projected_skills(self.root, self.project, "codex"))
        self.assertEqual({}, projected_skills(self.root, self.project, "claude-code"))
        self._yaml(self.project / ".embraion/project.yaml", {"framework": {
            "repository": "GORYNED/EmbrAIon", "version": "0.19.2"}})
        with self.assertRaisesRegex(RuntimeError, "pin"):
            projected_skills(self.root, self.project, "codex")

    def test_builtin_selection_and_path_boundaries_fail_closed(self) -> None:
        skill = self._manifest()
        self._inventory({**self.unity, "selected-skills": ["unity-not-listed"]})
        with self.assertRaises(RuntimeError):
            projected_skills(self.root, self.project, "codex")
        self._inventory(self.unity)
        (skill / "escape").symlink_to(self.project)
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            projected_skills(self.root, self.project, "codex")
        (skill / "escape").unlink()
        self._yaml(self.root / "extensions/unity/manifest.yaml", {
            "schema-version": 1, "id": "unity", "version": "0.20.0", "license": "MIT",
            "skills": {"unity-asset-audit": "../../elsewhere"},
        })
        with self.assertRaises(RuntimeError):
            projected_skills(self.root, self.project, "codex")

    def test_stage_separation_and_environment_name_only(self) -> None:
        self._manifest()
        self._inventory(self.unity, self.external)
        report = diagnose_external_capabilities(self.root, self.project, "codex",
                                                environ={"SPEC_KIT_TOKEN": "sensitive-value"}, now=NOW)
        rows = {row["id"]: row for row in report["capabilities"]}
        self.assertEqual("verified", rows["unity"]["stages"]["installed-config"]["status"])
        self.assertEqual("unverified", rows["unity"]["stages"]["host-discovered"]["status"])
        self.assertEqual("unverified", rows["spec-kit"]["stages"]["installed-config"]["status"])
        self.assertEqual("unverified", rows["spec-kit"]["stages"]["executed"]["status"])
        self.assertEqual([{"name": "SPEC_KIT_TOKEN", "present": True}], rows["spec-kit"]["required-env"])
        self.assertFalse(rows["spec-kit"]["ready"])
        self.assertNotIn("sensitive-value", json.dumps(report))

    def test_bound_observation_remains_self_reported(self) -> None:
        self._inventory(self.external)
        observed = {"schema-version": 1, "scope": observation_scope(self.root, self.project, "codex"),
                    "host": "codex", "observed-at": NOW.isoformat(), "capabilities": [{
                        "id": "spec-kit", "source": self.external["source"],
                        "version-or-digest": "1.2.3", "stages": ["host-discovered", "executed"]}]}
        report = diagnose_external_capabilities(self.root, self.project, "codex", observation=observed, now=NOW)
        self.assertEqual("accepted-self-report", report["observation-status"])
        stages = report["capabilities"][0]["stages"]
        self.assertEqual("self-reported", stages["executed"]["status"])
        self.assertEqual("unverified", stages["tools-ready"]["status"])
        self.assertFalse(report["capabilities"][0]["ready"])
        observed["observed-at"] = (NOW - timedelta(days=2)).isoformat()
        stale = diagnose_external_capabilities(self.root, self.project, "codex", observation=observed, now=NOW)
        self.assertEqual("stale", stale["observation-status"])
        self.assertEqual("unverified", stale["capabilities"][0]["stages"]["executed"]["status"])
        observed["observed-at"] = NOW.isoformat()
        observed["capabilities"][0]["source"] = "host:forged"
        forged = diagnose_external_capabilities(self.root, self.project, "codex", observation=observed, now=NOW)
        self.assertEqual("identity-mismatch", forged["observation-status"])

    def test_invalid_metadata_and_embedded_secrets_rejected_without_echo(self) -> None:
        for entry in (
            {**self.external, "token": "sensitive-value"},
            {**self.external, "source": "https://user:sensitive-value@github.com/github/spec-kit"},
            {**self.external, "source": "https://github.com/github/spec-kit?token=sensitive-value"},
            {**self.external, "data-class": "UNKNOWN"},
            {**self.external, "version": "latest"},
            {**self.external, "version": "1.2.3", "digest": "sha256:" + "0" * 64},
            {**self.external, "host-requirements": {"copilot": ["plugins"]}},
        ):
            with self.subTest(entry=entry):
                self._inventory(entry)
                with self.assertRaises(RuntimeError) as failure:
                    read_external_capabilities(self.root, self.project)
                self.assertNotIn("sensitive-value", str(failure.exception))
        self._inventory(self.external, self.external)
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            read_external_capabilities(self.root, self.project)

    def test_config_symlink_is_rejected(self) -> None:
        other = self.project / "other.yaml"
        self._yaml(other, {"schema-version": 1, "capabilities": []})
        (self.project / ".embraion/external-capabilities.yaml").symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            read_external_capabilities(self.root, self.project)


if __name__ == "__main__":
    unittest.main()
