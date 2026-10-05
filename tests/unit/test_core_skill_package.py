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
                        canonical = (self.candidate / "core/skills" / skill / "SKILL.md").read_text()
                        self.assertIn(canonical.strip(), matches[0].read_text())

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
