from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from embraion.common import read_yaml, write_yaml


ROOT = Path(__file__).resolve().parents[2]


class SelfHostingTests(unittest.TestCase):
    def test_older_locked_runtime_can_validate_newer_self_hosted_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "checkout"
            root.mkdir()
            for name in ("core", "adapters", "schemas", "templates"):
                shutil.copytree(ROOT / name, root / name)
            shutil.copytree(ROOT / "tools/cli/embraion", root / "tools/cli/embraion")
            shutil.copy2(ROOT / "tools/source.py", root / "tools/source.py")
            shutil.copy2(ROOT / "framework.yaml", root / "framework.yaml")
            # Change only fixture source version, keeping a stable older project lock.
            framework = read_yaml(root / "framework.yaml")
            framework["version"] = "99.0.1"
            write_yaml(root / "framework.yaml", framework)
            (root / "tools/cli/embraion/__init__.py").write_text('__version__ = "99.0.1"\n', encoding="utf-8")
            shutil.copytree(ROOT / ".embraion", root / ".embraion", ignore=shutil.ignore_patterns("state", "cache"))
            manifest = root / ".embraion/project.yaml"
            original = manifest.read_bytes()
            (root / "tests/unit").mkdir(parents=True)
            (root / "tests/fixtures").mkdir()
            (root / "tests/fixtures/source-only.txt").write_text("source fixture", encoding="utf-8")
            (root / "tests/unit/test_identity.py").write_text(
                "import os,shutil,tempfile,unittest\n"
                "from pathlib import Path\n"
                "import embraion\n"
                "from embraion.common import framework_root,read_yaml\n"
                "from embraion.runtime import route\n"
                "from embraion.project import load_agents,generate_host,install,projection_plan,projection_is_verified\n"
                "class Identity(unittest.TestCase):\n"
                " def test_source_and_routing(self):\n"
                "  root=Path.cwd()\n"
                "  self.assertEqual(root,framework_root())\n"
                "  self.assertEqual(root/'tools/cli/embraion/__init__.py',Path(embraion.__file__))\n"
                "  self.assertEqual('99.0.1',embraion.__version__)\n"
                "  self.assertTrue((root/'tests/fixtures/source-only.txt').is_file())\n"
                "  for key in ['EMBRAION_HOME','EMBRAION_VERSION_RESOLVED','EMBRAION_RESOLVED_VERSION','EMBRAION_RESOLVED_PROJECT']:\n"
                "   self.assertNotIn(key,os.environ)\n"
                "  configured=read_yaml(root/'.embraion/routing.yaml')['overrides']['codex']['routes']['substantial']\n"
                "  self.assertEqual(configured['deployment'],route('codex','substantial','PRIVATE')['deployment'])\n"
                "  with tempfile.TemporaryDirectory() as blank:\n"
                "   self.assertEqual('host-default',route('codex','substantial','PRIVATE',project=Path(blank))['resolution'])\n"
                "  self.assertEqual({'lead','worker','reviewer','architect','analyst','validator','researcher','steward'},{a['id'] for a in load_agents(root,root)})\n"
                "  generate_host(root,'codex',root/'build/codex',project=root)\n"
                "  self.assertIn('developer_instructions',(root/'build/codex/.codex/config.toml').read_text())\n"
                "  for directory in ['.codex','.agents']:\n"
                "   shutil.copytree(root/'build/codex'/directory,root/directory)\n"
                "  self.assertTrue(projection_is_verified(projection_plan('codex',root)))\n"
                "  install('codex',root)\n",
                encoding="utf-8",
            )
            write_yaml(root / ".embraion/validation.yaml", {
                "profiles": {"fast": [f'"{sys.executable}" tools/source.py test unit']},
            })
            # Mimic the interpreter-scoped environment of a delegated older runtime.
            environment = os.environ.copy()
            environment.update({
                "EMBRAION_VERSION_RESOLVED": "1",
                "EMBRAION_RESOLVED_VERSION": "0.16.0",
                "EMBRAION_RESOLVED_PROJECT": str(manifest),
                "EMBRAION_HOME": str(Path(temporary) / "packaged-data"),
                "PYTHONPATH": str(ROOT / "tools/cli"),
            })
            result = subprocess.run(
                [sys.executable, "-c", "from embraion.project_validation import run_validation_profile; "
                 "r=run_validation_profile('fast'); print(r); raise SystemExit(r['status']!='passed')"],
                cwd=root, env=environment, text=True, capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(original, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
