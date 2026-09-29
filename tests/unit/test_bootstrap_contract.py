from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root, read_json, read_yaml
from embraion.evals import evaluate_case
from embraion.project import generate_host, init_project, install, projection_is_verified, projection_plan
from embraion.runtime import route


class BootstrapContractTests(unittest.TestCase):
    def test_all_hosts_install_the_canonical_skill_and_verify_ownership(self) -> None:
        root = framework_root()
        canonical = (root / "core/skills/project-bootstrap/SKILL.md").read_text(encoding="utf-8")
        paths = {
            "codex": ".agents/skills/project-bootstrap/SKILL.md",
            "copilot": ".github/skills/project-bootstrap/SKILL.md",
            "claude-code": ".claude/skills/project-bootstrap/SKILL.md",
            "portable": "embraion/skills/project-bootstrap/SKILL.md",
        }
        with tempfile.TemporaryDirectory() as temporary:
            for host, relative in paths.items():
                with self.subTest(host=host):
                    project = Path(temporary) / host
                    init_project(project)
                    install(host, project)
                    self.assertEqual(canonical, (project / relative).read_text(encoding="utf-8"))
                    self.assertTrue(projection_is_verified(projection_plan(host, project)))
                    install(host, project)
                    self.assertTrue(projection_is_verified(projection_plan(host, project)))
                    bundle = Path(temporary) / f"bundle-{host}"
                    generate_host(root, host, bundle)
                    self.assertEqual(canonical, (bundle / relative).read_text(encoding="utf-8"))
                    if host == "portable":
                        catalog = read_yaml(bundle / "embraion/catalog.yaml")
                        entry = next(item for item in catalog["capabilities"] if item["id"] == "project-bootstrap")
                        self.assertTrue((bundle / "embraion" / entry["path"] / "SKILL.md").is_file())

    def test_bootstrap_eval_rejects_every_violated_property_and_missing_evidence(self) -> None:
        root = framework_root()
        case = read_yaml(root / "evals/cases/project-bootstrap.yaml")
        record = read_json(root / "tests/fixtures/evals/project-bootstrap.json")
        self.assertEqual((True, []), evaluate_case(case, record))
        self.assertFalse(case["context"]["live-host-execution"])
        for check in case["checks"]:
            with self.subTest(field=check["field"]):
                broken = copy.deepcopy(record)
                target = broken
                parts = check["field"].split(".")
                for part in parts[:-1]:
                    target = target[part]
                expected = check["value"]
                target[parts[-1]] = not expected if isinstance(expected, bool) else "unsupported"
                passed, failures = evaluate_case(case, broken)
                self.assertFalse(passed)
                self.assertEqual(1, len(failures))
        self.assertFalse(evaluate_case(case, {})[0])

    def test_empty_routing_with_core_specialists_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            self.assertEqual([], read_yaml(project / ".embraion/agents.yaml")["agents"])
            for role in ("architect", "worker", "reviewer", "validator", "steward"):
                result = route("codex", "substantial", "PRIVATE", role=role, project=project)
                self.assertEqual("host-default", result["resolution"])
                self.assertIsNone(result["model"])


if __name__ == "__main__":
    unittest.main()
