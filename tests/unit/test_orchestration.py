from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion.common import framework_root, read_yaml, write_yaml
from embraion.project import init_project, install, load_agents
from embraion.runtime import route
from embraion.validation import find_model_agnostic_violations


CORE_ROLES = {
    "lead", "worker", "reviewer", "architect", "analyst", "validator",
    "researcher", "steward",
}
SPECIALISTS = CORE_ROLES - {"lead"}


class OrchestrationTests(unittest.TestCase):
    def _lead(self) -> dict:
        return read_yaml(framework_root() / "core/agents/lead.yaml")

    def _assert_semantic_clause(self, clauses: list[str], *terms: str) -> None:
        self.assertTrue(
            any(all(term in clause.lower() for term in terms) for clause in clauses),
            f"Missing semantic clause containing {terms!r}",
        )

    def _config(self, project: Path) -> dict:
        return tomllib.loads(
            (project / ".codex/config.toml").read_text(encoding="utf-8")
        )

    def _assert_root_contract(self, config: dict) -> None:
        instructions = config["developer_instructions"]
        lead = self._lead()
        self.assertIn(lead["purpose"], instructions)
        for section in ("responsibilities", "restrictions"):
            for clause in lead[section]:
                with self.subTest(section=section, clause=clause):
                    self.assertIn(clause, instructions)
        self.assertTrue(config["agents"]["enabled"])

    def test_canonical_roles_remain_model_neutral_and_discoverable(self) -> None:
        root = framework_root()
        agents = load_agents(root)
        self.assertEqual(CORE_ROLES, {agent["id"] for agent in agents})
        catalog = read_yaml(root / "core/catalog.yaml")
        self.assertEqual(
            CORE_ROLES,
            {item["id"] for item in catalog["capabilities"] if item["type"] == "agent"},
        )
        for agent in agents:
            with self.subTest(role=agent["id"]):
                self.assertIs(True, agent["model-neutral"])
                self.assertFalse(
                    {"model", "deployment", "effort", "route-class"} & agent.keys()
                )
                if agent["id"] != "lead":
                    self.assertIn("do not recursively delegate", agent["restrictions"])
        self.assertEqual([], find_model_agnostic_violations(root))

    def test_lead_semantics_are_proportional_and_preserve_authority(self) -> None:
        lead = self._lead()
        responsibilities = lead["responsibilities"]
        for terms in (
            ("each engineering request", "scope", "risk", "ownership", "route class"),
            ("smallest useful role set", "trivial", "directly", "material value"),
            ("proactively delegate", "specialized", "materially improve"),
            ("delegate architecture", "ownership-boundary", "cross-package", "small"),
            ("before writable implementation", "matching available core specialist"),
            ("preserve the original scope and complexity", "small final diff", "final acceptance authority"),
            ("architecture or ownership decisions", "architect", "before implementation"),
            ("roles by purpose", "architect", "researcher", "steward", "validator"),
            ("each concrete delegated assignment", "classify", ".embraion/**", "host"),
            ("role", "access", "route class", "model selection", "independent"),
            ("parallelize", "independent writes", "serialize", "shared contracts"),
            ("fresh proportional validation", "project profiles", "pass", "fail", "skip", "infrastructure"),
            ("independent read-only reviewer", "completed substantial", "before final acceptance", "policy"),
            ("material findings", "fresh proportional validation", "re-review"),
            ("integrate", "final acceptance authority", "delivery responsibility"),
        ):
            with self.subTest(terms=terms):
                self._assert_semantic_clause(responsibilities, *terms)
        self._assert_semantic_clause(
            lead["restrictions"], "ceremony", "trivial", "material benefit"
        )
        self._assert_semantic_clause(
            lead["restrictions"], "small expected or final diff", "skip an available matching specialist", "cross-package"
        )
        self._assert_semantic_clause(
            lead["restrictions"], "missing", "historical", "fresh pass"
        )
        self._assert_semantic_clause(
            lead["restrictions"], "implementation owner", "independent reviewer"
        )

    def test_workflows_reference_canonical_lead_and_review_policy(self) -> None:
        root = framework_root()
        for name in ("engineering", "review"):
            text = (root / f"core/workflows/{name}.md").read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("../agents/lead.yaml", text)
                self.assertIn("../rules/review.md", text)
                self.assertIn("final acceptance", text)

    def test_codex_host_projection_requires_preimplementation_specialist_dispatch(self) -> None:
        text = (framework_root() / "adapters/codex/orchestration.md").read_text(encoding="utf-8").lower()
        for phrase in (
            "original nature and ownership of the problem",
            "before writable implementation",
            "matching available core specialist",
            "architect analyze",
            "before implementation",
            "small final diff does not retroactively reduce",
            "lead retains final acceptance authority",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_empty_project_agents_preserve_root_lead_and_core_specialists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="OrchestrationRegression")
            self.assertEqual({"agents": []}, read_yaml(project / ".embraion/agents.yaml"))
            install("codex", project)

            self.assertEqual(
                CORE_ROLES,
                {agent["id"] for agent in load_agents(framework_root(), project)},
            )
            self._assert_root_contract(self._config(project))
            profiles = project / ".codex/agents"
            self.assertEqual(SPECIALISTS, {path.stem for path in profiles.glob("*.toml")})
            self.assertFalse((profiles / "lead.toml").exists())
            for path in profiles.glob("*.toml"):
                profile = tomllib.loads(path.read_text(encoding="utf-8"))
                with self.subTest(role=path.stem):
                    self.assertNotIn("model", profile)
                    self.assertNotIn("model_reasoning_effort", profile)
                    self.assertIn("do not recursively delegate", profile["developer_instructions"])
            reviewer = tomllib.loads((profiles / "reviewer.toml").read_text(encoding="utf-8"))
            self.assertEqual("read-only", reviewer["sandbox_mode"])

    def test_project_agents_are_additive_without_replacing_orchestration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="AdditiveOrchestration")
            responsibility = "implement project-owned fixture behavior"
            write_yaml(project / ".embraion/agents.yaml", {
                "agents": [{
                    "id": "project-worker",
                    "extends": "worker",
                    "purpose": "Implement fixture-specific behavior.",
                    "access": "workspace-write",
                    "responsibilities": [responsibility],
                }],
            })
            install("codex", project)
            self._assert_root_contract(self._config(project))
            profiles = project / ".codex/agents"
            self.assertEqual(
                SPECIALISTS | {"project-worker"},
                {path.stem for path in profiles.glob("*.toml")},
            )
            profile = tomllib.loads((profiles / "project-worker.toml").read_text(encoding="utf-8"))
            self.assertEqual("workspace-write", profile["sandbox_mode"])
            self.assertIn(responsibility, profile["developer_instructions"])
            self.assertIn("do not recursively delegate", profile["developer_instructions"])
            self.assertNotIn("model", profile)

    def test_same_role_uses_assignment_route_and_project_owned_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="AssignmentRouting")
            selectors = {
                "bounded-read": "project-read-selector",
                "complex": "project-complex-selector",
            }
            write_yaml(project / ".embraion/routing.yaml", {
                "overrides": {"codex": {"routes": {
                    classification: {"model": selector}
                    for classification, selector in selectors.items()
                }}},
            })
            for classification, selector in selectors.items():
                result = route(
                    "codex", classification, "PUBLIC", role="architect",
                    access="inspect", project=project,
                )
                with self.subTest(assignment_route=classification):
                    self.assertEqual("architect", result["role"])
                    self.assertEqual(classification, result["route"])
                    self.assertEqual(selector, result["model"])
            install("codex", project)
            config = self._config(project)
            self._assert_root_contract(config)
            self.assertNotIn("model", config)
            self.assertNotIn("default_subagent_model", config["agents"])
            self.assertNotIn("default_subagent_reasoning_effort", config["agents"])
            for selector in selectors.values():
                self.assertNotIn(selector, config["developer_instructions"])
                for profile in (project / ".codex/agents").glob("*.toml"):
                    self.assertNotIn(selector, profile.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
