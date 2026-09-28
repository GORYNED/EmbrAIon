from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion.codex_config import (
    AGENTS_BEGIN, AGENTS_END, ORCHESTRATION_BEGIN, ORCHESTRATION_END,
    merge_codex_config, orchestration_block,
)
from embraion.common import framework_root
from embraion.project import generate_host, init_project, install, projection_is_verified, projection_plan


class CodexConfigTests(unittest.TestCase):
    def generated(self, text: str = "Generated Lead contract") -> str:
        import json
        return 'developer_instructions = ' + json.dumps(orchestration_block(text)) + '\n[agents]\nenabled = true\nmax_concurrent_threads_per_session = 3\n'

    def test_preserves_user_values_comments_and_instruction_prefix_suffix(self) -> None:
        user = '''# user root comment
model = "user-selector" # keep root option
developer_instructions = """User policy with \\n and [agents].""" # keep instruction comment
["agents"] # keep agents header
"enabled" = false
max_concurrent_threads_per_session = 8
default_subagent_model = "user-child"
default_subagent_reasoning_effort = "high"
note = ''' + "'''\n[agents]\nenabled = false\n'''" + '''
[other]
enabled = false
[[other.items]]
name = "one"
'''
        first = merge_codex_config(user, self.generated())
        values = tomllib.loads(first)
        self.assertEqual("user-selector", values["model"])
        self.assertEqual("user-child", values["agents"]["default_subagent_model"])
        self.assertEqual("high", values["agents"]["default_subagent_reasoning_effort"])
        self.assertEqual(tomllib.loads(user)["other"], values["other"])
        self.assertEqual(tomllib.loads(user)["agents"]["note"], values["agents"]["note"])
        self.assertTrue(values["developer_instructions"].startswith(tomllib.loads(user)["developer_instructions"] + "\n\n"))
        for comment in ("# user root comment", "# keep root option", "# keep instruction comment", "# keep agents header"):
            self.assertIn(comment, first)
        self.assertEqual(first, merge_codex_config(first, self.generated()))
        # User text added after the subsection survives a framework upgrade.
        import tomlkit
        document = tomlkit.parse(first)
        document["developer_instructions"] = str(document["developer_instructions"]) + "\nUser suffix"
        old = tomlkit.dumps(document)
        upgraded = merge_codex_config(old, self.generated("New Lead contract"))
        self.assertIn("New Lead contract", tomllib.loads(upgraded)["developer_instructions"])
        self.assertNotIn("Generated Lead contract", tomllib.loads(upgraded)["developer_instructions"])
        self.assertTrue(tomllib.loads(upgraded)["developer_instructions"].endswith("\nUser suffix"))
        self.assertEqual(upgraded, merge_codex_config(upgraded, self.generated("New Lead contract")))

    def test_legacy_agents_block_migrates_and_drift_repairs_only_owned_state(self) -> None:
        legacy = f'[agents]\n{AGENTS_BEGIN}\nenabled = false\nmax_concurrent_threads_per_session = 1\n{AGENTS_END}\nuser = "keep"\n'
        result = merge_codex_config(legacy, self.generated())
        self.assertTrue(tomllib.loads(result)["agents"]["enabled"])
        self.assertEqual("keep", tomllib.loads(result)["agents"]["user"])
        self.assertEqual(1, result.count(AGENTS_BEGIN))
        self.assertEqual(1, result.count(ORCHESTRATION_BEGIN))
        self.assertEqual(result, merge_codex_config(result, self.generated()))

    def test_ambiguous_markers_and_types_fail_closed(self) -> None:
        import json
        cases = [
            '[agents\n',
            'developer_instructions = 4\n',
            'agents = "wrong"\n',
            'agents = {enabled = true}\n',
            'agents.enabled = true\nagents.default_subagent_model = "user"\n',
            '[agents.worker]\nconfig_file = "agents/worker.toml"\n',
            '[agents.custom]\nvalue = 1\n[other]\nvalue = 2\n[agents]\nenabled = true\n',
            f'{AGENTS_BEGIN}\n[agents]\nenabled = true\n{AGENTS_END}\n',
            f'[agents]\n{AGENTS_BEGIN}\nenabled = true\n',
            f'[agents]\n{AGENTS_END}\n{AGENTS_BEGIN}\n',
            f'[agents]\n{AGENTS_BEGIN}\nenabled = true\nmax_concurrent_threads_per_session = 3\nuser = "valuable"\n{AGENTS_END}\n',
            f'note = \'\'\'\n{AGENTS_BEGIN}\n{AGENTS_END}\n\'\'\'\n',
            f'[other]\n{AGENTS_BEGIN}\nenabled = true\nmax_concurrent_threads_per_session = 3\n{AGENTS_END}\n',
        ]
        malformed = [ORCHESTRATION_BEGIN, ORCHESTRATION_END, ORCHESTRATION_END + "\n" + ORCHESTRATION_BEGIN,
                     orchestration_block("one") + "\n" + orchestration_block("two"), "prefix" + orchestration_block("one")]
        cases.extend('developer_instructions = ' + json.dumps(value) + '\n' for value in malformed)
        cases.append('[nested]\ndeveloper_instructions = ' + json.dumps(orchestration_block("wrong scope")))
        for value in cases:
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "Cannot safely merge"):
                merge_codex_config(value, self.generated())

    def test_install_diff_verify_upgrade_and_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="ConfigConsumer")
            config = project / ".codex/config.toml"
            config.parent.mkdir()
            config.write_text('user_option = "kept"\ndeveloper_instructions = "user policy"\n', encoding="utf-8")
            options = {"components": ["config"], "config_mode": "merge"}
            install("codex", project, **options)
            before = config.read_bytes()
            install("codex", project, **options)
            self.assertEqual(before, config.read_bytes())
            self.assertTrue(projection_is_verified(projection_plan("codex", project, **options)))
            config.write_text(config.read_text(encoding="utf-8").replace("proactively delegate", "old instructions"), encoding="utf-8")
            self.assertIn(".codex/config.toml", projection_plan("codex", project, **options)["update"])
            install("codex", project, **options)
            self.assertEqual(before, config.read_bytes())
            broken = config.read_text(encoding="utf-8").replace(ORCHESTRATION_END, "missing")
            config.write_text(broken, encoding="utf-8")
            self.assertIn(".codex/config.toml", projection_plan("codex", project, **options)["conflict"])
            with self.assertRaises(RuntimeError):
                install("codex", project, force=True, **options)
            self.assertEqual(broken, config.read_text(encoding="utf-8"))
            install("codex", project, components=["config"], force=True)
            self.assertNotIn("user_option", tomllib.loads(config.read_text(encoding="utf-8")))
            self.assertTrue(projection_is_verified(projection_plan("codex", project, components=["config"])))

    def test_nested_user_agents_preserve_ownership_and_idempotence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="NestedConfigConsumer")
            config = project / ".codex/config.toml"
            config.parent.mkdir()
            config.write_text('[agents]\ndefault_subagent_model = "user"\n[agents.worker]\nconfig_file = "agents/worker.toml"\n[agents.custom]\ndescription = "Keep my role"\n', encoding="utf-8")
            options = {"components": ["config"], "config_mode": "merge"}
            install("codex", project, **options)
            first = config.read_bytes()
            self.assertTrue(projection_is_verified(projection_plan("codex", project, **options)))
            install("codex", project, **options)
            self.assertEqual(first, config.read_bytes())
            agents = tomllib.loads(config.read_text(encoding="utf-8"))["agents"]
            self.assertEqual("user", agents["default_subagent_model"])
            self.assertEqual({"config_file": "agents/worker.toml"}, agents["worker"])
            self.assertEqual({"description": "Keep my role"}, agents["custom"])

    def test_all_hosts_receive_derived_lead_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for host, directory in (("codex", ".agents/skills"), ("copilot", ".github/skills"),
                                    ("claude-code", ".claude/skills"), ("portable", "embraion/skills")):
                target = Path(temporary) / host
                generate_host(framework_root(), host, target)
                skill = (target / directory / "orchestration/SKILL.md").read_text(encoding="utf-8")
                self.assertIn("Generated Core Lead contract", skill)
                self.assertIn("proactively delegate", skill)
                self.assertIn("final acceptance authority", skill)


if __name__ == "__main__":
    unittest.main()
