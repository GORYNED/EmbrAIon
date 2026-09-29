from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from embraion.bootstrap import apply_bootstrap, plan_bootstrap
from embraion.common import read_yaml, write_yaml
from embraion.project import init_project


class BootstrapTests(unittest.TestCase):
    def test_environment_parameter_mapping_is_preserved_without_false_secret(self):
        profile = {"profiles": {"fast": {"commands": ["python scripts/check.py"],
            "parameters": {"token": {"environment": "TEST_TOKEN", "required": True}}}, "affected": [], "full": []}}
        write_yaml(self.root / ".embraion/validation.yaml", profile)
        before = self.snapshot()
        apply_bootstrap(self.root, plan_bootstrap(self.root))
        self.assertEqual(before, self.snapshot())

    def test_credential_candidates_and_schema_errors_do_not_expose_values(self):
        import json
        value = "synthetic" + "-credential"
        for flag in ("api-key", "token", "password", "auth", "credentials", "access-key", "client-secret", "access_token"):
            with self.subTest(flag=flag):
                self.source(".github/workflows/check.yml", f"jobs:\n  test:\n    steps:\n      - run: pytest --{flag}={value}\n")
                self.source("package.json", json.dumps({"scripts": {"lint": f"check --{flag}={value}"}}))
                plan = plan_bootstrap(self.root)
                self.assertNotIn(value, json.dumps(plan))
                self.assertFalse(any(item.get("command") for item in plan["evidence"]))
                self.assertTrue(any("Credential-bearing" in item for item in plan["limitations"]))
        for command in ("pytest --client-secret short", "pytest --credentials abc", "pytest --token=x"):
            self.source(".github/workflows/check.yml", f"jobs:\n  test:\n    steps:\n      - run: {command}\n")
            plan = plan_bootstrap(self.root)
            self.assertFalse(any(item.get("command") for item in plan["evidence"]))
        write_yaml(self.root / ".embraion/validation.yaml", {"profiles": {"fast": [f"pytest --token={value}"]}})
        with self.assertRaises(RuntimeError) as raised:
            plan_bootstrap(self.root)
        self.assertNotIn(value, str(raised.exception))
        write_yaml(self.root / ".embraion/validation.yaml", {"profiles": {"fast": {"commands": [], "parameters": {"token": {"invalid": value}}}}})
        with self.assertRaises(RuntimeError) as raised:
            plan_bootstrap(self.root)
        self.assertNotIn(value, str(raised.exception))

    def test_optional_execution_and_pricing_use_project_schemas_and_survive(self):
        execution = {"schemaVersion": 1, "bindings": {}}
        pricing = {"schemaVersion": 1, "sources": {"example": {
            "url": "https://example.invalid/pricing", "adapter": "openai",
            "currency": "USD", "freshnessDays": 7,
            "skus": {"example": {"sku": "example", "patterns": {"input": "example"}}},
        }}}
        for name, value in (("execution", execution), ("pricing", pricing)):
            write_yaml(self.root / f".embraion/{name}.yaml", value)
        before = self.snapshot()
        apply_bootstrap(self.root, plan_bootstrap(self.root))
        self.assertEqual(before, self.snapshot())
        for name, value in (("execution", execution), ("pricing", pricing)):
            with self.subTest(name=name):
                path = self.root / f".embraion/{name}.yaml"
                write_yaml(path, {"invalid": True})
                invalid_before = self.snapshot()
                with self.assertRaisesRegex(RuntimeError, f"Invalid bootstrap {name}-config"):
                    plan_bootstrap(self.root)
                self.assertEqual(invalid_before, self.snapshot())
                write_yaml(path, value)

    def test_existing_noncanonical_policy_uses_canonical_path_matching(self):
        self.source("docs/architecture.md", "# Architecture\nExternal or generated content.\n")
        for category in ("external", "generated"):
            for pattern in ("docs/**", "docs\\**"):
                with self.subTest(category=category, pattern=pattern):
                    policy = read_yaml(self.root / ".embraion/policy.yaml")
                    policy["sources"]["external"] = []
                    policy["sources"]["generated"] = []
                    policy["sources"][category] = [pattern]
                    write_yaml(self.root / ".embraion/policy.yaml", policy)
                    plan = plan_bootstrap(self.root)
                    self.assertFalse(any(change["path"] == ".embraion/knowledge.yaml" for change in plan["changes"]))
                    self.assertTrue(any("ownership requires review" in item for item in plan["limitations"]))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        init_project(self.root)

    def source(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def snapshot(self):
        return {p.name: p.read_bytes() for p in (self.root / ".embraion").glob("*.yaml")}

    def test_minimal_repository_is_read_only_and_no_facts_invented(self):
        before = self.snapshot()
        with mock.patch("subprocess.run", side_effect=AssertionError("No commands allowed")):
            plan = plan_bootstrap(self.root)
            apply_bootstrap(self.root, plan)
        self.assertEqual([], plan["changes"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "docs").exists())

    def test_real_docs_and_manifest_validation_converge(self):
        self.source("docs/architecture.md", "# Architecture\nThe package exports a library.\n")
        self.source("package.json", '{"scripts":{"lint":"eslint .","test":"node --test","build":"tsc"}}')
        plan = plan_bootstrap(self.root)
        self.assertTrue(plan["requires-review"])
        apply_bootstrap(self.root, plan)
        knowledge = read_yaml(self.root / ".embraion/knowledge.yaml")
        self.assertEqual("docs/architecture.md", knowledge["slots"]["architecture"])
        self.assertIsNone(knowledge["slots"]["persistence"])
        profiles = read_yaml(self.root / ".embraion/validation.yaml")["profiles"]
        self.assertEqual(["npm run lint"], profiles["fast"])
        self.assertEqual(["npm run lint", "npm run test"], profiles["affected"])
        self.assertEqual(["npm run lint", "npm run test", "npm run build"], profiles["full"])
        before = self.snapshot()
        self.assertEqual([], plan_bootstrap(self.root)["changes"])
        apply_bootstrap(self.root, plan_bootstrap(self.root))
        self.assertEqual(before, self.snapshot())

    def test_stricter_policy_populated_slots_profiles_and_other_configs_preserved(self):
        knowledge = read_yaml(self.root / ".embraion/knowledge.yaml")
        knowledge["slots"]["architecture"] = "existing-design.md"
        knowledge["custom"] = "existing-contract.md"
        write_yaml(self.root / ".embraion/knowledge.yaml", knowledge)
        policy = read_yaml(self.root / ".embraion/policy.yaml")
        policy["privacy"]["default-class"] = "CONFIDENTIAL"
        policy["enforcement"]["enabled"] = True
        policy["enforcement"]["require-review"] = True
        policy["sources"]["protected"] = ["contracts/**"]
        write_yaml(self.root / ".embraion/policy.yaml", policy)
        write_yaml(self.root / ".embraion/validation.yaml", {"profiles": {"fast": ["existing-check"], "affected": [], "full": []}})
        # A comment in an untouched config must survive byte-for-byte.
        with (self.root / ".embraion/routing.yaml").open("a", encoding="utf-8") as stream:
            stream.write("# intentional host-default\n")
        self.source("docs/architecture.md", "# New candidate\n")
        self.source("package.json", '{"scripts":{"lint":"eslint .","test":"node --test"}}')
        before = self.snapshot()
        apply_bootstrap(self.root, plan_bootstrap(self.root))
        after = self.snapshot()
        for name in before:
            if name != "validation.yaml":
                self.assertEqual(before[name], after[name], name)
        self.assertEqual(["existing-check"], read_yaml(self.root / ".embraion/validation.yaml")["profiles"]["fast"])

    def test_ci_literal_checks_are_real_complex_context_is_not_executable(self):
        self.source(".github/workflows/check.yml", "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: ruff check .\n      - run: python -m pytest tests\n      - run: echo ${{ secrets.TOKEN }}\n  matrix:\n    strategy:\n      matrix:\n        python: ['3.11']\n    steps:\n      - run: python -m pytest other-tests\n")
        plan = plan_bootstrap(self.root)
        validation = next(c["value"] for c in plan["changes"] if c["path"].endswith("validation.yaml"))
        self.assertEqual(["ruff check ."], validation["profiles"]["fast"])
        self.assertEqual(["ruff check .", "python -m pytest tests"], validation["profiles"]["full"])
        self.assertNotIn("secrets.TOKEN", str(plan))
        self.assertTrue(any(e["kind"] == "command-candidate" and e["path"].endswith("check.yml") for e in plan["evidence"]))

    def test_ambiguous_authority_and_package_manager_remain_unbound(self):
        self.source("ARCHITECTURE.md", "# Design A\n")
        self.source("docs/architecture.md", "# Design B\n")
        self.source("package.json", '{"scripts":{"test":"vitest"}}')
        self.source("pnpm-lock.yaml", "lockfileVersion: 9\n")
        plan = plan_bootstrap(self.root)
        self.assertFalse(any(c["path"].endswith("knowledge.yaml") for c in plan["changes"]))
        self.assertFalse(any(c["path"].endswith("validation.yaml") for c in plan["changes"]))
        self.assertIn("Ambiguous architecture", str(plan["limitations"]))

    def test_changed_or_added_evidence_blocks_all_writes(self):
        self.source("docs/architecture.md", "# Design\n")
        for mutation in (lambda: self.source("docs/architecture.md", "# Changed\n"),
                         lambda: self.source("CONTRIBUTING.md", "# Contributing\n"),
                         lambda: self.source(".embraion/custom.txt", "intentional config\n")):
            plan = plan_bootstrap(self.root)
            mutation()
            before = self.snapshot()
            with self.assertRaises(RuntimeError):
                apply_bootstrap(self.root, plan)
            self.assertEqual(before, self.snapshot())

    def test_tampered_proposals_root_and_paths_block(self):
        self.source("docs/architecture.md", "# Design\n")
        plan = plan_bootstrap(self.root)
        variants = []
        changed = copy.deepcopy(plan)
        changed["changes"][0]["value"]["slots"]["architecture"] = "invented.md"
        variants.append(changed)
        changed = copy.deepcopy(plan)
        changed["root"] += "-other"
        variants.append(changed)
        changed = copy.deepcopy(plan)
        changed["snapshots"]["../escape"] = "a" * 64
        variants.append(changed)
        changed = copy.deepcopy(plan)
        changed["snapshots"]["C:/escape"] = "a" * 64
        variants.append(changed)
        before = self.snapshot()
        for changed in variants:
            with self.assertRaises(RuntimeError):
                apply_bootstrap(self.root, changed)
            self.assertEqual(before, self.snapshot())

    def test_invalid_candidate_or_existing_config_blocks_before_write(self):
        self.source("docs/architecture.md", "# Design\n")
        plan = plan_bootstrap(self.root)
        self.source(".embraion/validation.yaml", "profiles: invalid\n")
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            plan_bootstrap(self.root)
        with self.assertRaises(RuntimeError):
            apply_bootstrap(self.root, plan)
        self.assertEqual(before, self.snapshot())

    def test_initialized_project_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "initialized"):
                plan_bootstrap(Path(temporary))

    def test_symlink_evidence_cannot_be_applied(self):
        self.source("docs/architecture.md", "# Design\n")
        plan = plan_bootstrap(self.root)
        target = self.root / "docs/architecture.md"
        target.unlink()
        try:
            target.symlink_to(self.root / "package.json")
        except OSError:
            self.skipTest("Creating symlinks requires platform permission")
        with self.assertRaisesRegex(RuntimeError, "Linked"):
            apply_bootstrap(self.root, plan)
