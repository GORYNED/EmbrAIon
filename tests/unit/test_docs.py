from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path
from urllib.parse import unquote

import yaml

from embraion.cli import build_parser


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SITE_URL = "https://goryned.github.io/EmbrAIon/"


def _nav_targets(value: object) -> list[str]:
    targets: list[str] = []

    if isinstance(value, str):
        targets.append(value)
    elif isinstance(value, list):
        for item in value:
            targets.extend(_nav_targets(item))
    elif isinstance(value, dict):
        for item in value.values():
            targets.extend(_nav_targets(item))

    return targets


class DocumentationTests(unittest.TestCase):
    def test_mkdocs_nav_targets_exist(self) -> None:
        config = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
        targets = _nav_targets(config["nav"])

        self.assertIn("index.md", targets)
        self.assertIn("reference/cli.md", targets)
        self.assertIn("examples/unity.md", targets)
        self.assertIn("oss/security-reporting.md", targets)

        for target in targets:
            if not target.endswith(".md"):
                continue
            with self.subTest(target=target):
                self.assertTrue((DOCS / target).is_file())

    def test_internal_markdown_links_resolve(self) -> None:
        link_pattern = re.compile(r"!?[[^]]*](([^)]+))")

        for path in DOCS.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for raw_target in link_pattern.findall(text):
                target = unquote(raw_target.strip().split()[0].strip("<>"))
                target = target.split("#", 1)[0]

                if not target:
                    continue
                if target.startswith(("http://", "https://", "mailto:")):
                    continue

                resolved = (path.parent / target).resolve()
                with self.subTest(path=path.relative_to(ROOT), target=target):
                    self.assertTrue(resolved.exists(), resolved)

    def test_cli_reference_covers_top_level_commands(self) -> None:
        parser = build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if action.__class__.__name__ == "_SubParsersAction"
        )
        commands = set(subparsers.choices)
        reference = (DOCS / "reference" / "cli.md").read_text(encoding="utf-8")

        missing = [
            command
            for command in sorted(commands)
            if f"`embraion {command}`" not in reference
        ]
        self.assertEqual([], missing)

    def test_brand_assets_are_available_to_site(self) -> None:
        self.assertTrue((DOCS / "assets" / "hero-dark.png").is_file())
        self.assertTrue((DOCS / "assets" / "icon-dark-1024.png").is_file())
        self.assertTrue((DOCS / "stylesheets" / "extra.css").is_file())

    def test_package_metadata_points_to_public_docs(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            package = tomllib.load(handle)

        self.assertEqual(SITE_URL, package["project"]["urls"]["Documentation"])
