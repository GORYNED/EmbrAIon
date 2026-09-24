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
from embraion.validation import collect_issues, find_model_agnostic_violations


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
            data = read_yaml(manifest)
            data["routing"] = {
                "overrides": {
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
            }
            write_yaml(manifest, data)

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
