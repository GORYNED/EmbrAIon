from __future__ import annotations

import hashlib
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from embraion import __version__
from embraion.common import read_json, read_yaml, write_json, write_yaml
from embraion.context import build_context
from embraion.contracts import (
    PROJECT_CONTRACT_SLOT_NAMES,
    project_contract_status,
)
from embraion.policy import effective_policy, read_knowledge_config
from embraion.project import (
    _host_access_projection,
    _projection_recovery_path,
    init_project,
    install,
    normalize_project_config,
    projection_is_verified,
    projection_plan,
    update_project,
)


class ProjectionPolicyTests(unittest.TestCase):
    def test_init_creates_project_policy_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            policy = effective_policy(project)
            routing = read_yaml(project / ".embraion/routing.yaml")
            knowledge = read_yaml(project / ".embraion/knowledge.yaml")
            project_policy = read_yaml(project / ".embraion/policy.yaml")
            validation = read_yaml(project / ".embraion/validation.yaml")
            agents = read_yaml(project / ".embraion/agents.yaml")
            project_manifest = read_yaml(project / ".embraion/project.yaml")
            self.assertEqual({"overrides": {}}, routing)
            self.assertEqual(
                set(PROJECT_CONTRACT_SLOT_NAMES),
                set(knowledge["slots"]),
            )
            self.assertTrue(
                all(value is None for value in knowledge["slots"].values())
            )
            self.assertEqual(
                {"fast": [], "affected": [], "full": []},
                validation["profiles"],
            )
            self.assertEqual({"agents": []}, agents)
            self.assertEqual("PRIVATE", project_policy["privacy"]["default-class"])
            self.assertFalse(project_policy["enforcement"]["enabled"])
            self.assertEqual(
                "affected",
                project_policy["enforcement"]["validation-profile"],
            )
            self.assertTrue(project_policy["review"]["substantial-required"])
            self.assertEqual([], project_policy["sources"]["protected"])
            for key in (
                "routing",
                "knowledge",
                "sources",
                "review",
                "privacy",
                "validation",
                "agents",
            ):
                self.assertNotIn(key, project_manifest)
            self.assertEqual("PRIVATE", policy["privacy"]["default-class"])
            self.assertTrue(policy["review"]["substantial-required"])
            self.assertEqual([], policy["sources"]["protected"])
            local_ignore = (project / ".embraion/.gitignore").read_text(
                encoding="utf-8"
            )
            self.assertIn("state/", local_ignore)
            self.assertIn("cache/", local_ignore)

    def test_update_adds_missing_defaults_without_overwriting_user_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")

            policy_path = project / ".embraion" / "policy.yaml"
            policy = read_yaml(policy_path)
            policy.pop("enforcement")
            policy["privacy"]["default-class"] = "CONFIDENTIAL"
            policy["review"]["substantial-required"] = False
            policy["sources"]["canonical"] = ["src/**"]
            write_yaml(policy_path, policy)

            validation_path = project / ".embraion" / "validation.yaml"
            validation = read_yaml(validation_path)
            validation["profiles"]["fast"] = ["python -m unittest"]
            write_yaml(validation_path, validation)

            routing_path = project / ".embraion" / "routing.yaml"
            routing = read_yaml(routing_path)
            routing["overrides"] = {
                "codex": {
                    "routes": {
                        "ordinary": {
                            "model": "host-owned-selector",
                        }
                    }
                }
            }
            write_yaml(routing_path, routing)

            knowledge_path = project / ".embraion" / "knowledge.yaml"
            write_yaml(
                knowledge_path,
                {"legacy-project": "knowledge/project.md"},
            )

            install("codex", project)
            projection_path = project / ".codex" / "config.toml"
            projection_before = projection_path.read_bytes()
            state_path = project / ".embraion/state/projections/codex.json"
            state_before = state_path.read_bytes()

            project_data = read_yaml(manifest)
            project_data["framework"]["version"] = "0.8.1"
            write_yaml(manifest, project_data)

            previous, current = update_project(project, version=__version__)
            self.assertEqual("0.8.1", str(previous))
            self.assertEqual(__version__, current)

            updated_policy = read_yaml(policy_path)
            self.assertEqual(
                {
                    "enabled": False,
                    "validation-profile": "affected",
                    "require-review": False,
                },
                updated_policy["enforcement"],
            )
            self.assertEqual(
                "CONFIDENTIAL",
                updated_policy["privacy"]["default-class"],
            )
            self.assertFalse(updated_policy["review"]["substantial-required"])
            self.assertEqual(
                ["src/**"],
                updated_policy["sources"]["canonical"],
            )

            self.assertEqual(
                ["python -m unittest"],
                read_yaml(validation_path)["profiles"]["fast"],
            )
            self.assertEqual(
                "host-owned-selector",
                read_yaml(routing_path)["overrides"]["codex"]["routes"][
                    "ordinary"
                ]["model"],
            )
            self.assertEqual(
                __version__,
                str(read_yaml(manifest)["framework"]["version"]),
            )
            updated_knowledge = read_yaml(knowledge_path)
            self.assertEqual(
                "knowledge/project.md",
                updated_knowledge["legacy-project"],
            )
            self.assertEqual(
                set(PROJECT_CONTRACT_SLOT_NAMES),
                set(updated_knowledge["slots"]),
            )

            self.assertEqual(projection_before, projection_path.read_bytes())
            self.assertEqual(state_before, state_path.read_bytes())

    def test_update_validates_every_candidate_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            policy_path = project / ".embraion" / "policy.yaml"
            validation_path = project / ".embraion" / "validation.yaml"

            project_data = read_yaml(manifest)
            project_data["framework"]["version"] = "0.8.1"
            write_yaml(manifest, project_data)

            policy = read_yaml(policy_path)
            policy.pop("enforcement")
            write_yaml(policy_path, policy)

            validation = read_yaml(validation_path)
            validation["profiles"]["fast"] = "not-a-command-list"
            write_yaml(validation_path, validation)

            manifest_before = manifest.read_bytes()
            policy_before = policy_path.read_bytes()

            with self.assertRaisesRegex(
                RuntimeError,
                "Cannot safely update",
            ):
                update_project(project, version=__version__)

            self.assertEqual(manifest_before, manifest.read_bytes())
            self.assertEqual(policy_before, policy_path.read_bytes())
            self.assertNotIn("enforcement", read_yaml(policy_path))

    def test_update_refuses_incomplete_legacy_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            (project / ".embraion" / "policy.yaml").unlink()

            with self.assertRaisesRegex(
                RuntimeError,
                "incomplete or legacy layout",
            ):
                normalize_project_config(project, version=__version__)

    def test_update_refuses_non_launcher_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            before = manifest.read_bytes()

            with self.assertRaisesRegex(
                RuntimeError,
                "installed EmbrAIon launcher version",
            ):
                update_project(project, version="not-a-release")

            self.assertEqual(before, manifest.read_bytes())

    def test_update_rejects_non_mapping_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            policy_path = project / ".embraion" / "policy.yaml"
            policy_path.write_text("[]\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Invalid project configuration mapping",
            ):
                normalize_project_config(project, version=__version__)

    def test_init_preserves_existing_local_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            local_ignore = project / ".embraion/.gitignore"
            local_ignore.parent.mkdir(parents=True)
            local_ignore.write_text("custom-local-rule/\n", encoding="utf-8")

            init_project(project, name="Consumer")
            self.assertEqual(
                "custom-local-rule/\n",
                local_ignore.read_text(encoding="utf-8"),
            )

    def test_host_projection_includes_project_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)
            install("copilot", project)
            install("claude-code", project)

            self.assertTrue((project / ".agents/skills/review/SKILL.md").is_file())
            self.assertTrue((project / ".github/skills/review/SKILL.md").is_file())
            self.assertTrue((project / ".claude/skills/review/SKILL.md").is_file())

    def test_execution_host_access_contract_and_core_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            for host in ("codex", "copilot", "claude-code"):
                install(
                    host,
                    project,
                    components=["agents", "skills"],
                )

            access_by_agent = {
                "analyst": "read-only",
                "architect": "read-only",
                "researcher": "read-only",
                "reviewer": "read-only",
                "steward": "workspace-write",
                "validator": "workspace-write",
                "worker": "workspace-write",
            }
            expected_agents = set(access_by_agent)
            expected_skills = {
                "debugging",
                "implementation",
                "planning",
                "research",
                "review",
                "routing-configuration",
                "validation",
                "verification",
            }

            codex_root = project / ".codex" / "agents"
            self.assertEqual(
                {f"{agent_id}.toml" for agent_id in expected_agents},
                {path.name for path in codex_root.glob("*.toml")},
            )
            self.assertFalse((codex_root / "lead.toml").exists())
            for agent_id, access in access_by_agent.items():
                text = (codex_root / f"{agent_id}.toml").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f'sandbox_mode = "{access}"', text)
                self.assertIn("do not recursively delegate", text)
                self.assertNotIn("model =", text)

            copilot_tools = {
                "read-only": ["read", "search"],
                "workspace-write": ["read", "search", "edit", "execute"],
            }
            copilot_root = project / ".github" / "agents"
            self.assertEqual(
                {f"{agent_id}.agent.md" for agent_id in expected_agents},
                {path.name for path in copilot_root.glob("*.agent.md")},
            )
            self.assertFalse((copilot_root / "lead.agent.md").exists())
            for agent_id, access in access_by_agent.items():
                profile = copilot_root / f"{agent_id}.agent.md"
                profile_text = profile.read_text(encoding="utf-8")
                frontmatter = yaml.safe_load(
                    profile_text.split("---", 2)[1]
                )
                self.assertIn("do not recursively delegate", profile_text)
                self.assertEqual(copilot_tools[access], frontmatter["tools"])
                self.assertIs(True, frontmatter["include-custom-instructions"])
                self.assertIn("name", frontmatter)
                self.assertIn("description", frontmatter)
                self.assertNotIn("model", frontmatter)

            claude_tools = {
                "read-only": ["Read", "Grep", "Glob"],
                "workspace-write": [
                    "Read",
                    "Grep",
                    "Glob",
                    "Write",
                    "Edit",
                    "Bash",
                ],
            }
            claude_root = project / ".claude" / "agents"
            self.assertEqual(
                {f"{agent_id}.md" for agent_id in expected_agents},
                {path.name for path in claude_root.glob("*.md")},
            )
            self.assertFalse((claude_root / "lead.md").exists())
            for agent_id, access in access_by_agent.items():
                profile = claude_root / f"{agent_id}.md"
                profile_text = profile.read_text(encoding="utf-8")
                frontmatter = yaml.safe_load(
                    profile_text.split("---", 2)[1]
                )
                self.assertIn("do not recursively delegate", profile_text)
                self.assertEqual(claude_tools[access], frontmatter["tools"])
                self.assertNotIn("include-custom-instructions", frontmatter)
                self.assertIn("name", frontmatter)
                self.assertIn("description", frontmatter)
                self.assertNotIn("model", frontmatter)

            for skills_root in (
                project / ".agents" / "skills",
                project / ".github" / "skills",
                project / ".claude" / "skills",
            ):
                self.assertEqual(
                    expected_skills,
                    {
                        path.parent.name
                        for path in skills_root.glob("*/SKILL.md")
                    },
                )

    def test_host_access_projection_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "unsupported access mapping",
        ):
            _host_access_projection(
                "copilot",
                {"id": "unsafe", "access": "unrestricted"},
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "no enforceable agent access projection",
        ):
            _host_access_projection(
                "portable",
                {"id": "worker", "access": "workspace-write"},
            )

    def test_project_agents_project_to_hosts_with_delegation_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            agents_path = project / ".embraion" / "agents.yaml"
            write_yaml(
                agents_path,
                {
                    "agents": [
                        {
                            "id": "domain-specialist",
                            "title": "Domain Specialist",
                            "extends": "reviewer",
                            "purpose": "Review project-specific domain behavior.",
                            "access": "read-only",
                            "responsibilities": [
                                "focus on project-specific domain contracts"
                            ],
                            "restrictions": [
                                "do not modify project files"
                            ],
                        },
                        {
                            "id": "standalone-specialist",
                            "title": "Standalone Specialist",
                            "purpose": "Analyze project-specific behavior.",
                            "access": "read-only",
                            "responsibilities": [
                                "analyze a bounded project concern"
                            ],
                        },
                    ]
                },
            )

            install("codex", project)
            install("copilot", project)
            install("claude-code", project)

            codex = project / ".codex" / "agents" / "domain-specialist.toml"
            copilot = (
                project
                / ".github"
                / "agents"
                / "domain-specialist.agent.md"
            )
            claude = project / ".claude" / "agents" / "domain-specialist.md"

            self.assertTrue(codex.is_file())
            self.assertTrue(copilot.is_file())
            self.assertTrue(claude.is_file())

            codex_text = codex.read_text(encoding="utf-8")
            self.assertIn('sandbox_mode = "read-only"', codex_text)
            self.assertIn(
                "review intent, diff, contracts, evidence",
                codex_text,
            )
            self.assertIn(
                "focus on project-specific domain contracts",
                codex_text,
            )
            self.assertIn("do not recursively delegate", codex_text)
            self.assertIn(
                "Review project-specific domain behavior.",
                copilot.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Review project-specific domain behavior.",
                claude.read_text(encoding="utf-8"),
            )
            copilot_frontmatter = yaml.safe_load(
                copilot.read_text(encoding="utf-8").split("---", 2)[1]
            )
            claude_frontmatter = yaml.safe_load(
                claude.read_text(encoding="utf-8").split("---", 2)[1]
            )
            self.assertEqual(
                ["read", "search"],
                copilot_frontmatter["tools"],
            )
            self.assertIs(
                True,
                copilot_frontmatter["include-custom-instructions"],
            )
            self.assertEqual(
                ["Read", "Grep", "Glob"],
                claude_frontmatter["tools"],
            )
            self.assertNotIn(
                "include-custom-instructions",
                claude_frontmatter,
            )

            standalone_paths = (
                project / ".codex" / "agents" / "standalone-specialist.toml",
                project / ".github" / "agents" / "standalone-specialist.agent.md",
                project / ".claude" / "agents" / "standalone-specialist.md",
            )
            for standalone in standalone_paths:
                standalone_text = standalone.read_text(encoding="utf-8")
                self.assertIn("do not recursively delegate", standalone_text)
                self.assertIn(
                    "analyze a bounded project concern",
                    standalone_text,
                )

            agents = read_yaml(agents_path)
            agents["agents"][0]["title"] = "Domain: Specialist"
            write_yaml(agents_path, agents)
            install("copilot", project, force=True)
            frontmatter = yaml.safe_load(
                copilot.read_text(encoding="utf-8").split("---", 2)[1]
            )
            self.assertEqual("Domain: Specialist", frontmatter["name"])
            self.assertEqual(["read", "search"], frontmatter["tools"])
            self.assertIs(True, frontmatter["include-custom-instructions"])

    def test_project_agent_cannot_shadow_or_widen_core_role(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            agents_path = project / ".embraion" / "agents.yaml"

            write_yaml(
                agents_path,
                {
                    "agents": [
                        {
                            "id": "reviewer",
                            "purpose": "Shadow reviewer.",
                            "access": "read-only",
                            "responsibilities": ["shadow"],
                        }
                    ]
                },
            )
            with self.assertRaisesRegex(RuntimeError, "conflicts with a Core agent"):
                projection_plan("codex", project)

            write_yaml(
                agents_path,
                {
                    "agents": [
                        {
                            "id": "unsafe-reviewer",
                            "extends": "reviewer",
                            "purpose": "Attempt to widen reviewer access.",
                            "access": "workspace-write",
                            "responsibilities": ["change reviewed files"],
                        }
                    ]
                },
            )
            with self.assertRaisesRegex(RuntimeError, "must preserve access"):
                projection_plan("codex", project)

    def test_selective_projection_preserves_existing_host_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")

            existing = project / ".codex/config.toml"
            existing.parent.mkdir(parents=True)
            existing.write_text("[project]\ncustom = true\n", encoding="utf-8")

            plan = projection_plan(
                "codex",
                project,
                components=["skills"],
            )
            self.assertEqual(["skills"], plan["components"])
            self.assertEqual([], plan["conflict"])

            installed = install(
                "codex",
                project,
                components=["skills"],
            )
            self.assertEqual(["skills"], installed["components"])
            self.assertEqual(
                "[project]\ncustom = true\n",
                existing.read_text(encoding="utf-8"),
            )
            self.assertFalse((project / ".codex/agents/reviewer.toml").exists())
            self.assertTrue((project / ".agents/skills/review/SKILL.md").is_file())

            full = projection_plan("codex", project)
            self.assertIn(".codex/config.toml", full["conflict"])
            self.assertIn(
                ".agents/skills/review/SKILL.md",
                full["unchanged"],
            )

    def test_selective_projection_does_not_orphan_unselected_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            selective = projection_plan(
                "codex",
                project,
                components=["skills"],
            )
            self.assertEqual([], selective["obsolete-owned"])
            self.assertEqual([], selective["obsolete-modified"])

            install("codex", project, components=["skills"])
            state = read_json(
                project / ".embraion/state/projections/codex.json"
            )
            self.assertIn(".codex/config.toml", state["files"])
            self.assertIn(".codex/agents/reviewer.toml", state["files"])
            self.assertEqual(
                ["agents", "config", "skills"],
                state["managed-components"],
            )

    def test_selective_install_infers_legacy_managed_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            state_path = project / ".embraion/state/projections/codex.json"
            state = read_json(state_path)
            state.pop("managed-components", None)
            write_json(state_path, state)

            install("codex", project, components=["skills"])
            upgraded = read_json(state_path)
            self.assertEqual(
                ["agents", "config", "skills"],
                upgraded["managed-components"],
            )

    def test_invalid_projection_component_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            with self.assertRaises(RuntimeError):
                projection_plan(
                    "copilot",
                    project,
                    components=["config"],
                )

    def test_update_recovers_exact_prior_projection_in_fresh_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            project_data = read_yaml(manifest)
            project_data["framework"]["version"] = "0.9.9"
            write_yaml(manifest, project_data)

            old_skill = project / ".github/skills/review/SKILL.md"
            old_skill.parent.mkdir(parents=True)
            old_skill.write_text("prior generated skill\n", encoding="utf-8")

            def fake_generate(
                runtime_python: Path,
                runtime_root: Path,
                host: str,
                output: Path,
                consumer: Path,
            ) -> None:
                self.assertEqual("copilot", host)
                generated = output / ".github/skills/review/SKILL.md"
                generated.parent.mkdir(parents=True)
                generated.write_text(
                    "prior generated skill\n",
                    encoding="utf-8",
                )

            with (
                patch(
                    "embraion.project.ensure_cached_runtime",
                    return_value=SimpleNamespace(
                        python=Path("previous-python"),
                        framework_root=Path("previous-framework"),
                    ),
                ),
                patch(
                    "embraion.project._generate_host_with_cached_runtime",
                    side_effect=fake_generate,
                ),
            ):
                previous, current = update_project(
                    project,
                    version=__version__,
                )

            self.assertEqual("0.9.9", previous)
            self.assertEqual(__version__, current)

            recovery_path = _projection_recovery_path(project, "copilot")
            self.assertTrue(recovery_path.is_file())
            recovery = read_json(recovery_path)
            relative = ".github/skills/review/SKILL.md"
            self.assertEqual("0.9.9", recovery["source-framework-version"])
            self.assertEqual(__version__, recovery["target-framework-version"])
            self.assertIn(relative, recovery["files"])

            plan = projection_plan(
                "copilot",
                project,
                components=["skills"],
            )
            self.assertIn(relative, plan["update"])
            self.assertNotIn(relative, plan["conflict"])
            self.assertEqual(
                "0.9.9",
                plan["ownership-recovery"]["source-framework-version"],
            )

            installed = install(
                "copilot",
                project,
                components=["skills"],
            )
            self.assertIn(relative, installed["update"])
            self.assertFalse(recovery_path.exists())

            state = read_json(
                project / ".embraion/state/projections/copilot.json"
            )
            self.assertIn(relative, state["files"])

    def test_recovered_projection_still_fails_closed_after_local_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            project_data = read_yaml(manifest)
            project_data["framework"]["version"] = "0.9.9"
            write_yaml(manifest, project_data)

            old_skill = project / ".github/skills/review/SKILL.md"
            old_skill.parent.mkdir(parents=True)
            old_skill.write_text("prior generated skill\n", encoding="utf-8")

            def fake_generate(
                runtime_python: Path,
                runtime_root: Path,
                host: str,
                output: Path,
                consumer: Path,
            ) -> None:
                generated = output / ".github/skills/review/SKILL.md"
                generated.parent.mkdir(parents=True)
                generated.write_text(
                    "prior generated skill\n",
                    encoding="utf-8",
                )

            with (
                patch(
                    "embraion.project.ensure_cached_runtime",
                    return_value=SimpleNamespace(
                        python=Path("previous-python"),
                        framework_root=Path("previous-framework"),
                    ),
                ),
                patch(
                    "embraion.project._generate_host_with_cached_runtime",
                    side_effect=fake_generate,
                ),
            ):
                update_project(project, version=__version__)

            old_skill.write_text(
                "prior generated skill\n# local edit\n",
                encoding="utf-8",
            )

            plan = projection_plan(
                "copilot",
                project,
                components=["skills"],
            )
            relative = ".github/skills/review/SKILL.md"
            self.assertIn(relative, plan["conflict"])
            self.assertNotIn(relative, plan["update"])

            with self.assertRaisesRegex(
                RuntimeError,
                "Projection conflicts",
            ):
                install(
                    "copilot",
                    project,
                    components=["skills"],
                )

    def test_codex_config_merge_preserves_project_owned_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            config = project / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[agents]\n"
                'default_subagent_model = "project-owned-model"\n'
                "\n"
                "[mcp_servers.unity]\n"
                'command = "unity"\n'
                'args = ["mcp", "--project-path", "."]\n',
                encoding="utf-8",
            )

            install(
                "codex",
                project,
                components=["config"],
                config_mode="merge",
            )

            merged_text = config.read_text(encoding="utf-8")
            merged = tomllib.loads(merged_text)
            self.assertTrue(merged["agents"]["enabled"])
            self.assertEqual(
                3,
                merged["agents"]["max_concurrent_threads_per_session"],
            )
            self.assertEqual(
                "project-owned-model",
                merged["agents"]["default_subagent_model"],
            )
            self.assertEqual("unity", merged["mcp_servers"]["unity"]["command"])
            self.assertIn("# >>> EmbrAIon managed: agents", merged_text)
            self.assertIn("# <<< EmbrAIon managed: agents", merged_text)

            clean = projection_plan(
                "codex",
                project,
                components=["config"],
                config_mode="merge",
            )
            self.assertTrue(projection_is_verified(clean))
            self.assertIn(".codex/config.toml", clean["unchanged"])

            config.write_text(
                merged_text.replace("enabled = true", "enabled = false"),
                encoding="utf-8",
            )
            drift = projection_plan(
                "codex",
                project,
                components=["config"],
                config_mode="merge",
            )
            self.assertFalse(projection_is_verified(drift))
            self.assertIn(".codex/config.toml", drift["update"])

            install(
                "codex",
                project,
                components=["config"],
                config_mode="merge",
            )
            repaired = tomllib.loads(config.read_text(encoding="utf-8"))
            self.assertTrue(repaired["agents"]["enabled"])
            self.assertEqual(
                "project-owned-model",
                repaired["agents"]["default_subagent_model"],
            )
            self.assertEqual(
                "unity",
                repaired["mcp_servers"]["unity"]["command"],
            )

    def test_codex_config_merge_rejects_markers_outside_agents_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            config = project / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[agents]\n"
                "enabled = true\n"
                "max_concurrent_threads_per_session = 3\n"
                'default_subagent_model = "project-owned"\n'
                "\n"
                "[mcp_servers.fake]\n"
                '"# not a TOML key" = "kept"\n'
                "# >>> EmbrAIon managed: agents\n"
                "enabled = true\n"
                "max_concurrent_threads_per_session = 3\n"
                "# <<< EmbrAIon managed: agents\n"
                'command = "fake"\n',
                encoding="utf-8",
            )

            plan = projection_plan(
                "codex",
                project,
                components=["config"],
                config_mode="merge",
            )
            self.assertIn(".codex/config.toml", plan["conflict"])

            with self.assertRaisesRegex(
                RuntimeError,
                "Cannot safely merge .codex/config.toml",
            ):
                install(
                    "codex",
                    project,
                    components=["config"],
                    config_mode="merge",
                )

    def test_codex_config_merge_fails_closed_on_invalid_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            config = project / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[agents\n", encoding="utf-8")

            plan = projection_plan(
                "codex",
                project,
                components=["config"],
                config_mode="merge",
            )
            self.assertIn(".codex/config.toml", plan["conflict"])

            with self.assertRaisesRegex(
                RuntimeError,
                "Cannot safely merge .codex/config.toml",
            ):
                install(
                    "codex",
                    project,
                    components=["config"],
                    config_mode="merge",
                    force=True,
                )

    def test_projection_lifecycle_detects_local_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            clean = projection_plan("codex", project)
            self.assertEqual([], clean["conflict"])
            self.assertGreater(len(clean["unchanged"]), 0)

            reviewer = project / ".codex/agents/reviewer.toml"
            reviewer.write_text(
                reviewer.read_text(encoding="utf-8") + "\n# local change\n",
                encoding="utf-8",
            )

            dirty = projection_plan("codex", project)
            self.assertIn(".codex/agents/reviewer.toml", dirty["conflict"])
            with self.assertRaises(RuntimeError):
                install("codex", project)

            install("codex", project, force=True)
            restored = projection_plan("codex", project)
            self.assertEqual([], restored["conflict"])

    def test_obsolete_projection_ownership_survives_until_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            relative = ".codex/agents/obsolete.toml"
            stale = project / relative
            original = "generated obsolete projection\n"
            stale.write_text(original, encoding="utf-8")

            state_path = project / ".embraion/state/projections/codex.json"
            state = read_json(state_path)
            state["files"][relative] = hashlib.sha256(stale.read_bytes()).hexdigest()
            write_json(state_path, state)

            before = projection_plan("codex", project)
            self.assertIn(relative, before["obsolete-owned"])

            install("codex", project)
            retained = projection_plan("codex", project)
            self.assertIn(relative, retained["obsolete-owned"])

            stale.write_text(original + "# local change\n", encoding="utf-8")
            modified = projection_plan("codex", project)
            self.assertIn(relative, modified["obsolete-modified"])

            install("codex", project, prune=True)
            self.assertTrue(stale.is_file())
            still_modified = projection_plan("codex", project)
            self.assertIn(relative, still_modified["obsolete-modified"])

            stale.write_text(original, encoding="utf-8")
            install("codex", project, prune=True)
            self.assertFalse(stale.exists())

    def test_structured_knowledge_uses_dedicated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            knowledge_dir = project / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "architecture.md").write_text(
                "architecture",
                encoding="utf-8",
            )

            knowledge_path = manifest.with_name("knowledge.yaml")
            data = read_yaml(knowledge_path)
            data["architecture"] = {
                "path": "knowledge/architecture.md",
                "data-class": "PRIVATE",
                "trust": "project",
                "roles": ["architect"],
                "triggers": ["architecture"],
            }
            write_yaml(knowledge_path, data)

            self.assertNotIn("knowledge", read_yaml(manifest))
            self.assertEqual(
                "knowledge/architecture.md",
                read_yaml(knowledge_path)["architecture"]["path"],
            )

    def test_slots_is_a_reserved_top_level_knowledge_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            knowledge_path = project / ".embraion" / "knowledge.yaml"
            write_yaml(
                knowledge_path,
                {"slots": "knowledge/legacy-slots.md"},
            )

            with self.assertRaisesRegex(
                RuntimeError,
                ".embraion/knowledge.yaml",
            ):
                read_knowledge_config(project)

    def test_project_contract_slots_select_bound_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            docs = project / "docs"
            docs.mkdir()
            (docs / "architecture.md").write_text(
                "project architecture",
                encoding="utf-8",
            )
            (docs / "persistence.md").write_text(
                "stable persisted identifiers",
                encoding="utf-8",
            )

            knowledge_path = project / ".embraion" / "knowledge.yaml"
            knowledge = read_yaml(knowledge_path)
            knowledge["slots"]["architecture"] = "docs/architecture.md"
            knowledge["slots"]["persistence"] = {
                "path": "docs/persistence.md",
                "data-class": "PRIVATE",
            }
            write_yaml(knowledge_path, knowledge)

            automatic = build_context(
                "Review architecture ownership boundaries",
                "architect",
                "PRIVATE",
                project=project,
                persist=False,
            )
            self.assertEqual(
                ["slot:architecture"],
                [item["id"] for item in automatic["selected"]],
            )
            self.assertEqual(
                "architecture",
                automatic["selected"][0]["slot"],
            )

            forced = build_context(
                "Review this change",
                "reviewer",
                "PRIVATE",
                slots=["persistence"],
                project=project,
                persist=False,
            )
            self.assertIn(
                "slot:persistence",
                [item["id"] for item in forced["selected"]],
            )
            self.assertEqual(["persistence"], forced["requested-slots"])

    def test_project_contract_status_reports_bound_and_missing_slots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            docs = project / "docs"
            docs.mkdir()
            (docs / "architecture.md").write_text(
                "architecture",
                encoding="utf-8",
            )

            knowledge_path = project / ".embraion" / "knowledge.yaml"
            knowledge = read_yaml(knowledge_path)
            knowledge["slots"]["architecture"] = "docs/architecture.md"
            knowledge["slots"]["compatibility"] = "docs/missing.md"
            write_yaml(knowledge_path, knowledge)

            report = project_contract_status(
                read_knowledge_config(project),
                project,
            )
            by_id = {item["id"]: item for item in report["slots"]}
            self.assertTrue(by_id["architecture"]["configured"])
            self.assertTrue(by_id["architecture"]["exists"])
            self.assertTrue(by_id["compatibility"]["configured"])
            self.assertFalse(by_id["compatibility"]["exists"])
            self.assertFalse(by_id["persistence"]["configured"])
            self.assertEqual(2, report["configured"])
            self.assertEqual(1, report["available"])


if __name__ == "__main__":
    unittest.main()
