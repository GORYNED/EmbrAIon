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
        if len(arguments) != 2 or arguments[1] not in {"unit", "integration"}:
            raise SystemExit("Usage: python tools/source.py test {unit,integration}")
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests" / arguments[1]))
        return 0 if unittest.TextTestRunner().run(suite).wasSuccessful() else 1

    # CLI development is an explicit checkout override; project commands retain
    # the self-host overlay and routing. Test processes above keep resolution on.
    os.environ["EMBRAION_HOME"] = str(ROOT)
    from embraion.cli import main as cli_main

    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
