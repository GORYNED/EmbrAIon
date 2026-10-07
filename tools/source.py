"""Run framework development commands from this checkout, independently of its pin."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not (ROOT / "tools/cli/embraion/cli.py").is_file():
        raise SystemExit("Source commands require an EmbrAIon source checkout.")
    # Prefer the checkout's development environment when invoked by a global CLI.
    # CI uses its installed dependencies when no local environment exists.
    development = ROOT / ".venv"
    python = development / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.is_file() and Path(sys.prefix).resolve() != development.resolve():
        return subprocess.call([str(python), str(Path(__file__).resolve()), *arguments])

    os.chdir(ROOT)
    source = str(ROOT / "tools/cli")
    sys.path.insert(0, source)
    from embraion.environment import child_environment

    environment = child_environment()
    # This entry point explicitly chooses source even under an older pinned CLI.
    environment.pop("EMBRAION_HOME", None)
    environment.pop("EMBRAION_DISABLE_VERSION_RESOLUTION", None)
    environment["PYTHONPATH"] = source
    os.environ.clear()
    os.environ.update(environment)

    if arguments[:1] == ["test"]:
        usage = "Usage: python tools/source.py test {unit,integration} [--jobs {N,auto}]"
        options = arguments[1:]
        jobs = None
        if len(options) == 3 and options[1] == "--jobs":
            jobs = options[2]
            options = options[:1]
        elif len(options) == 2 and options[1].startswith("--jobs="):
            jobs = options[1].partition("=")[2]
            options = options[:1]
        if len(options) != 1 or options[0] not in {"unit", "integration"}:
            raise SystemExit(usage)
        suite_dir = ROOT / "tests" / options[0]
        if jobs is not None:
            # The parallel runner is loaded only on request: the default run stays unchanged.
            tools = str(Path(__file__).resolve().parent)
            if tools not in sys.path:
                sys.path.insert(0, tools)
            import parallel_tests

            try:
                count = parallel_tests.resolve_jobs(jobs)
            except ValueError as error:
                raise SystemExit(f"{error}\n{usage}") from None
            if count > 1:
                return parallel_tests.run_parallel(options[0], suite_dir, count)
        suite = unittest.defaultTestLoader.discover(str(suite_dir))
        return 0 if unittest.TextTestRunner().run(suite).wasSuccessful() else 1

    # CLI development is an explicit checkout override; project commands retain
    # the self-host overlay and routing. Test processes above keep resolution on.
    os.environ["EMBRAION_HOME"] = str(ROOT)
    from embraion.cli import main as cli_main

    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
