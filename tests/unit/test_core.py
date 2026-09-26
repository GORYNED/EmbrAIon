from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion import __version__
from embraion.common import framework_root, read_yaml, write_yaml
from embraion.evals import evaluate_case
from embraion.project import init_project, sync
from embraion.runtime import route
from embraion.security import collect_findings
from embraion.validation import (
    collect_issues,
    find_model_agnostic_semantic_violations,
    find_model_agnostic_violations,
)


class CoreTests(unittest.TestCase):
    def test_framework_validation_is_clean(self) -> None:
        issues = collect_issues(framework_root())
        errors = [item for item in issues if item["severity"] == "error"]
        self.assertEqual([], errors)

    def test_version_contract_is_aligned(self) -> None:
        root = framework_root()
        framework = read_yaml(root / "framework.yaml") or {}
        with (root / "pyproject.toml").open("rb") as handle:
            package = tomllib.load(handle)

        self.assertEqual(__version__, str(framework["version"]))
        self.assertEqual(__version__, str(package["project"]["version"]))

    def test_project_templates_track_framework_version(self) -> None:
        root = framework_root()
        framework = read_yaml(root / "framework.yaml") or {}
        expected = str(framework["version"])

        manifests = [
            root / "templates/project-overlay/.embraion/project.yaml",
            *sorted((root / "examples").glob("*/.embraion/project.yaml")),
        ]

        self.assertGreaterEqual(len(manifests), 4)
        for manifest in manifests:
            with self.subTest(manifest=manifest):
                data = read_yaml(manifest) or {}
                self.assertEqual(
                    "GORYNED/EmbrAIon",
                    data["framework"]["repository"],
                )
                self.assertEqual(expected, str(data["framework"]["version"]))

    def test_default_route_uses_host_default_without_model_catalog(self) -> None:
        result = route("codex", "substantial", "CONFIDENTIAL")
        self.assertEqual("host-default", result["resolution"])
        self.assertIsNone(result["model"])
        self.assertIsNone(result["effort"])
        self.assertEqual({}, result["options"])

    def test_project_route_override_accepts_arbitrary_host_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            routing_path = manifest.with_name("routing.yaml")
            routing = read_yaml(routing_path)
            routing["overrides"] = {
                "codex": {
                    "routes": {
                        "substantial": {
                            "model": "future-model",
                            "effort": "deep",
                        }
                    },
                    "roles": {
                        "reviewer": {
                            "model": "future-review-model",
                            "options": {"thinking": "maximum"},
                        }
                    },
                }
            }
            write_yaml(routing_path, routing)

            routed = route(
                "codex",
                "substantial",
                "PRIVATE",
                project=project,
            )
            self.assertEqual("project-override", routed["resolution"])
            self.assertEqual("future-model", routed["model"])
            self.assertEqual("deep", routed["effort"])

            reviewed = route(
                "codex",
                "substantial",
                "PRIVATE",
                role="reviewer",
                project=project,
            )
            self.assertEqual("future-review-model", reviewed["model"])
            self.assertEqual("deep", reviewed["effort"])
            self.assertEqual({"thinking": "maximum"}, reviewed["options"])

    def test_project_deployment_registry_resolves_route_and_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="DeploymentConsumer")
            deployments_path = manifest.with_name("deployments.yaml")
            routing_path = manifest.with_name("routing.yaml")

            write_yaml(
                deployments_path,
                {
                    "providers": {"example": {"display-name": "Example Provider"}},
                    "deployments": {
                        "primary": {
                            "host": "codex",
                            "provider": "example",
                            "model": "future-primary",
                            "efforts": ["medium", "high"],
                            "default-effort": "medium",
                            "billing": {"mode": "subscription"},
                            "capabilities": {
                                "data-classes": ["PRIVATE"],
                                "access-modes": ["read-only", "workspace-write"],
                                "roles": ["worker"],
                                "task-classes": ["substantial"],
                            },
                            "options": {"temperature": 0},
                        },
                        "fallback": {
                            "host": "codex",
                            "provider": "example",
                            "model": "future-fallback",
                            "efforts": ["low"],
                            "default-effort": "low",
                            "billing": {"mode": "api"},
                            "capabilities": {
                                "data-classes": ["PRIVATE"],
                                "access-modes": ["workspace-write"],
                                "roles": ["worker"],
                                "task-classes": ["substantial"],
                            },
                        },
                    },
                },
            )
            write_yaml(
                routing_path,
                {
                    "overrides": {
                        "codex": {
                            "routes": {
                                "substantial": {
                                    "deployment": "primary",
                                    "effort": "high",
                                    "options": {"thinking": "deep"},
                                    "fallbacks": [
                                        {"deployment": "fallback", "effort": "low"}
                                    ],
                                }
                            }
                        }
                    }
                },
            )

            routed = route(
                "codex",
                "substantial",
                "PRIVATE",
                role="worker",
                access="write",
                project=project,
            )
            self.assertEqual("project-deployment", routed["resolution"])
            self.assertEqual("primary", routed["deployment"])
            self.assertEqual("example", routed["provider"])
            self.assertEqual("future-primary", routed["model"])
            self.assertEqual("high", routed["effort"])
            self.assertEqual(
                {"temperature": 0, "thinking": "deep"},
                routed["options"],
            )
            self.assertEqual(1, len(routed["fallbacks"]))
            self.assertEqual("future-fallback", routed["fallbacks"][0]["model"])
            self.assertEqual("low", routed["fallbacks"][0]["effort"])

    def test_project_deployment_registry_fails_closed_on_invalid_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="DeploymentBoundary")
            deployments_path = manifest.with_name("deployments.yaml")
            routing_path = manifest.with_name("routing.yaml")

            write_yaml(
                deployments_path,
                {
                    "providers": {},
                    "deployments": {
                        "read-only": {
                            "host": "codex",
                            "model": "future-model",
                            "efforts": ["low"],
                            "capabilities": {
                                "data-classes": ["PUBLIC"],
                                "access-modes": ["read-only"],
                            },
                        }
                    },
                },
            )
            write_yaml(
                routing_path,
                {
                    "overrides": {
                        "codex": {
                            "routes": {
                                "substantial": {
                                    "deployment": "read-only",
                                    "effort": "high",
                                }
                            }
                        }
                    }
                },
            )

            with self.assertRaisesRegex(RuntimeError, "does not support effort"):
                route(
                    "codex",
                    "substantial",
                    "PUBLIC",
                    access="review",
                    project=project,
                )

            routing = read_yaml(routing_path)
            routing["overrides"]["codex"]["routes"]["substantial"] = {
                "deployment": "missing"
            }
            write_yaml(routing_path, routing)
            with self.assertRaisesRegex(RuntimeError, "Unknown project deployment"):
                route("codex", "substantial", "PUBLIC", project=project)

    def test_model_agnostic_invariant_rejects_framework_model_registries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_catalog = root / "adapters/codex/models.yaml"
            route_map = root / "adapters/providers/example/routes.json"
            harmless_routes = root / "adapters/portable/routes.yaml"
            model_schema = root / "schemas/model.schema.json"

            for path in (model_catalog, route_map, harmless_routes, model_schema):
                path.parent.mkdir(parents=True, exist_ok=True)

            model_catalog.write_text("models: []\n", encoding="utf-8")
            route_map.write_text(
                '{"routes":{"complex":{"model":"hardcoded-model"}}}\n',
                encoding="utf-8",
            )
            harmless_routes.write_text(
                "routes:\n  complex:\n    transport: host-default\n",
                encoding="utf-8",
            )
            model_schema.write_text("{}\n", encoding="utf-8")

            violations = {
                path.relative_to(root).as_posix()
                for path in find_model_agnostic_violations(root)
            }
            self.assertEqual(
                {
                    "adapters/codex/models.yaml",
                    "adapters/providers/example/routes.json",
                    "schemas/model.schema.json",
                },
                violations,
            )

    def test_model_agnostic_semantic_invariant_rejects_legacy_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stale_workflow = root / "core/workflows/engineering.md"
            stale_routing_path = root / "core/routing/README.md"
            stale_route_class = root / "docs/routing.md"
            stale_nested_path = root / "localization/docs/ru/model-routing.md"
            allowed_version_pin = root / "docs/release-process.md"
            allowed_fallback = root / "core/routing/fallback.yaml"
            allowed_modular_summary = root / "README.md"

            for path in (
                stale_workflow,
                stale_routing_path,
                stale_route_class,
                stale_nested_path,
                allowed_version_pin,
                allowed_fallback,
                allowed_modular_summary,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)

            stale_workflow.write_text(
                "Lead selects job-like agents and explicit model/effort routes.\n",
                encoding="utf-8",
            )
            stale_routing_path.write_text(
                "Store model overrides in .embraion/project.yaml.\n",
                encoding="utf-8",
            )
            stale_route_class.write_text(
                "Use strong-high for difficult work.\n",
                encoding="utf-8",
            )
            stale_nested_path.write_text(
                "Write project values under routing.overrides.\n",
                encoding="utf-8",
            )
            allowed_version_pin.write_text(
                "Pin framework.version in .embraion/project.yaml.\n",
                encoding="utf-8",
            )
            allowed_fallback.write_text(
                "model-to-model fallback is owned by the execution host\n",
                encoding="utf-8",
            )
            allowed_modular_summary.write_text(
                ".embraion/project.yaml stores identity; "
                ".embraion/routing.yaml stores model overrides.\n",
                encoding="utf-8",
            )

            violations = find_model_agnostic_semantic_violations(root)
            paths = {
                item["path"].relative_to(root).as_posix()
                for item in violations
            }
            self.assertEqual(
                {
                    "core/workflows/engineering.md",
                    "core/routing/README.md",
                    "docs/routing.md",
                    "localization/docs/ru/model-routing.md",
                },
                paths,
            )

    def test_sync_generates_all_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            generated = sync("all", output, force=True)
            self.assertEqual(4, len(generated))
            codex_config = output / "codex/.codex/config.toml"
            self.assertTrue(codex_config.is_file())
            config_text = codex_config.read_text(encoding="utf-8")
            self.assertNotIn("default_subagent_model", config_text)
            self.assertNotIn("default_subagent_reasoning_effort", config_text)
            self.assertTrue((output / "copilot/.github/agents/reviewer.agent.md").is_file())
            self.assertTrue((output / "claude-code/.claude/agents/reviewer.md").is_file())
            self.assertTrue((output / "portable/embraion/plugin.json").is_file())

    def test_security_scanner_detects_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = "a" * 24
            (root / "bad.txt").write_text(
                "api_key=" + secret,
                encoding="utf-8",
            )
            findings = collect_findings(root)
            self.assertTrue(any(item["severity"] == "high" for item in findings))

    def test_eval_checks_are_deterministic(self) -> None:
        case = {
            "checks": [
                {
                    "type": "changed-paths-within",
                    "field": "changed-paths",
                    "patterns-field": "owned-paths",
                }
            ]
        }
        passed, failures = evaluate_case(
            case,
            {
                "changed-paths": ["src/owned/a.cs"],
                "owned-paths": ["src/owned/**"],
            },
        )
        self.assertTrue(passed)
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
