from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from embraion.eval_oracles import calibration, oracle_metadata
from embraion.project import generate_host


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "evals/evolution/candidates/core-skills-package.json"
# Catalog entries added after this package was applied. The replay removes them
# (and restores the package-era catalog version) so the frozen package is still
# verified byte for byte; any other catalog drift keeps failing the replay.
LATER_CATALOG_VERSION = ("catalog-version: 9", "catalog-version: 8")
LATER_CATALOG_ENTRIES = ("handling-review-findings", "authorization", "owner-interaction", "architecture-decision")
# Wording edits made to packaged files after the package was applied, as
# (current, package-era) pairs. The replay restores the package-era text.
LATER_FILE_EDITS = {
    "core/skills/orchestration/SKILL.md": (
        ("No hosted bot review or cross-host external review is required by default.",
         "No Copilot Review or cross-host external review is required by default."),
        ("For an assignment that may make an architecture-level decision (dependency direction, ownership, "
         "a persisted format or stable identifier, a platform or build strategy, a foundational dependency, "
         "or a new or removed package), load the architecture-decision skill during planning so the record, "
         "or a stated waiver, is part of the implementation scope and the project's configured decisions "
         "check is among the required checks.\n\n", ""),
    ),
    "core/skills/planning/SKILL.md": (
        ("5. Decide whether the task makes an architecture-level decision: dependency direction, ownership, "
         "a persisted format or stable identifier, a platform or build strategy, a foundational dependency, "
         "or a new or removed package. When it does, plan the architecture-decision skill and its record as "
         "part of the change, not as a follow-up.\n6. Define observable", "5. Define observable"),
        ("7. Return a compact execution plan", "6. Return a compact execution plan"),
    ),
    "core/skills/compatibility-migration/SKILL.md": (
        ("   - Never reuse a retired identifier, number, or name for a different meaning. A rename is a removal "
         "plus an addition.\n   - Deprecate before removing: mark the old surface, name its replacement, and "
         "state how long it keeps working.\n   - Readers of persisted data formats tolerate unknown fields, so a newer writer "
         "does not break an older reader.\n", ""),
        (" A failed migration must leave the source data intact and recoverable: keep the original until the "
         "new form is verified.", ""),
    ),
    "core/skills/review/SKILL.md": (
        ("especially architecture, decisions, source authority,", "especially architecture, source authority,"),
        ("For a change that makes an architecture-level decision, check that the decision is recorded in the "
         "project's decisions folder, or that its waiver states a reason you accept, that any record it "
         "supersedes is linked both ways, and that no accepted record's decision text was rewritten; use "
         "architecture-decision. ", ""),
    ),
}


def restore_package_era_catalog(path: Path) -> None:
    text = path.read_text(encoding="utf-8").replace(*LATER_CATALOG_VERSION)
    kept = [line for line in text.splitlines(keepends=True)
            if not any(line.startswith(f"  - {{ id: {entry},") for entry in LATER_CATALOG_ENTRIES)]
    path.write_bytes("".join(kept).encode("utf-8"))


