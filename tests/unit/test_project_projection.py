from __future__ import annotations

import os
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion.common import framework_root, framework_version, read_json, write_yaml
from embraion.project import (
    _pin_core_links,
    _projection_state_path,
    generate_host,
    init_project,
    install,
    projection_is_verified,
    projection_plan,
)


SPECIALIST = {
    "id": "domain-specialist",
    "extends": "reviewer",
    "purpose": "Review project-specific domain behavior.",
    "access": "read-only",
    "responsibilities": ["focus review on project-specific domain contracts"],
    "triggers": ["domain-focused review"],
    "outputs": ["domain review findings"],
}

HOST_SKILLS = {
    "codex": ".agents/skills",
    "copilot": ".github/skills",
    "claude-code": ".claude/skills",
}


def _skill(project: Path, name: str, body: str = "# Skill\n", *, front_name: str | None = None) -> Path:
    directory = project / ".embraion" / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {front_name or name}\ndescription: A project-owned skill.\n---\n\n{body}",
        encoding="utf-8",
    )
    return directory


class CoreLinkProjectionTests(unittest.TestCase):
    def test_no_projected_output_contains_an_unresolved_core_relative_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            init_project(project)
            write_yaml(project / ".embraion/agents.yaml", {"agents": [SPECIALIST]})
            _skill(project, "domain-glossary")
            for host in ("codex", "copilot", "claude-code", "portable"):
                generate_host(framework_root(), host, Path(temporary) / host, project=project)
            offenders = [
                path.relative_to(temporary).as_posix()
                for path in Path(temporary).rglob("*")
                if path.is_file() and "project" not in path.relative_to(temporary).parts[:1]
                and "../../core/" in path.read_text(encoding="utf-8", errors="ignore")
            ]
            self.assertEqual([], offenders)

    def test_worktree_link_is_pinned_to_the_framework_release(self) -> None:
        pinned = (
            f"https://github.com/GORYNED/EmbrAIon/blob/v{framework_version(framework_root())}"
            "/core/workflows/worktree.md"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            generate_host(framework_root(), "claude-code", output / "claude", ["skills"])
            generate_host(framework_root(), "codex", output / "codex", ["config", "skills"])
            self.assertIn(pinned, (output / "claude/.claude/skills/orchestration/SKILL.md").read_text(encoding="utf-8"))
            self.assertIn(pinned, (output / "codex/.agents/skills/orchestration/SKILL.md").read_text(encoding="utf-8"))
            config = tomllib.loads((output / "codex/.codex/config.toml").read_text(encoding="utf-8"))
            self.assertIn(pinned, config["developer_instructions"])

    def test_link_to_a_missing_core_file_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing Core file"):
            _pin_core_links(framework_root(), "See [gone](../../core/workflows/gone.md).")
        self.assertIn(
            "/core/workflows/worktree.md#cleanup)",
            _pin_core_links(framework_root(), "[w](../../core/workflows/worktree.md#cleanup)"),
        )


class ProjectSpecialistProjectionTests(unittest.TestCase):
    def test_triggers_and_outputs_reach_every_host_profile_and_the_orchestration_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            write_yaml(project / ".embraion/agents.yaml", {"agents": [SPECIALIST]})
            for host in ("claude-code", "codex", "copilot"):
                install(host, project)

            profiles = {
                "claude-code": (project / ".claude/agents/domain-specialist.md").read_text(encoding="utf-8"),
                "copilot": (project / ".github/agents/domain-specialist.agent.md").read_text(encoding="utf-8"),
                "codex": tomllib.loads(
                    (project / ".codex/agents/domain-specialist.toml").read_text(encoding="utf-8")
                )["developer_instructions"],
            }
            for host, text in profiles.items():
                with self.subTest(host=host):
                    self.assertIn("Triggers:\n", text)
                    self.assertIn("- domain-focused review", text)
                    self.assertIn("Outputs:\n", text)
                    self.assertIn("- domain review findings", text)

            # Core role profiles keep their existing content.
            self.assertNotIn("Triggers:", (project / ".claude/agents/reviewer.md").read_text(encoding="utf-8"))

            for relative in HOST_SKILLS.values():
                with self.subTest(skills=relative):
                    skill = (project / relative / "orchestration/SKILL.md").read_text(encoding="utf-8")
                    section = skill.split("## Project specialists", 1)[1]
                    self.assertIn(
                        "- `domain-specialist` (extends `reviewer`): Review project-specific domain behavior.",
                        section,
                    )
                    self.assertIn("  - Triggers: domain-focused review\n", section)
                    self.assertIn("  - Outputs: domain review findings\n", section)
                    # Inherited Core cues are not repeated in the Lead summary.
                    self.assertNotIn("every pull request", section.split("\n## ", 1)[0])

    def test_no_specialists_writes_no_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            install("claude-code", project, components=["skills"])
            skill = (project / ".claude/skills/orchestration/SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("## Project specialists", skill)
            (project / ".embraion/agents.yaml").unlink()
            install("copilot", project, components=["skills"])
            self.assertNotIn(
                "## Project specialists",
                (project / ".github/skills/orchestration/SKILL.md").read_text(encoding="utf-8"),
            )


class ProjectSkillProjectionTests(unittest.TestCase):
    def test_project_skills_are_projected_recorded_and_verified_for_every_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            source = _skill(project, "domain-glossary", "# Glossary\r\n")
            (source / "references").mkdir()
            (source / "references/terms.md").write_text("terms\n", encoding="utf-8")

            for host, relative in HOST_SKILLS.items():
                with self.subTest(host=host):
                    install(host, project)
                    entry = f"{relative}/domain-glossary/SKILL.md"
                    self.assertTrue((project / entry).is_file())
                    self.assertNotIn(b"\r\n", (project / entry).read_bytes())
                    self.assertTrue((project / relative / "orchestration/SKILL.md").is_file())
                    files = read_json(_projection_state_path(project, host))["files"]
                    self.assertIn(entry, files)
                    self.assertIn(f"{relative}/domain-glossary/references/terms.md", files)
                    self.assertTrue(projection_is_verified(projection_plan(host, project)))

            (project / ".claude/skills/domain-glossary/SKILL.md").write_text("edited\n", encoding="utf-8")
            drift = projection_plan("claude-code", project)
            self.assertEqual([".claude/skills/domain-glossary/SKILL.md"], drift["conflict"])

            shutil.rmtree(source)
            for host, relative in HOST_SKILLS.items():
                with self.subTest(removed=host):
                    plan = projection_plan(host, project)
                    self.assertFalse(projection_is_verified(plan))
                    obsolete = plan["obsolete-owned"] + plan["obsolete-modified"]
                    self.assertIn(f"{relative}/domain-glossary/references/terms.md", obsolete)
                    self.assertIn(f"{relative}/domain-glossary/SKILL.md", obsolete)

            install("codex", project, prune=True)
            self.assertFalse((project / ".agents/skills/domain-glossary/SKILL.md").exists())
            self.assertTrue(projection_is_verified(projection_plan("codex", project)))

    def test_core_collision_and_malformed_skills_fail_before_writing(self) -> None:
        cases = {
            "collides with a Core skill": lambda project: _skill(project, "review"),
            "lowercase kebab-case": lambda project: _skill(project, "Domain_Skill"),
            "front matter": lambda project: _skill(project, "domain-glossary", front_name="other"),
            "missing SKILL.md": lambda project: (project / ".embraion/skills/empty").mkdir(parents=True),
            "skill directory": lambda project: (
                (project / ".embraion/skills").mkdir(parents=True),
                (project / ".embraion/skills/notes.md").write_text("x", encoding="utf-8"),
            ),
        }
        for message, prepare in cases.items():
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                init_project(project)
                prepare(project)
                with self.assertRaisesRegex(RuntimeError, message):
                    install("claude-code", project, components=["skills"])
                self.assertFalse((project / ".claude/skills").exists())

    @unittest.skipIf(os.name == "nt", "symbolic links need elevated rights on Windows")
    def test_linked_project_skill_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            init_project(project)
            source = _skill(project, "domain-glossary")
            outside = Path(temporary) / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            (source / "linked.md").symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                projection_plan("copilot", project, components=["skills"])


if __name__ == "__main__":
    unittest.main()
