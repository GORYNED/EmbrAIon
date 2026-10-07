from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("parallel_tests_under_test", ROOT / "tools" / "parallel_tests.py")
parallel = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = parallel
_SPEC.loader.exec_module(parallel)


def write_suite(directory: Path, prefix: str) -> None:
    (directory / f"{prefix}_alpha.py").write_text(
        "import unittest\n"
        "class Alpha(unittest.TestCase):\n"
        "    def test_one(self): pass\n"
        "    def test_two(self): pass\n"
        "    @unittest.skip('reason')\n"
        "    def test_skipped(self): pass\n",
        encoding="utf-8",
    )
    (directory / f"{prefix}_beta.py").write_text(
        "import unittest\n"
        "class Beta(unittest.TestCase):\n"
        "    def test_fails(self): self.assertEqual(1, 2)\n"
        "    def test_errors(self): raise RuntimeError('boom')\n"
        "    def test_passes(self): pass\n",
        encoding="utf-8",
    )
    (directory / f"{prefix}_broken.py").write_text("raise ImportError('missing dependency')\n", encoding="utf-8")
    (directory / f"{prefix}_optional.py").write_text(
        "import unittest\nraise unittest.SkipTest('optional dependency missing')\n", encoding="utf-8")


class SuiteFixture(unittest.TestCase):
    def make_suite(self, prefix: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        write_suite(directory, prefix)
        original_path = list(sys.path)
        original_modules = set(sys.modules)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        self.addCleanup(lambda: [sys.modules.pop(name) for name in set(sys.modules) - original_modules])
        return directory


class ResolveJobsTests(unittest.TestCase):
    def test_auto_uses_cpu_count_capped_at_four(self) -> None:
        self.assertEqual(1, parallel.resolve_jobs("auto", 1))
        self.assertEqual(2, parallel.resolve_jobs("auto", 2))
        self.assertEqual(4, parallel.resolve_jobs("auto", 4))
        self.assertEqual(4, parallel.resolve_jobs("auto", 64))

    def test_auto_survives_an_unknown_cpu_count(self) -> None:
        self.assertGreaterEqual(parallel.resolve_jobs("auto", None), 1)

    def test_positive_integers_are_taken_as_given(self) -> None:
        self.assertEqual(1, parallel.resolve_jobs("1"))
        self.assertEqual(8, parallel.resolve_jobs("8"))

    def test_invalid_values_are_errors(self) -> None:
        for value in ("0", "-1", "", "x", "1.5", "AUTO", " 2", "٣"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parallel.resolve_jobs(value)


class PlanningTests(SuiteFixture):
    def test_counts_group_tests_by_module_and_name_broken_imports(self) -> None:
        directory = self.make_suite("test_plan")
        suite = unittest.TestLoader().discover(str(directory))
        counts = parallel.count_by_module(suite)
        self.assertEqual({"test_plan_alpha": 3, "test_plan_beta": 3, "test_plan_broken": 1, "test_plan_optional": 1}, counts)
        self.assertEqual(suite.countTestCases(), sum(counts.values()))

    def test_order_is_largest_first_with_name_ties(self) -> None:
        sizes = {"b": 10, "a": 10, "c": 99, "d": 1}
        self.assertEqual(["c", "a", "b", "d"], parallel.order_modules(["d", "b", "a", "c"], sizes))
        self.assertEqual(["x", "y"], parallel.order_modules(["y", "x"], {}))

    def test_sequential_allowlist_splits_named_modules(self) -> None:
        parallel_set, pinned = parallel.split_sequential(["a", "b", "c"], {"b": "shares a fixed path"})
        self.assertEqual((["a", "c"], ["b"]), (parallel_set, pinned))
        self.assertEqual((["a"], []), parallel.split_sequential(["a"], {}))

    def test_allowlist_names_a_reason_for_every_module(self) -> None:
        for suite, modules in parallel.SEQUENTIAL_MODULES.items():
            self.assertIn(suite, {"unit", "integration"})
            for module, reason in modules.items():
                self.assertTrue(module.startswith("test_") and reason.strip(), module)

    def test_allowlisted_modules_exist_in_their_suite(self) -> None:
        for suite, modules in parallel.SEQUENTIAL_MODULES.items():
            for module in modules:
                self.assertTrue((ROOT / "tests" / suite / f"{module}.py").is_file(), (suite, module))

    def test_module_size_reads_the_file_and_tolerates_missing_files(self) -> None:
        directory = self.make_suite("test_size")
        self.assertGreater(parallel.module_size(directory, "test_size_alpha"), 0)
        self.assertEqual(0, parallel.module_size(directory, "test_size_absent"))


class ExecutionTests(SuiteFixture):
    def test_execute_modules_reports_counts_and_only_failure_details(self) -> None:
        directory = self.make_suite("test_exec")
        payload = parallel.execute_modules(directory, ["test_exec_alpha", "test_exec_beta", "test_exec_broken",
                                                      "test_exec_optional"])
        self.assertEqual(
            {"ran": 8, "failures": 1, "errors": 2, "skipped": 2, "expected_failures": 0, "unexpected_successes": 0},
            {key: payload[key] for key in ("ran", "failures", "errors", "skipped", "expected_failures",
                                           "unexpected_successes")},
        )
        report = payload["report"]
        self.assertIn("FAIL: test_fails", report)
        self.assertIn("RuntimeError: boom", report)
        self.assertIn("missing dependency", report)
        self.assertNotIn("\nRan ", report)

    def test_extract_failure_report_drops_dots_and_totals(self) -> None:
        text = ".F\n" + "=" * 70 + "\nFAIL: x\n" + "-" * 70 + "\nTraceback\n\n" + "-" * 70 + "\nRan 2 tests in 0.0s\n\nFAILED\n"
        self.assertEqual("=" * 70 + "\nFAIL: x\n" + "-" * 70 + "\nTraceback", parallel.extract_failure_report(text))
        self.assertEqual("", parallel.extract_failure_report("..\n" + "-" * 70 + "\nRan 2 tests in 0.0s\n\nOK\n"))


class AggregationTests(unittest.TestCase):
    def result(self, module: str, slot: int, **fields) -> object:
        return parallel.ModuleResult(module=module, slot=slot, **fields)

    def test_combine_adds_every_counter(self) -> None:
        totals = parallel.combine([
            self.result("a", 1, ran=3, failures=1, skipped=1),
            self.result("b", 2, ran=4, errors=2, expected_failures=1, unexpected_successes=1),
        ])
        self.assertEqual(
            {"ran": 7, "failures": 1, "errors": 2, "skipped": 1, "expected_failures": 1, "unexpected_successes": 1},
            totals,
        )

    def test_verdict_matches_the_unittest_vocabulary(self) -> None:
        clean = parallel.combine([])
        self.assertEqual("OK", parallel.verdict(clean))
        skipped = parallel.combine([self.result("a", 1, ran=2, skipped=2)])
        self.assertEqual("OK (skipped=2)", parallel.verdict(skipped))
        failed = parallel.combine([self.result("a", 1, ran=5, failures=1, errors=2, skipped=1)])
        self.assertEqual("FAILED (failures=1, errors=2, skipped=1)", parallel.verdict(failed))

    def test_crashes_count_mismatches_and_unexpected_successes_fail_the_run(self) -> None:
        clean = parallel.combine([])
        self.assertEqual("FAILED (crashed-modules=1)", parallel.verdict(clean, crashed=1))
        self.assertEqual("FAILED (test-count-mismatch=1)", parallel.verdict(clean, count_mismatch=True))
        unexpected = parallel.combine([self.result("a", 1, ran=1, unexpected_successes=1)])
        self.assertTrue(parallel.verdict(unexpected).startswith("FAILED"))

    def test_success_property_requires_no_failure_and_no_crash(self) -> None:
        self.assertTrue(self.result("a", 1, ran=1, skipped=1).successful)
        self.assertFalse(self.result("a", 1, failures=1).successful)
        self.assertFalse(self.result("a", 1, errors=1).successful)
        self.assertFalse(self.result("a", 1, crashed=True).successful)

    def test_slot_summaries_cover_every_slot_and_the_parent(self) -> None:
        results = [
            self.result("a", 1, ran=3, seconds=1.0),
            self.result("b", 1, ran=2, seconds=0.5, failures=1),
            self.result("c", 0, ran=1, seconds=2.0),
        ]
        lines = parallel.slot_summaries(results, [1, 2, 0])
        self.assertEqual(
            [
                "process 1: 2 modules, 5 tests, 1.5s, FAILED (failures=1)",
                "process 2: 0 modules, 0 tests, 0.0s, OK",
                "parent (sequential): 1 modules, 1 tests, 2.0s, OK",
            ],
            lines,
        )

    def test_payload_round_trip_defaults_missing_counters_to_zero(self) -> None:
        result = parallel.result_from_payload("m", 3, {"ran": 4, "seconds": 1.5, "report": "r"})
        self.assertEqual(("m", 3, 4, 0, 1.5, "r"),
                         (result.module, result.slot, result.ran, result.failures, result.seconds, result.report))


class PoolTests(unittest.TestCase):
    def test_every_module_runs_once_on_a_bounded_set_of_slots(self) -> None:
        modules = [f"m{index}" for index in range(12)]
        guard = threading.Lock()
        running = {"now": 0, "peak": 0}
        seen: list[tuple[int, str]] = []
        reported: list[str] = []

        def launch(slot: int, module: str):
            with guard:
                running["now"] += 1
                running["peak"] = max(running["peak"], running["now"])
                seen.append((slot, module))
            time.sleep(0.01)
            with guard:
                running["now"] -= 1
            return parallel.ModuleResult(module=module, slot=slot, ran=1)

        results = parallel.run_pool(modules, 3, launch, lambda result: reported.append(result.module))
        self.assertEqual(modules, [result.module for result in results])
        self.assertEqual(sorted(modules), sorted(module for _, module in seen))
        self.assertEqual(sorted(modules), sorted(reported))
        self.assertLessEqual(running["peak"], 3)
        self.assertLessEqual({slot for slot, _ in seen}, {1, 2, 3})

    def test_a_slot_is_never_used_by_two_modules_at_once(self) -> None:
        guard = threading.Lock()
        busy: set[int] = set()
        clashes: list[int] = []

        def launch(slot: int, module: str):
            with guard:
                if slot in busy:
                    clashes.append(slot)
                busy.add(slot)
            time.sleep(0.005)
            with guard:
                busy.discard(slot)
            return parallel.ModuleResult(module=module, slot=slot, ran=1)

        parallel.run_pool([f"m{index}" for index in range(20)], 4, launch)
        self.assertEqual([], clashes)

    def test_a_failing_launch_aborts_without_waiting_for_running_modules(self) -> None:
        release = threading.Event()
        started = threading.Event()
        aborted: list[bool] = []

        def launch(slot: int, module: str):
            if module == "bad":
                started.wait(5)
                raise RuntimeError("launch failed")
            started.set()
            release.wait(10)
            return parallel.ModuleResult(module=module, slot=slot, ran=1)

        begun = time.perf_counter()
        try:
            with self.assertRaises(RuntimeError):
                parallel.run_pool(["blocked", "bad", "never"], 2, launch, on_abort=lambda: aborted.append(True))
            self.assertLess(time.perf_counter() - begun, 5)
            self.assertEqual([True], aborted)
        finally:
            release.set()

    def test_total_ran_equals_the_sum_of_modules(self) -> None:
        counts = {"a": 5, "b": 7, "c": 1}
        results = parallel.run_pool(
            list(counts), 2, lambda slot, module: parallel.ModuleResult(module=module, slot=slot, ran=counts[module])
        )
        self.assertEqual(sum(counts.values()), parallel.combine(results)["ran"])


if __name__ == "__main__":
    unittest.main()
