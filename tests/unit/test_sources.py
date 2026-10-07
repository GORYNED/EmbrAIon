from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from jsonschema import Draft202012Validator

from embraion.cli import main
from embraion.common import framework_root
from embraion.execution import check_request_consistency
from embraion.policy import check_source_classes
from embraion.project import init_project
from embraion.security import collect_findings
from embraion.sources import (
    check_source_writes, load_registry, local_path_values, read_local_paths, registry_errors,
    set_local_path, source_status,
)

LOCAL_PATH_MARKER = "synthetic-checkout"


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def entry(source_id: str, **extra: object) -> dict:
    return {"id": source_id, "role": "reference", "write": "read-only", **extra}


class SourceRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        write(self.root / ".embraion" / "policy.yaml", {
            "sources": {"canonical": [], "protected": [], "generated": [], "external": []},
            "review": {"substantial-required": True},
            "privacy": {"default-class": "PRIVATE",
                        "sources": {"App": "PRIVATE", "Docs": "PUBLIC", "Vendor": "CONFIDENTIAL"}},
            "enforcement": {"enabled": False, "validation-profile": "affected", "require-review": False},
        })
        (self.root / "docs").mkdir()
        (self.root / "docs" / "sources.md").write_text("# Sources\n", encoding="utf-8")

    def registry(self, *sources: dict) -> None:
        write(self.root / ".embraion" / "sources.yaml", {"schema-version": 1, "sources": list(sources)})

    def test_absent_file_changes_nothing(self) -> None:
        self.assertEqual([], registry_errors(self.root))
        self.assertIsNone(load_registry(self.root))
        check_source_writes("workspace-write", ["Anything"], self.root)

    def test_schema_is_a_valid_strict_contract(self) -> None:
        schema = json.loads((framework_root() / "schemas" / "sources.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        good = {"schema-version": 1, "sources": [entry("App", description="Main", doc="docs/sources.md",
                                                       **{"data-class": "CONFIDENTIAL"})]}
        self.assertEqual([], list(validator.iter_errors(good)))
        for bad in (
            {"schema-version": 2, "sources": []},
            {"schema-version": 1},
            {"schema-version": 1, "sources": [], "extra": True},
            {"schema-version": 1, "sources": [{"id": "App", "role": "reference"}]},
            {"schema-version": 1, "sources": [entry("App", role="other")]},
            {"schema-version": 1, "sources": [entry("App", write="read-write")]},
            {"schema-version": 1, "sources": [entry("App", path="/somewhere")]},
            {"schema-version": 1, "sources": [entry("App", **{"data-class": "SECRET"})]},
        ):
            with self.subTest(bad=bad):
                self.assertTrue(list(validator.iter_errors(bad)))

    def test_valid_registry_loads(self) -> None:
        self.registry(entry("App", role="canonical-code", write="workspace-write"),
                      entry("Docs", doc="docs/sources.md"))
        self.assertEqual([], registry_errors(self.root))
        self.assertEqual(["App", "Docs"], [item["id"] for item in load_registry(self.root) or []])

    def test_unknown_and_duplicate_ids_fail_closed(self) -> None:
        self.registry(entry("App"), entry("App"), entry("Unlisted"))
        errors = "\n".join(registry_errors(self.root))
        self.assertIn("duplicate id", errors)
        self.assertIn("'Unlisted': id is not declared in privacy.sources", errors)
        with self.assertRaises(RuntimeError):
            load_registry(self.root)

    def test_ids_are_free_when_privacy_sources_is_not_declared(self) -> None:
        policy = yaml.safe_load((self.root / ".embraion" / "policy.yaml").read_text(encoding="utf-8"))
        del policy["privacy"]["sources"]
        write(self.root / ".embraion" / "policy.yaml", policy)
        self.registry(entry("Anything"))
        self.assertEqual([], registry_errors(self.root))

    def test_data_class_may_only_raise(self) -> None:
        self.registry(entry("App", **{"data-class": "PUBLIC"}), entry("Docs", **{"data-class": "CONFIDENTIAL"}),
                      entry("Vendor", **{"data-class": "CONFIDENTIAL"}))
        errors = registry_errors(self.root)
        self.assertEqual(1, len(errors))
        self.assertIn("'App'", errors[0])
        self.assertIn("may only raise", errors[0])

    def test_raised_class_applies_to_requests(self) -> None:
        self.registry(entry("Docs", **{"data-class": "PRIVATE"}))
        check_source_classes("PRIVATE", ["Docs"], self.root)
        with self.assertRaisesRegex(RuntimeError, r"PUBLIC is below the declared class of: Docs \(PRIVATE\)"):
            check_source_classes("PUBLIC", ["Docs"], self.root)

    def test_doc_must_be_an_existing_repository_relative_file(self) -> None:
        for doc in ("docs/missing.md", "../outside.md", "docs/../docs/sources.md", "/abs/path.md", "docs"):
            with self.subTest(doc=doc):
                self.registry(entry("App", doc=doc))
                self.assertEqual(1, len(registry_errors(self.root)))

    def test_malformed_yaml_and_symlink_are_errors(self) -> None:
        (self.root / ".embraion" / "sources.yaml").write_text("a: [", encoding="utf-8")
        self.assertEqual(1, len(registry_errors(self.root)))
        (self.root / ".embraion" / "sources.yaml").write_text("- 1\n", encoding="utf-8")
        self.assertEqual(1, len(registry_errors(self.root)))

    def test_write_requests_need_writable_registry_sources(self) -> None:
        self.registry(entry("App", write="workspace-write"), entry("Docs"), entry("Vendor", write="forbidden"))
        check_source_writes("workspace-write", ["App"], self.root)
        check_source_writes("read-only", ["Docs", "Vendor", "Unlisted"], self.root)
        for names in (["Docs"], ["App", "Vendor"], ["Unlisted"]):
            with self.subTest(names=names), self.assertRaisesRegex(RuntimeError, "not writable"):
                check_source_writes("workspace-write", names, self.root)

    def test_request_consistency_refuses_a_write_to_a_read_only_source(self) -> None:
        self.registry(entry("App", write="workspace-write"), entry("Docs"))
        base = {"routeClass": "ordinary", "candidates": [{"deployment": "one"}], "dataClass": "PRIVATE"}
        check_request_consistency({**base, "access": "workspace-write", "sourceIds": ["App"]}, self.root)
        with self.assertRaisesRegex(RuntimeError, r"Docs \(read-only\)"):
            check_request_consistency({**base, "access": "workspace-write", "sourceIds": ["App", "Docs"]}, self.root)


class LocalAvailabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        self.root.mkdir()
        write(self.root / ".embraion" / "sources.yaml", {"schema-version": 1, "sources": [
            entry("App", role="canonical-code", write="workspace-write"), entry("Docs")]})
        self.elsewhere = Path(temporary.name) / LOCAL_PATH_MARKER / "docs-checkout"
        self.elsewhere.mkdir(parents=True)

    def test_status_without_a_local_file_is_unset(self) -> None:
        rows = source_status(self.root)
        self.assertEqual([("App", "unset"), ("Docs", "unset")], [(row["id"], row["availability"]) for row in rows])
        self.assertEqual({"id", "role", "write", "availability"}, set(rows[0]))

    def test_set_roundtrip_reports_available_then_missing(self) -> None:
        self.assertEqual("Docs", set_local_path(self.root, "Docs", str(self.elsewhere)))
        self.assertEqual({"Docs": str(self.elsewhere.resolve())}, read_local_paths(self.root))
        self.assertEqual("available", {row["id"]: row["availability"] for row in source_status(self.root)}["Docs"])
        self.elsewhere.rmdir()
        self.assertEqual("missing", {row["id"]: row["availability"] for row in source_status(self.root)}["Docs"])

    def test_set_refuses_unknown_ids_and_missing_paths(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Unknown source id"):
            set_local_path(self.root, "Nope", str(self.elsewhere))
        with self.assertRaisesRegex(RuntimeError, "does not exist") as raised:
            set_local_path(self.root, "Docs", str(self.elsewhere / "absent"))
        self.assertNotIn(LOCAL_PATH_MARKER, str(raised.exception))
        self.assertFalse((self.root / ".embraion" / "state" / "sources-local.yaml").exists())

    def test_malformed_local_file_is_an_error(self) -> None:
        for content in ("- a\n", "App: relative/path\n", "App: 3\n"):
            with self.subTest(content=content):
                (self.root / ".embraion" / "state").mkdir(exist_ok=True)
                (self.root / ".embraion" / "state" / "sources-local.yaml").write_text(content, encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    read_local_paths(self.root)
                self.assertEqual({}, local_path_values(self.root))

    def test_security_scan_flags_a_tracked_file_with_a_recorded_path_without_printing_it(self) -> None:
        set_local_path(self.root, "Docs", str(self.elsewhere))
        (self.root / "notes.md").write_text(f"See {self.elsewhere.resolve()} for more.\n", encoding="utf-8")
        (self.root / "other.md").write_text(f"See {self.elsewhere.resolve()}-other for more.\n", encoding="utf-8")
        findings = [item for item in collect_findings(self.root) if item["id"].startswith("source-path-leak")]
        self.assertEqual(["source-path-leak:Docs:notes.md"], [item["id"] for item in findings])
        self.assertEqual("medium", findings[0]["severity"])
        self.assertNotIn(LOCAL_PATH_MARKER, json.dumps(findings))

    def test_security_scan_is_unchanged_without_a_local_file(self) -> None:
        (self.root / "notes.md").write_text(f"See {self.elsewhere.resolve()} for more.\n", encoding="utf-8")
        self.assertEqual([], [item for item in collect_findings(self.root) if "source-path-leak" in item["id"]])


class ValidateWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "consumer"
        self.project.mkdir()
        init_project(self.project, name="Consumer")

    def validate(self) -> tuple[int, list[dict]]:
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        stdout = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), patch("sys.stdout", stdout):
            code = main(["validate", "--json"])
        os.chdir(previous)
        return code, json.loads(stdout.getvalue())["issues"]

    def test_init_does_not_create_a_registry(self) -> None:
        self.assertFalse((self.project / ".embraion" / "sources.yaml").exists())
        self.assertFalse((self.project / ".embraion" / "state" / "sources-local.yaml").exists())
        code, issues = self.validate()
        self.assertEqual([], [item for item in issues if "sources" in item["code"] or "sources.yaml" in item["path"]])

    def test_valid_registry_passes_and_is_not_reported_as_inert(self) -> None:
        write(self.project / ".embraion" / "sources.yaml", {"schema-version": 1, "sources": [entry("App")]})
        _, issues = self.validate()
        self.assertEqual([], [item for item in issues if "sources.yaml" in item["path"]])

    def test_invalid_registry_fails_validation(self) -> None:
        write(self.project / ".embraion" / "sources.yaml", {"schema-version": 1, "sources": [
            entry("App"), entry("App", role="bogus")]})
        code, issues = self.validate()
        self.assertEqual(1, code)
        self.assertIn("sources-invalid", {item["code"] for item in issues if item["severity"] == "error"})


if __name__ == "__main__":
    unittest.main()
