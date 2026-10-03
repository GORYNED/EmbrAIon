"""Run the opt-in adapter's mock behavior suite when Node is available."""
import shutil
import subprocess
import unittest

from embraion.common import framework_root


class ClaudeModsProbeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Optional Claude Mods mock tests require Node")
    def test_mock_native_hooks(self):
        version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True, timeout=10)
        if int(version.stdout.strip().lstrip("v").split(".")[0]) < 18:
            self.skipTest("Optional Claude Mods mock tests require Node 18 or newer")
        result = subprocess.run(
            ["node", str(framework_root() / "adapters/claude-code/mods-probe/hooks/register.test.mjs")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
