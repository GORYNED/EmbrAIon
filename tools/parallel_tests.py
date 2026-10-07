"""Run the source test suites in parallel worker processes.

``tools/source.py test {unit,integration} --jobs N`` imports this module. The default
sequential run does not use it. Each test module runs in its own short-lived process.
A pool of N slots pulls modules from a queue, largest files first, so no slot idles
while others still hold slow modules. Every slot has its own temporary directory, so
tests that use the system temporary directory cannot collide.

The parent discovers the suite once. It fails the run when the worker processes do not
run exactly the number of tests that discovery found.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Callable, Iterable, Iterator, Mapping, Sequence
import unittest


MAX_AUTO_JOBS = 4
SEPARATOR = "-" * 70
LOG_TAIL_LINES = 40

# Modules that must not share a machine with parallel test processes run one after the
# other in the parent process, after the parallel phase. Keep this empty unless a module
# cannot be made isolated; name each module and say why. Keys are suite names
# ("unit", "integration"), values map a module name to its reason.
SEQUENTIAL_MODULES: dict[str, dict[str, str]] = {}


@dataclass
class ModuleResult:
    module: str
    slot: int
    ran: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    expected_failures: int = 0
    unexpected_successes: int = 0
    seconds: float = 0.0
    report: str = ""
    log: str = ""
    crashed: bool = False

    @property
    def successful(self) -> bool:
        return not (self.crashed or self.failures or self.errors or self.unexpected_successes)


def resolve_jobs(value: str, cpu_count: int | None = None) -> int:
    """Return the worker count for ``--jobs``: a positive integer or ``auto``."""
    if value == "auto":
        return max(1, min(cpu_count or os.cpu_count() or 1, MAX_AUTO_JOBS))
    if not value.isascii() or not value.isdigit() or int(value) < 1:
        raise ValueError(f"--jobs must be a positive integer or 'auto', not {value!r}")
    return int(value)


def _walk(suite: unittest.TestSuite | unittest.TestCase) -> Iterator[unittest.TestCase]:
    if isinstance(suite, unittest.TestSuite):
        for child in suite:
            yield from _walk(child)
    else:
        yield suite


def count_by_module(suite: unittest.TestSuite) -> dict[str, int]:
    """Count the discovered tests per module, in discovery order."""
    counts: dict[str, int] = {}
    for test in _walk(suite):
        if type(test).__name__ == "_FailedTest":
            # A module that fails to import is reported by name; rerunning it reports it again.
            module = test._testMethodName
        else:
            module = type(test).__module__
        counts[module] = counts.get(module, 0) + 1
    return counts


def module_size(suite_dir: Path, module: str) -> int:
    path = suite_dir.joinpath(*module.split(".")).with_suffix(".py")
    try:
        return path.stat().st_size
    except OSError:
        return 0


def order_modules(modules: Iterable[str], sizes: Mapping[str, int]) -> list[str]:
    """Order modules largest first (a cheap proxy for run time), ties by name."""
    return sorted(modules, key=lambda module: (-sizes.get(module, 0), module))


def split_sequential(modules: Sequence[str], sequential: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """Split modules into the parallel set and the named sequential-in-parent set."""
    parallel = [module for module in modules if module not in sequential]
    pinned = [module for module in modules if module in sequential]
    return parallel, pinned


def extract_failure_report(text: str) -> str:
    """Keep the failure details of a unittest text report and drop dots and totals."""
    marker = "=" * 70
    start = text.find(marker)
    if start < 0:
        return ""
    end = text.rfind("\n" + SEPARATOR + "\nRan ")
    return text[start:end if end > start else len(text)].strip("\n")


def execute_modules(suite_dir: Path, modules: Sequence[str]) -> dict[str, object]:
    """Run modules in this process and return the counts as a JSON-ready mapping."""
    path = str(suite_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
    suite = unittest.defaultTestLoader.loadTestsFromNames(list(modules))
    stream = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream).run(suite)
    return {
        "ran": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "seconds": time.perf_counter() - started,
        "report": extract_failure_report(stream.getvalue()),
    }


def _tail(text: str, lines: int = LOG_TAIL_LINES) -> str:
    return "\n".join(text.rstrip("\n").splitlines()[-lines:])


def result_from_payload(module: str, slot: int, payload: Mapping[str, object]) -> ModuleResult:
    return ModuleResult(
        module=module,
        slot=slot,
        ran=int(payload.get("ran", 0)),  # type: ignore[call-overload]
        failures=int(payload.get("failures", 0)),  # type: ignore[call-overload]
        errors=int(payload.get("errors", 0)),  # type: ignore[call-overload]
        skipped=int(payload.get("skipped", 0)),  # type: ignore[call-overload]
        expected_failures=int(payload.get("expected_failures", 0)),  # type: ignore[call-overload]
        unexpected_successes=int(payload.get("unexpected_successes", 0)),  # type: ignore[call-overload]
        seconds=float(payload.get("seconds", 0.0)),  # type: ignore[arg-type]
        report=str(payload.get("report", "")),
    )


def combine(results: Sequence[ModuleResult]) -> dict[str, int]:
    keys = ("ran", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")
    return {key: sum(getattr(result, key) for result in results) for key in keys}


def verdict(totals: Mapping[str, int], crashed: int = 0, count_mismatch: bool = False) -> str:
    """Format the last line like ``unittest`` and add crashed-process and count failures."""
    details = []
    for key, label in (("failures", "failures"), ("errors", "errors")):
        if totals[key]:
            details.append(f"{label}={totals[key]}")
    if crashed:
        details.append(f"crashed-modules={crashed}")
    if count_mismatch:
        details.append("test-count-mismatch=1")
    for key, label in (("skipped", "skipped"), ("expected_failures", "expected failures"),
                       ("unexpected_successes", "unexpected successes")):
        if totals[key]:
            details.append(f"{label}={totals[key]}")
    failed = bool(totals["failures"] or totals["errors"] or totals["unexpected_successes"]
                  or crashed or count_mismatch)
    if failed:
        return f"FAILED ({', '.join(details)})"
    return f"OK ({', '.join(details)})" if details else "OK"


def slot_summaries(results: Sequence[ModuleResult], slots: Sequence[int]) -> list[str]:
    lines = []
    for slot in slots:
        mine = [result for result in results if result.slot == slot]
        label = "parent (sequential)" if slot == 0 else f"process {slot}"
        totals = combine(mine)
        crashed = sum(1 for result in mine if result.crashed)
        lines.append(
            f"{label}: {len(mine)} modules, {totals['ran']} tests, "
            f"{sum(result.seconds for result in mine):.1f}s, {verdict(totals, crashed)}"
        )
    return lines


Launcher = Callable[[int, str], ModuleResult]


def run_pool(modules: Sequence[str], jobs: int, launch: Launcher,
             report: Callable[[ModuleResult], None] | None = None) -> list[ModuleResult]:
    """Run each module once on a pool of ``jobs`` slots numbered 1..jobs."""
    slots: queue.Queue[int] = queue.Queue()
    for slot in range(1, jobs + 1):
        slots.put(slot)

    def task(module: str) -> ModuleResult:
        slot = slots.get()
        try:
            result = launch(slot, module)
        finally:
            slots.put(slot)
        if report is not None:
            report(result)
        return result

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(task, modules))


def _launch_process(suite_dir: Path, work: Path, environment: Mapping[str, str],
                    active: set, guard: threading.Lock) -> Launcher:
    def launch(slot: int, module: str) -> ModuleResult:
        temporary = work / f"slot-{slot}"
        temporary.mkdir(exist_ok=True)
        stem = f"{slot}-{module}"
        result_path = work / f"{stem}.json"
        log_path = work / f"{stem}.log"
        child = dict(environment)
        for name in ("TMPDIR", "TEMP", "TMP"):
            child[name] = str(temporary)
        command = [sys.executable, str(Path(__file__).resolve()), "--worker",
                   str(suite_dir), str(result_path), module]
        started = time.perf_counter()
        with log_path.open("wb") as log:
            process = subprocess.Popen(command, env=child, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT)
            with guard:
                active.add(process)
            try:
                code = process.wait()
            finally:
                with guard:
                    active.discard(process)
        text = log_path.read_text(encoding="utf-8", errors="replace")
        elapsed = time.perf_counter() - started
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ModuleResult(module=module, slot=slot, seconds=elapsed, crashed=True,
                                report=f"Worker exited with status {code} without a result.",
                                log=_tail(text))
        result = result_from_payload(module, slot, payload)
        if not result.successful or code:
            result.log = _tail(text)
        return result

    return launch


def run_parallel(suite_name: str, suite_dir: Path, jobs: int) -> int:
    """Discover ``suite_dir``, run its modules on ``jobs`` processes, and return an exit code."""
    if hasattr(sys.stdout, "reconfigure"):
        # Failure reports may contain characters a legacy console encoding cannot show.
        sys.stdout.reconfigure(errors="backslashreplace")
    suite_path = str(suite_dir)
    if suite_path not in sys.path:
        sys.path.insert(0, suite_path)
    suite = unittest.defaultTestLoader.discover(suite_path)
    counts = count_by_module(suite)
    expected = sum(counts.values())
    sizes = {module: module_size(suite_dir, module) for module in counts}
    parallel, pinned = split_sequential(order_modules(counts, sizes),
                                        SEQUENTIAL_MODULES.get(suite_name, {}))
    print(f"Running {expected} {suite_name} tests from {len(counts)} modules on {jobs} processes"
          + (f"; {len(pinned)} sequential in the parent: {', '.join(pinned)}" if pinned else ""),
          flush=True)

    started = time.perf_counter()
    work = Path(tempfile.mkdtemp(prefix="embraion-tests-"))
    active: set = set()
    guard = threading.Lock()
    printed = threading.Lock()
    finished = 0
    total = len(counts)

    def progress(result: ModuleResult) -> None:
        nonlocal finished
        with printed:
            finished += 1
            state = "ok" if result.successful else "FAILED"
            print(f"[{finished}/{total}] {state} {result.module}: {result.ran} tests, "
                  f"{result.seconds:.1f}s (process {result.slot})", flush=True)

    results: list[ModuleResult] = []
    try:
        launch = _launch_process(suite_dir, work, os.environ, active, guard)
        try:
            results.extend(run_pool(parallel, jobs, launch, progress))
        except BaseException:
            with guard:
                for process in list(active):
                    process.kill()
            raise
        for module in pinned:
            try:
                payload = execute_modules(suite_dir, [module])
                result = result_from_payload(module, 0, payload)
            except Exception as error:  # report a harness failure as a crashed module
                result = ModuleResult(module=module, slot=0, crashed=True,
                                      report=f"Sequential run raised {error!r}.")
            results.append(result)
            progress(result)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    elapsed = time.perf_counter() - started

    for result in results:
        if result.successful:
            continue
        print("\n" + "#" * 70)
        print(f"# {result.module} (process {result.slot})")
        if result.report:
            print(result.report)
        if result.log:
            print(f"--- captured process output (last {LOG_TAIL_LINES} lines) ---")
            print(result.log)
    print()
    print("\n".join(slot_summaries(results, list(range(1, jobs + 1)) + ([0] if pinned else []))))
    totals = combine(results)
    crashed = sum(1 for result in results if result.crashed)
    mismatch = totals["ran"] != expected
    print(SEPARATOR)
    print(f"Ran {totals['ran']} tests in {elapsed:.3f}s ({jobs} processes, {len(results)} modules)")
    if mismatch:
        print(f"Test count mismatch: discovery found {expected} tests, the processes ran {totals['ran']}.")
    else:
        print(f"Test count matches discovery: {expected}.")
    print()
    line = verdict(totals, crashed, mismatch)
    print(line)
    return 0 if line.startswith("OK") else 1


def main(argv: Sequence[str]) -> int:
    if len(argv) >= 4 and argv[0] == "--worker":
        suite_dir, result_path, modules = Path(argv[1]), Path(argv[2]), argv[3:]
        payload = execute_modules(suite_dir, modules)
        Path(result_path).write_text(json.dumps(payload), encoding="utf-8")
        return 0
    raise SystemExit("This module is the worker entry point of tools/source.py test --jobs.")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