def restore_package_era_files(root: Path) -> None:
    for name, edits in LATER_FILE_EDITS.items():
        path = root / name
        text = path.read_text(encoding="utf-8")
        for current, original in edits:
            if text.count(current) != 1:
                raise AssertionError("later edit is not present exactly once: " + name)
            text = text.replace(current, original)
        path.write_bytes(text.encode("utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CoreSkillPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package = json.loads(PACKAGE.read_bytes())
        cls.temporary = tempfile.TemporaryDirectory()
        cls.candidate = Path(cls.temporary.name) / "candidate"
        cls.candidate.mkdir()
        # An independent Git root prevents git apply discovering the author's
        # checkout when the temporary directory is nested beneath a worktree.
        subprocess.run(["git", "-c", "core.fsmonitor=false", "init", "--quiet", str(cls.candidate)],
                       check=True, capture_output=True)
        # Exercise the Windows default even on Linux/macOS. Applying an
        # immutable proposal must preserve LF bytes despite checkout defaults.
        subprocess.run(["git", "-c", "core.fsmonitor=false", "config", "core.autocrlf", "true"],
                       cwd=cls.candidate, check=True, capture_output=True)
        for name in ("core", "adapters", "schemas", "templates"):
            shutil.copytree(ROOT / name, cls.candidate / name)
        shutil.copyfile(ROOT / "framework.yaml", cls.candidate / "framework.yaml")
        restore_package_era_catalog(cls.candidate / "core/catalog.yaml")
        restore_package_era_files(cls.candidate)
        for package in cls.package["packages"]:
            if digest(ROOT / package["patch"]) != package["sha256"]:
                raise AssertionError("proposal patch digest changed: " + package["id"])
        present = {item["path"]: digest(cls.candidate / item["path"])
                   if (cls.candidate / item["path"]).is_file() else None
                   for item in cls.package["files"]}
        if all(present[item["path"]] == item["after-sha256"] for item in cls.package["files"]):
            # The same roundtrip must remain reproducible after explicit Core
            # application. Reconstruct the declared baseline in the temp copy.
            for package in reversed(cls.package["packages"]):
                for suffix in (["--check"], []):
                    subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false",
                                    "apply", "--reverse", *suffix, str(ROOT / package["patch"])],
                                   cwd=cls.candidate, check=True, capture_output=True)
        elif not all(present[item["path"]] == item["before-sha256"] for item in cls.package["files"]):
            raise AssertionError("Core must match the complete declared baseline or final candidate")
        cls.original = {path.relative_to(cls.candidate).as_posix(): digest(path)
                        for path in cls.candidate.rglob("*")
                        if path.is_file() and ".git" not in path.relative_to(cls.candidate).parts}
        for package in cls.package["packages"]:
            patch = ROOT / package["patch"]
            if digest(patch) != package["sha256"]:
                raise AssertionError("proposal patch digest changed: " + package["id"])
            for suffix in (["--check"], []):
                subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false",
                                "apply", *suffix, str(patch)],
                               cwd=cls.candidate, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_patch_roundtrip_has_only_declared_changes(self) -> None:
        current = {path.relative_to(self.candidate).as_posix(): digest(path)
                   for path in self.candidate.rglob("*")
                   if path.is_file() and ".git" not in path.relative_to(self.candidate).parts}
        changed = {name for name in set(self.original) | set(current)
                   if self.original.get(name) != current.get(name)}
        declared = {item["path"] for item in self.package["files"]}
        self.assertEqual(declared, changed)
        self.assertEqual(14, len(changed))
        for item in self.package["files"]:
            with self.subTest(file=item["path"]):
                self.assertEqual(item["before-sha256"], self.original.get(item["path"]))
                self.assertEqual(item["after-sha256"], current[item["path"]])
                self.assertTrue(item["path"].startswith("core/"))
        self.assertEqual(self.package["canonical-core-mutated"],
                         self.package["approval"]["applied-to-canonical-core"])
        self.assertFalse(self.package["approval"]["applied-to-canonical-core"]
                         and not self.package["approval"]["received"])

    def test_catalog_and_all_host_projections_preserve_canonical_content(self) -> None:
        catalog = yaml.safe_load((self.candidate / "core/catalog.yaml").read_text())
        schema = json.loads((ROOT / "schemas/catalog.schema.json").read_bytes())
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(catalog)))
        capabilities = {entry["id"]: entry for entry in catalog["capabilities"]}
        self.assertEqual(set(self.package["roles"]),
                         {entry["id"] for entry in catalog["capabilities"] if entry["type"] == "agent"})
        self.assertNotIn("refactoring", capabilities)
        self.assertEqual("conditional", capabilities["security-assessment"]["load"])
        for entry in capabilities.values():
            path = self.candidate / "core" / entry["path"]
            self.assertTrue((path / "SKILL.md").is_file() if entry["type"] == "skill" else path.is_file())
        skills = {Path(item["path"]).parent.name for item in self.package["files"]
                  if item["path"].endswith("/SKILL.md")}
        with tempfile.TemporaryDirectory() as temporary:
            for host in ("codex", "claude-code", "copilot", "portable"):
                output = Path(temporary) / host
                output.mkdir()
                generate_host(self.candidate, host, output)
                for skill in skills:
                    with self.subTest(host=host, skill=skill):
                        matches = [path for path in output.rglob("SKILL.md") if path.parent.name == skill]
                        self.assertEqual(1, len(matches))
                        canonical = (self.candidate / "core/skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                        self.assertIn(canonical.strip(), matches[0].read_text(encoding="utf-8"))

    def test_scenario_references_and_calibrated_oracle_boundaries(self) -> None:
        scenarios = self.package["registered-scenarios"]
        self.assertEqual(39, len(scenarios))
        self.assertEqual(39, len({entry["id"] for entry in scenarios}))
        for entry in scenarios:
            registry = json.loads((ROOT / entry["registry"]).read_bytes())
            cases = (registry["targets"][entry["target"]]["cases"]
                     if "targets" in registry else registry["cases"])
            source = next(case for case in cases if case["id"] == entry["id"])
            self.assertEqual(source["language"], entry["language"])
            self.assertEqual(source["polarity"], entry["polarity"])
        oracle_ids = {entry["oracle-id"] for entry in scenarios}
        oracle_ids.update(self.package["additional-calibrated-oracles"])
        for oracle_id in sorted(oracle_ids):
            with self.subTest(oracle=oracle_id):
                metadata = oracle_metadata(oracle_id)
                self.assertTrue(metadata["coverage"]["proves"])
                self.assertTrue(metadata["coverage"]["does_not_prove"])
                result = calibration(oracle_id, ROOT)
                self.assertEqual("pass", result["status"], result)
                if oracle_id == "refactor-characterization-v1":
                    # This existing oracle labels calibration success for both
                    # correct controls and detected mutations, rather than
                    # repeating the candidate's expected grade in each row.
                    self.assertTrue({"changed-behavior", "dead-consumer", "changed-identity"}
                                    <= {item["id"] for item in result["outcomes"]})
                else:
                    self.assertTrue(any(item["expected"] == "fail" for item in result["outcomes"]))
        # These are instruction-review cases, not fabricated live passes.
        reviews = self.package["review-scenarios"]
        self.assertEqual(12, len(reviews))
        self.assertEqual({"en", "ru"}, {entry["language"] for entry in reviews})
        self.assertEqual({"positive", "negative"}, {entry["polarity"] for entry in reviews})
        self.assertTrue(all(entry["status"] == "specified-for-independent-instruction-review-not-live-executed"
                            for entry in reviews))


if __name__ == "__main__":
    unittest.main()
