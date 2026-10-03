from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root
from embraion.skill_evals import _digest, _grade, _load_suite, _source_files, run_suite


FAKE_HOST = '''#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv
root = Path(args[args.index('--cd') + 1])
prompt = sys.stdin.read()
mode = os.getenv('FAKE_MODE', 'success')
if mode == 'timeout':
    time.sleep(10)
if mode == 'invalid':
    print('invalid json', flush=True)
    raise SystemExit(0)
if mode == 'large':
    print('x' * 3000000, flush=True)
    time.sleep(10)
if mode == 'failed':
    print(json.dumps({'type':'turn.failed'}), flush=True)
    raise SystemExit(1)
if mode != 'no-read' and (root / '.agents/skills/code-organization/SKILL.md').is_file():
    print(json.dumps({'type':'item.started','item':{'type':'command_execution','command':'cat .agents/skills/code-organization/SKILL.md'}}), flush=True)
    print(json.dumps({'type':'item.completed','item':{'type':'command_execution','command':'cat .agents/skills/code-organization/SKILL.md','exit_code':0}}), flush=True)
if 'edit' in prompt:
    (root / 'answer.txt').write_text('done', encoding='utf-8')
if mode == 'symlink':
    (root / 'answer.txt').unlink()
    (root / 'answer.txt').symlink_to('/etc/passwd')
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':7}}), flush=True)
'''


class SkillEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = self.root / "fixture"
        fixture.mkdir()
        (fixture / "input.txt").write_text("original", encoding="utf-8")
        self.suite = self.root / "suite.json"
        self.data = {
            "schema-version": 1,
            "id": "unit-suite",
            "skills": [{"id": "code-organization", "candidate": "core/skills/code-organization"}],
            "cases": [{"id": "edit", "polarity": "positive", "fixture": "fixture", "prompt": "edit answer", "checks": [{"type": "file-contains", "path": "answer.txt", "text": "done"}, {"type": "unchanged-path", "path": "input.txt"}]}],
        }
        self.suite.write_text(json.dumps(self.data), encoding="utf-8")
        self.host = self.root / "fake-host"
        self.host.write_text(FAKE_HOST, encoding="utf-8")
        self.host.chmod(0o755)

    def run_eval(self, **kwargs: object) -> dict:
        return run_suite(self.suite, host="codex", model="gpt-test", effort="high", attempts=2, output=self.root / "report.json", codex_binary=str(self.host), **kwargs)

    def test_paired_attempts_and_privacy_minimal_report(self) -> None:
        digest = _digest(self.root / "fixture")
        report = self.run_eval()
        self.assertEqual({"total": 2, "behavior-passed": 2}, report["summary"]["baseline"])
        self.assertEqual({"total": 2, "behavior-passed": 2}, report["summary"]["candidate"])
        self.assertEqual(4, len(report["runs"]))
        self.assertEqual(["tied-pass", "tied-pass"], [pair["candidate-vs"]["baseline"] for pair in report["pairs"]])
        self.assertEqual("read-observed", report["runs"][1]["trigger-evidence"]["code-organization"])
        self.assertEqual("unverified", report["runs"][0]["trigger-evidence"]["code-organization"])
        self.assertEqual(12, report["runs"][1]["host"]["tokens"]["input_tokens"])
        self.assertEqual(digest, _digest(self.root / "fixture"))
        saved = (self.root / "report.json").read_text(encoding="utf-8")
        self.assertNotIn("edit answer", saved)
        self.assertNotIn("original", saved)
        self.assertNotIn("cat .agents", saved)

    def test_host_failures_do_not_pass_behavior(self) -> None:
        import os

        prior = os.environ.get("FAKE_MODE")
        try:
            for mode, expected in (("invalid", "invalid-host-events"), ("failed", "host-failed"), ("large", "output-limit"), ("timeout", "timeout"), ("symlink", "grading-error")):
                with self.subTest(mode=mode):
                    os.environ["FAKE_MODE"] = mode
                    report = run_suite(self.suite, host="codex", model=None, effort=None, attempts=1, output=self.root / "report.json", codex_binary=str(self.host), timeout_seconds=1)
                    self.assertEqual(expected, report["runs"][0]["host"]["status"])
                    self.assertFalse(report["runs"][0]["behavior-passed"])
        finally:
            if prior is None:
                os.environ.pop("FAKE_MODE", None)
            else:
                os.environ["FAKE_MODE"] = prior

    def test_rejects_unsafe_paths_and_symlinks(self) -> None:
        self.data["cases"][0]["fixture"] = "../outside"
        self.suite.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaises(ValueError):
            _load_suite(self.suite)
        (self.root / "fixture" / "link").symlink_to(self.root / "outside")
        with self.assertRaises(ValueError):
            _source_files(self.root / "fixture")

    def test_grader_checks_actual_files(self) -> None:
        root = self.root / "fixture"
        before = {"input.txt": _digest(root)}
        checks = [{"type": "file-exists", "path": "missing.txt"}, {"type": "file-absent", "path": "missing.txt"}, {"type": "json-field-equals", "path": "input.txt", "field": "a", "value": 1}]
        self.assertEqual([False, True, False], [item["passed"] for item in _grade(root, before, checks)])

    def test_real_suite_validates(self) -> None:
        suite = _load_suite(framework_root() / "evals/skills/code-organization.json")
        self.assertEqual({"positive", "negative"}, {case["polarity"] for case in suite["cases"]})
        self.assertEqual(4, len(suite["cases"]))

    def test_composed_skills_with_previous_variant_and_unverified_trigger(self) -> None:
        import os

        self.data["skills"].append({"id": "implementation", "candidate": "core/skills/implementation", "previous": "core/skills/implementation"})
        self.data["skills"][0]["previous"] = "core/skills/code-organization"
        self.suite.write_text(json.dumps(self.data), encoding="utf-8")
        prior = os.environ.get("FAKE_MODE")
        os.environ["FAKE_MODE"] = "no-read"
        try:
            report = run_suite(self.suite, host="codex", model=None, effort=None, attempts=1, output=self.root / "report.json", codex_binary=str(self.host))
        finally:
            if prior is None:
                os.environ.pop("FAKE_MODE", None)
            else:
                os.environ["FAKE_MODE"] = prior
        self.assertEqual({"baseline", "candidate", "previous"}, {run["variant"] for run in report["runs"]})
        self.assertEqual({"code-organization", "implementation"}, set(report["skill-identities"]))
        self.assertEqual(1, report["pair-summary"]["previous"]["tied-pass"])
        self.assertEqual({"unverified"}, set(report["runs"][1]["trigger-evidence"].values()))


if __name__ == "__main__":
    unittest.main()
