from __future__ import annotations

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("parallel_runner_under_test", ROOT / "tools" / "parallel_tests.py")
parallel = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = parallel
_SPEC.loader.exec_module(parallel)

RECORDING_MODULE = (
    "import tempfile, time, unittest\n"
    "from pathlib import Path\n"
    "class Recording(unittest.TestCase):\n"
    "    def test_records_its_temporary_directory(self):\n"
    "        time.sleep(0.3)\n"
    "        (Path(__file__).parent / 'record-{name}.txt').write_text(tempfile.gettempdir(), encoding='utf-8')\n"
)


class ParallelRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.suite = Path(temporary.name) / "suite"
        self.suite.mkdir()
        original_path = list(sys.path)
        original_modules = set(sys.modules)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        self.addCleanup(lambda: [sys.modules.pop(name) for name in set(sys.modules) - original_modules])

    def run_suite(self, jobs: int, sequential: dict[str, str] | None = None) -> tuple[int, str]:
        output = io.StringIO()
        with patch.dict(parallel.SEQUENTIAL_MODULES, {"unit": sequential or {}}, clear=True), \
                contextlib.redirect_stdout(output):
            code = parallel.run_parallel("unit", self.suite, jobs)
        return code, output.getvalue()

    def test_each_process_gets_its_own_temporary_directory(self) -> None:
        for name in ("a", "b", "c", "d"):
            (self.suite / f"test_rec_{name}.py").write_text(RECORDING_MODULE.format(name=name), encoding="utf-8")
        code, output = self.run_suite(2)
        self.assertEqual(0, code, output)
        self.assertIn("Ran 4 tests", output)
        self.assertIn("Test count matches discovery: 4.", output)
        recorded = {path.read_text(encoding="utf-8") for path in self.suite.glob("record-*.txt")}
        self.assertEqual(2, len(recorded), recorded)
        parent = Path(tempfile.gettempdir()).resolve()
        for directory in recorded:
            self.assertNotEqual(parent, Path(directory).resolve())
            self.assertIn("et-", directory)
        self.assertIn("process 1:", output)
        self.assertIn("process 2:", output)

    def test_a_failing_module_fails_the_run_and_keeps_its_report(self) -> None:
        (self.suite / "test_good.py").write_text(
            "import unittest\nclass Good(unittest.TestCase):\n    def test_ok(self): pass\n", encoding="utf-8")
        (self.suite / "test_bad.py").write_text(
            "import unittest\nclass Bad(unittest.TestCase):\n"
            "    def test_fails(self): self.assertEqual('left', 'right')\n", encoding="utf-8")
        code, output = self.run_suite(2)
        self.assertEqual(1, code)
        self.assertIn("FAIL: test_fails", output)
        self.assertIn("AssertionError", output)
        self.assertIn("FAILED (failures=1)", output)
        self.assertIn("Ran 2 tests", output)

    def test_a_module_that_dies_is_reported_as_crashed(self) -> None:
        (self.suite / "test_exit.py").write_text(
            "import os, unittest\nclass Exit(unittest.TestCase):\n"
            "    def test_dies(self):\n        print('last words', flush=True)\n        os._exit(3)\n", encoding="utf-8")
        code, output = self.run_suite(2)
        self.assertEqual(1, code)
        self.assertIn("without a result", output)
        self.assertIn("last words", output)
        self.assertIn("crashed-modules=1", output)
        self.assertIn("test-count-mismatch=1", output)

    def test_a_worker_that_exits_non_zero_after_writing_a_result_fails_the_run(self) -> None:
        (self.suite / "test_late.py").write_text(
            "import atexit, os, unittest\n"
            "atexit.register(os._exit, 5)\n"
            "class Late(unittest.TestCase):\n    def test_passes(self): pass\n", encoding="utf-8")
        code, output = self.run_suite(2)
        self.assertEqual(1, code, output)
        self.assertIn("exited with status 5 after writing a result", output)
        self.assertIn("crashed-modules=1", output)
        self.assertIn("Test count matches discovery: 1.", output)

    def test_a_module_that_skips_itself_on_import_is_counted_as_skipped(self) -> None:
        (self.suite / "test_optional.py").write_text(
            "import unittest\nraise unittest.SkipTest('optional dependency missing')\n", encoding="utf-8")
        (self.suite / "test_plain.py").write_text(
            "import unittest\nclass Plain(unittest.TestCase):\n    def test_ok(self): pass\n", encoding="utf-8")
        code, output = self.run_suite(2)
        self.assertEqual(0, code, output)
        self.assertIn("Test count matches discovery: 2.", output)
        self.assertIn("OK (skipped=1)", output)

    def test_named_sequential_modules_run_in_the_parent_after_the_workers(self) -> None:
        for name in ("a", "b"):
            (self.suite / f"test_pin_{name}.py").write_text(
                "import os, unittest\nclass Pin(unittest.TestCase):\n"
                "    def test_pid(self):\n"
                "        from pathlib import Path\n"
                f"        (Path(__file__).parent / 'pid-{name}.txt').write_text(str(os.getpid()), encoding='utf-8')\n",
                encoding="utf-8")
        code, output = self.run_suite(2, {"test_pin_b": "uses a fixed path"})
        self.assertEqual(0, code, output)
        self.assertIn("1 sequential in the parent: test_pin_b", output)
        self.assertIn("parent (sequential): 1 modules, 1 tests", output)
        self.assertEqual(str(os.getpid()), (self.suite / "pid-b.txt").read_text(encoding="utf-8"))
        self.assertNotEqual(str(os.getpid()), (self.suite / "pid-a.txt").read_text(encoding="utf-8"))
        self.assertIn("Test count matches discovery: 2.", output)


class SourceCommandJobsTests(unittest.TestCase):
    def source(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(ROOT / "tools" / "source.py"), "test", *arguments],
                              capture_output=True, text=True, timeout=120)

    def test_invalid_jobs_values_are_usage_errors_before_any_test_runs(self) -> None:
        for arguments in (("unit", "--jobs", "0"), ("unit", "--jobs", "many"), ("unit", "--jobs=-2"),
                          ("unit", "--jobs"), ("--jobs", "2"), ("other", "--jobs", "2")):
            with self.subTest(arguments=arguments):
                result = self.source(*arguments)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Usage: python tools/source.py test {unit,integration} [--jobs {N,auto}]",
                              result.stderr)
                self.assertNotIn("Ran ", result.stderr)


if __name__ == "__main__":
    unittest.main()
