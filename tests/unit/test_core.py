from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion import __version__
from embraion.common import framework_root, read_json, read_yaml, write_yaml
from embraion.evals import evaluate_case
from embraion.project import init_project, sync
from embraion.runtime import route
from embraion.security import collect_findings, redact_text
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
        with tempfile.TemporaryDirectory() as temporary:
            result = route("codex", "substantial", "CONFIDENTIAL", project=Path(temporary))
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

    def test_security_scanner_detects_prefixed_tokens_and_machine_paths(self) -> None:
        tokens = {
            "github": "gh" + "p_" + "A1b2" * 9,
            "fine-grained": "github" + "_pat_" + "A1b2_C3d4" * 9,
            "cloud": "AK" + "IA" + "ABCDEFGHIJ234567",
            "model": "s" + "k-ant-" + "a1B2c3D4" * 5,
            "maps": "AI" + "za" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, token in tokens.items():
                (root / f"{name}.md").write_text(f"Use {token} here.", encoding="utf-8")
            (root / "local.md").write_text("Logs are in C:" + "\\Users\\owner\\Documents\\", encoding="utf-8")
            (root / "forward.md").write_text("Data in C:/" + "Users/owner/AppData/", encoding="utf-8")
            (root / "placeholder.md").write_text(
                "See /home/runner/work, /Users/<name>/, /Users/Shared/, C:" + "\\Users\\%USERNAME%\\ and "
                "task-abcdefghijklmnopqrstuvwxyz0123456789, s" + "k-build-cache-key-for-the-release-pipeline-x, "
                "xo" + "xb-your-bot-token-goes-here, github" + "_pat_placeholder_value_in_the_documentation_page_example_text.",
                encoding="utf-8",
            )
            findings = {(item["path"], item["category"], item["severity"]) for item in collect_findings(root)}
        self.assertEqual(
            {(f"{name}.md", "access-token", "high") for name in tokens}
            | {("local.md", "machine-path", "medium"), ("forward.md", "machine-path", "medium")},
            findings,
        )
        redacted = redact_text("token " + tokens["github"] + " and " + tokens["cloud"])
        self.assertEqual("token <REDACTED:access-token> and <REDACTED:access-token>", redacted)

    def test_security_scanner_all_files_checks_source_for_precise_patterns_only(self) -> None:
        token = "gh" + "p_" + "A1b2" * 9
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "Client.cs").write_text(f'var t = "{token}";', encoding="utf-8")
            (root / "src" / "Bridge.mm").write_text('NSString *p = @"/Users/' + 'owner/tmp/";', encoding="utf-8")
            (root / "src" / "Key.uxml").write_text("-----BEGIN " + "PRIVATE KEY-----", encoding="utf-8")
            # Ordinary code assignments must not trip the keyword heuristic.
            (root / "src" / "Session.cs").write_text(
                "to" + "ken = cancellationTokenSource.Token;", encoding="utf-8"
            )
            (root / "src" / "Image.bin").write_bytes(b"\x00" + token.encode())
            (root / "src" / "Large.asset").write_text(token + "x" * (2 * 1024 * 1024), encoding="utf-8")
            (root / "Library").mkdir()
            (root / "Library" / "Cache.cs").write_text(token, encoding="utf-8")
            (root / "notes.md").write_text("api_key=" + "b" * 24, encoding="utf-8")

            default = {(item["path"], item["category"]) for item in collect_findings(root)}
            everything = {
                (item["path"].replace("\\", "/"), item["category"])
                for item in collect_findings(root, all_files=True)
            }
        self.assertEqual({("notes.md", "api-key")}, default)
        self.assertEqual(
            {
                ("notes.md", "api-key"),
                ("src/Client.cs", "access-token"),
                ("src/Bridge.mm", "machine-path"),
                ("src/Key.uxml", "private-key"),
            },
            everything,
        )

    def test_security_scanner_all_files_skips_git_ignored_files(self) -> None:
        import shutil
        import subprocess

        if shutil.which("git") is None:
            self.skipTest("git is not available")
        token = "gh" + "p_" + "A1b2" * 9
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("Temp/\n", encoding="utf-8")
            (root / "Temp").mkdir()
            (root / "Temp" / "Build.cs").write_text(token, encoding="utf-8")
            (root / "Tracked.cs").write_text(token, encoding="utf-8")
            findings = {item["path"] for item in collect_findings(root, all_files=True)}
        self.assertEqual({"Tracked.cs"}, findings)

    def test_security_scanner_ignores_public_key_token_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "settings.json").write_text(
                "PublicKeyToken=b77a5c561934e089",
                encoding="utf-8",
            )
            findings = collect_findings(root)
            self.assertFalse(any(item["severity"] == "high" for item in findings))

    def test_security_scanner_flags_undeclared_legacy_data_class(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = "COMPANY" + "_SECRET"
            (root / "policy.txt").write_text(
                "data-class=" + legacy,
                encoding="utf-8",
            )
            findings = collect_findings(root)
            self.assertTrue(
                any(
                    item["category"] == "policy-drift"
                    and item["severity"] == "medium"
                    for item in findings
                )
            )

    def test_security_scanner_accepts_declared_confidential_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / ".embraion" / "execution.yaml"
            config.parent.mkdir(parents=True)
            legacy = "COMPANY" + "_SECRET"
            write_yaml(
                config,
                {
                    "schemaVersion": 1,
                    "bindings": {
                        "project-api": {
                            "adapter": "example",
                            "selector": "example/model",
                            "sourceIds": ["Project"],
                            "trustLevels": ["verified"],
                            "dataClassAliases": {
                                "CONFIDENTIAL": legacy
                            },
                        }
                    },
                },
            )
            (root / "policy.txt").write_text(
                "data-class=" + legacy,
                encoding="utf-8",
            )
            findings = collect_findings(root)
            self.assertFalse(
                any(item["category"] == "policy-drift" for item in findings)
            )

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

    def test_cross_package_orchestration_eval_covers_solo_execution_failure(self) -> None:
        root = framework_root()
        case = read_yaml(root / "evals/cases/cross-package-orchestration.yaml")
        passed_record = read_json(root / "tests/fixtures/evals/cross-package-orchestration.json")
        passed, failures = evaluate_case(case, passed_record)
        self.assertTrue(passed, failures)

        # A successful process exit and a small patch cannot substitute for
        # required specialist dispatch before writable implementation.
        blocked_record = {"process-exit-code": 0}
        passed, failures = evaluate_case(case, blocked_record)
        self.assertFalse(passed)
        self.assertTrue(any("selected-capabilities" in failure for failure in failures))
        self.assertTrue(any("task-complete" in failure for failure in failures))
        self.assertTrue(any("final-acceptance-owner" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
