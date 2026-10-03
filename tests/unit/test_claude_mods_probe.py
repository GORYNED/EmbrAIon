"""Run the opt-in adapter's mock behavior suite when Node is available."""
import shutil
import subprocess
import unittest

from embraion.common import framework_root


class ClaudeModsProbeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Optional Claude Mods mock tests require Node")
    def test_mock_native_hooks(self):
        result = subprocess.run(
            ["node", "--test", str(framework_root() / "adapters/claude-code/mods-probe/hooks/register.test.mjs")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
