from __future__ import annotations

import json
import signal
import subprocess
import sys
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from embraion.common import framework_root
from embraion.skill_evals import MAX_SUITE_BYTES, _check_output_destination, _digest, _grade, _load_suite, _reject_source_ancestors, _safe_relative, _source_files, _terminate_host, run_suite


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
    (root / 'answer.txt').symlink_to(root / 'input.txt')
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
        real_popen = subprocess.Popen

        def run_fake_with_python(argv, *args, **kwargs):
            if argv and argv[0] == str(self.host):
                argv = [sys.executable, *argv]
            return real_popen(argv, *args, **kwargs)

        popen_patch = patch("embraion.skill_evals.subprocess.Popen", side_effect=run_fake_with_python)
        popen_patch.start()
        self.addCleanup(popen_patch.stop)
        def can_symlink(target: Path, *, directory: bool) -> bool:
            probe = self.root / ("directory-symlink-probe" if directory else "file-symlink-probe")
            try:
                probe.symlink_to(target, target_is_directory=directory)
                return probe.is_symlink()
            except (OSError, NotImplementedError):
                return False
            finally:
                if probe.is_symlink():
                    try:
                        probe.unlink()
                    except OSError:
                        probe.rmdir()

        self.file_symlink_supported = can_symlink(fixture / "input.txt", directory=False)
        self.directory_symlink_supported = can_symlink(fixture, directory=True)

    def run_eval(self, **kwargs: object) -> dict:
        return run_suite(self.suite, host="codex", model="gpt-test", effort="high", attempts=2, output=self.root / "report.json", codex_binary=str(self.host), **kwargs)

    def test_v1_skill_suite_keeps_native_invocation_without_output_schema(self) -> None:
        with patch("embraion.skill_evals._invoke_codex", return_value={"status": "completed"}) as native:
            self.run_eval()
        self.assertTrue(native.called)
        self.assertTrue(all("output_schema" not in call.kwargs for call in native.call_args_list))

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
                    if mode == "symlink" and not self.file_symlink_supported:
                        continue
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
        for unsafe in ("../outside", "./fixture", "fixture/./file", "fixture//file", "fixture/../file", "C:/secret", "C:secret", "\\\\server\\share", "fixture\\..\\secret", "fixture\0bad"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    _safe_relative(unsafe)
        if self.file_symlink_supported:
            (self.root / "fixture" / "link").symlink_to(self.root / "fixture" / "input.txt")
            with self.assertRaises(ValueError):
                _source_files(self.root / "fixture")
            (self.root / "fixture" / "link").unlink()
        if self.directory_symlink_supported:
            (self.root / "fixture-link").symlink_to(self.root / "fixture", target_is_directory=True)
            with self.assertRaises(ValueError):
                _reject_source_ancestors(self.root / "fixture-link", self.root)
            self.data["cases"][0]["fixture"] = "fixture-link"
            self.suite.write_text(json.dumps(self.data), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_suite(self.suite, host="codex", model=None, effort=None, attempts=1, output=self.root / "report.json", codex_binary=str(self.host))

    def test_termination_uses_platform_appropriate_process_api(self) -> None:
        process = Mock(pid=123)
        with patch("embraion.skill_evals.os.killpg", create=True) as kill_group:
            with patch("embraion.skill_evals.signal.SIGKILL", 9, create=True):
                _terminate_host(process, windows=True)
                process.kill.assert_called_once_with()
                kill_group.assert_not_called()
                process.kill.reset_mock()
                _terminate_host(process, windows=False)
                process.kill.assert_not_called()
                kill_group.assert_called_once_with(123, signal.SIGKILL)

    def test_grader_checks_actual_files(self) -> None:
        root = self.root / "fixture"
        before = {"input.txt": _digest(root)}
        checks = [{"type": "file-exists", "path": "missing.txt"}, {"type": "file-absent", "path": "missing.txt"}, {"type": "json-field-equals", "path": "input.txt", "field": "a", "value": 1}]
        self.assertEqual([False, True, False], [item["passed"] for item in _grade(root, before, checks)])

    def test_real_suite_validates(self) -> None:
        suite = _load_suite(framework_root() / "evals/skills/code-organization.json")
        self.assertEqual({"positive", "negative"}, {case["polarity"] for case in suite["cases"]})
        self.assertEqual(4, len(suite["cases"]))

    def test_invalid_suite_errors_do_not_echo_prompt_payload(self) -> None:
        canary = "PRIVATE_PROMPT_CANARY_7421"
        self.data["cases"][0]["prompt"] = canary
        self.data["cases"][0]["polarity"] = "invalid"
        self.suite.write_text(json.dumps(self.data), encoding="utf-8")
        try:
            _load_suite(self.suite)
        except ValueError:
            rendered = traceback.format_exc()
        else:
            self.fail("invalid suite was accepted")
        self.assertNotIn(canary, rendered)
        self.assertIn("invalid skill evaluation suite schema", rendered)

        self.suite.write_text('{"prompt": "' + canary + '",', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid skill evaluation suite JSON"):
            _load_suite(self.suite)
        self.suite.write_bytes(b" " * (MAX_SUITE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "exceeds size limit"):
            _load_suite(self.suite)

    def test_output_source_aliases_rejected_before_host_run(self) -> None:
        fixture_file = self.root / "fixture" / "input.txt"
        skill_file = framework_root() / "core/skills/code-organization/SKILL.md"
        originals = {path: path.read_bytes() for path in (self.suite, fixture_file, skill_file)}
        destinations = [self.suite, fixture_file, skill_file]
        if self.file_symlink_supported:
            alias = self.root / "suite-alias.json"
            alias.symlink_to(self.suite)
            destinations.append(alias)
        if self.directory_symlink_supported:
            alias_dir = self.root / "fixture-alias"
            alias_dir.symlink_to(self.root / "fixture", target_is_directory=True)
            destinations.append(alias_dir / "report.json")
        with patch("embraion.skill_evals._invoke_codex") as invoke:
            for destination in destinations:
                with self.subTest(destination=destination):
                    with self.assertRaises(ValueError):
                        run_suite(self.suite, host="codex", model=None, effort=None, attempts=1, output=destination, codex_binary=str(self.host))
            invoke.assert_not_called()
        self.assertEqual(originals, {path: path.read_bytes() for path in originals})

    def test_output_allows_system_alias_above_owner_but_rejects_link_inside(self) -> None:
        if not self.directory_symlink_supported:
            return
        sources = [self.root / "fixture", framework_root() / "core/skills/code-organization"]
        with tempfile.TemporaryDirectory(dir=self.root.parent) as outer:
            alias = Path(outer) / "system-alias"
            alias.symlink_to(self.root.parent, target_is_directory=True)
            with patch("embraion.skill_evals.tempfile.gettempdir", return_value=str(self.root / "not-the-system-temp-root")):
                _check_output_destination(alias / self.root.name / "report.json", self.suite, sources)
        reports = self.root / "reports"
        reports.mkdir()
        internal_alias = self.root / "internal-alias"
        internal_alias.symlink_to(reports, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "contains a symlink"):
            _check_output_destination(internal_alias / "report.json", self.suite, sources)
        cross_owner_alias = self.root / "cross-owner-alias"
        cross_owner_alias.symlink_to(framework_root(), target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "contains a symlink"):
            _check_output_destination(cross_owner_alias / "report.json", self.suite, sources)

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
