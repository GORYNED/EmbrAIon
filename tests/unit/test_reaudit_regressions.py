"""Adversarial follow-up fixtures; never touch real worktrees or provider APIs."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from embraion.common import framework_root, read_json, read_yaml, write_json, write_yaml
from embraion.evidence import start_run, complete_run, read_run
from embraion.enforcement import check_enforcement
from embraion.learning import observe, transition
from embraion.project import init_project, install, _projection_state_path
from test_audit_regressions import git
import test_mixed_execution as mixed


class ReauditRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def symlink(self, link, target):
        try:
            link.symlink_to(target)
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")

    def test_metadata_temp_aliases_never_write_outside(self):
        project = self.root / 'project'
        init_project(project, name='Fixture')
        state = _projection_state_path(project, 'codex')
        state.parent.mkdir(parents=True)
        outside = self.root / 'external'
        outside.write_text('preserve')
        temp = state.with_suffix('.json.tmp')
        self.symlink(temp, outside)
        install('codex', project, components=['config'])
        self.assertEqual('preserve', outside.read_text())
        self.assertFalse(state.is_symlink())
        self.assertTrue(temp.is_symlink())
        self.assertEqual('codex', read_json(state)['host'])

    def test_json_yaml_atomic_writes_preserve_linked_external_files(self):
        for writer, suffix in ((write_json, '.json'), (write_yaml, '.yaml')):
            with self.subTest(suffix=suffix):
                target = self.root / ('target' + suffix)
                outside = self.root / ('outside' + suffix)
                outside.write_text('preserve')
                self.symlink(target.with_suffix(suffix + '.tmp'), outside)
                os.link(outside, target)
                writer(target, {'value': 'new'})
                self.assertEqual('preserve', outside.read_text())
                self.assertFalse(target.samefile(outside))

    def test_projection_hardlinks_replace_inode_in_merge_and_force_modes(self):
        for mode in ('merge', 'replace'):
            project = self.root / mode
            init_project(project, name='Fixture')
            target = project / '.codex/config.toml'
            target.parent.mkdir()
            outside = self.root / (mode + '.toml')
            outside.write_text('# preserve external\n')
            os.link(outside, target)
            install('codex', project, components=['config'], config_mode=mode, force=True)
            self.assertEqual('# preserve external\n', outside.read_text())
            self.assertFalse(target.samefile(outside))

    def reviewed_repo(self):
        project = self.root
        init_project(project, name='Fixture')
        git(project, 'init', '-b', 'work')
        git(project, 'config', 'user.name', 'Fixture')
        git(project, 'config', 'user.email', 'fixture@example.invalid')
        (project / 'src').mkdir()
        (project / 'src/app.py').write_text('original')
        policy = read_yaml(project / '.embraion/policy.yaml')
        policy['enforcement'] = {'enabled': True, 'validation-profile': 'affected', 'require-review': True}
        write_yaml(project / '.embraion/policy.yaml', policy)
        import sys
        write_yaml(project / '.embraion/validation.yaml', {'profiles': {'affected': [f'"{sys.executable}" -c "print(123)"']}})
        git(project, 'add', '.')
        git(project, 'commit', '-m', 'base')
        start_run('reviewed', 'task', 'worker', 'codex', 'substantial', 'PRIVATE', 'write', ['src/**'], substantial=True, project=project)
        (project / 'src/app.py').write_text('reviewed')
        complete_run('reviewed', changed_paths=['src/app.py'], validation=[], review='passed', outcome='completed', residual_risks=[], project=project)
        self.assertTrue(check_enforcement(base_ref='HEAD', project=project, run_id='reviewed')['passed'])
        return project

    def test_review_binding_rejects_content_index_untracked_mode_and_commit_changes(self):
        project = self.reviewed_repo()
        before = read_run('reviewed', project)
        target = project / 'src/app.py'
        for content in ('unreviewed same path', 'reviewed'):
            target.write_text(content)
            self.assertEqual(content == 'reviewed', check_enforcement(base_ref='HEAD', project=project, run_id='reviewed')['passed'])
        new = project / 'src/new.py'
        new.write_text('new untracked')
        self.assertFalse(check_enforcement(base_ref='HEAD', project=project, run_id='reviewed')['passed'])
        new.unlink()
        git(project, 'add', 'src/app.py')
        self.assertFalse(check_enforcement(base_ref='HEAD', project=project, run_id='reviewed')['passed'])
        git(project, 'commit', '-m', 'new commit')
        self.assertFalse(check_enforcement(base_ref='HEAD^', project=project, run_id='reviewed')['passed'])
        self.assertEqual(before, read_run('reviewed', project))

    def test_validation_cannot_change_reviewed_snapshot_and_still_pass(self):
        project = self.reviewed_repo()
        from embraion import enforcement
        real = enforcement.run_validation_profile
        def mutating_validation(*args, **kwargs):
            result = real(*args, **kwargs)
            (project / 'src/app.py').write_text('changed during validation')
            return result
        with patch.object(enforcement, 'run_validation_profile', side_effect=mutating_validation):
            self.assertFalse(check_enforcement(base_ref='HEAD', project=project, run_id='reviewed')['passed'])

    def test_external_and_no_review_gates_reject_validation_mutations(self):
        from embraion import enforcement
        project = self.reviewed_repo()
        policy_path = project / '.embraion/policy.yaml'
        policy = read_yaml(policy_path)
        policy['sources']['protected'] = ['protected.txt']
        real = enforcement.run_validation_profile
        def mutating_validation(*args, **kwargs):
            result = real(*args, **kwargs)
            (project / 'protected.txt').write_text('changed during validation')
            return result
        for required in (True, False):
            with self.subTest(require_review=required):
                policy['enforcement']['require-review'] = required
                write_yaml(policy_path, policy)
                (project / 'protected.txt').unlink(missing_ok=True)
                with patch.object(enforcement, 'run_validation_profile', side_effect=mutating_validation):
                    result = check_enforcement(base_ref='HEAD', project=project, external_review_gate=True)
                self.assertFalse(result['passed'])
                checks = {check['id']: check for check in result['checks']}
                self.assertEqual('failed', checks['workspace-stability']['status'])
                self.assertIn('protected.txt', checks['protected-sources']['changed-paths'])

    def test_pruning_preserves_edit_after_plan_and_records_conflict(self):
        import hashlib
        from embraion import project as projections
        project = self.root / 'project'
        init_project(project, name='Fixture')
        install('codex', project, components=['agents'])
        retired = project / '.codex/agents/retired.toml'
        retired.write_text('old generated')
        state_path = _projection_state_path(project, 'codex')
        state = read_json(state_path)
        digest = hashlib.sha256(retired.read_bytes()).hexdigest()
        state['files']['.codex/agents/retired.toml'] = digest
        write_json(state_path, state)
        real = projections._projection_plan_from_generated
        def edit_after_plan(*args, **kwargs):
            plan = real(*args, **kwargs)
            retired.write_text('new user work')
            return plan
        with patch.object(projections, '_projection_plan_from_generated', side_effect=edit_after_plan):
            result = install('codex', project, components=['agents'], prune=True)
        self.assertEqual('new user work', retired.read_text())
        self.assertIn('.codex/agents/retired.toml', result['obsolete-modified'])
        self.assertEqual(digest, read_json(state_path)['files']['.codex/agents/retired.toml'])

    def test_legacy_review_without_snapshot_fails_closed(self):
        project = self.reviewed_repo()
        path = project / '.embraion/state/runs/reviewed.json'
        record = read_json(path)
        record.pop('review-snapshot', None)
        write_json(path, record)
        self.assertFalse(check_enforcement(base_ref='HEAD', project=project, run_id='reviewed')['passed'])

    def test_learning_associations_are_order_independent_and_schema_valid(self):
        validator = Draft202012Validator(read_json(framework_root() / 'schemas/learning.schema.json'))
        with patch('embraion.learning.project_root', return_value=self.root):
            for order in ('paired-first', 'eval-first'):
                def add(run=None, ev=None):
                    return observe(order, 'pattern', 'skill', None, 'same', run_id=run, eval_id=ev)
                if order == 'eval-first':
                    for ev in ('e1','e2','e3'): add(ev=ev)
                for ev in ('e1','e2','e3'): add('one-run', ev)
                for ev in ('e1','e2','e3'): item = add(ev=ev)
                self.assertEqual(1, item['evidence']['count'])
                self.assertEqual(0.5, item['confidence'])
                validator.validate(item)
                with self.assertRaisesRegex(RuntimeError, 'Insufficient'):
                    transition(order, 'propose')
                for run in ('r2','r3','r4'): item = add(run, 'e1')
                self.assertEqual(4, item['evidence']['count'])
                for action in ('propose','approve','promote'):
                    validator.validate(transition(order, action))
                with self.assertRaises(RuntimeError):
                    transition(order, 'propose')

    def test_learning_recorrelation_withdraws_unproven_proposal_and_migrates_disk(self):
        with patch('embraion.learning.project_root', return_value=self.root):
            for ev in ('e1', 'e2', 'e3', 'e4'):
                observe('correlated', 'pattern', 'skill', None, 'same', eval_id=ev)
            transition('correlated', 'propose')
            transition('correlated', 'approve')
            for ev in ('e1', 'e2', 'e3', 'e4'):
                item = observe('correlated', 'pattern', 'skill', None, 'same', run_id='one', eval_id=ev)
            self.assertEqual(1, item['evidence']['count'])
            self.assertEqual('observed', item['state'])
            with self.assertRaises(RuntimeError):
                transition('correlated', 'promote')
            path = self.root / '.embraion/state/learning/correlated.json'
            item['evidence'].pop('observation-ids')
            item['evidence'].pop('eval-runs')
            write_json(path, item)
            returned = observe('correlated', 'pattern', 'skill', None, 'same', run_id='one')
            self.assertEqual(returned, read_json(path))
            self.assertIn('eval-runs', returned['evidence'])

    def test_atomic_failure_preserves_destination_and_removes_own_temp(self):
        target = self.root / 'record.json'
        write_json(target, {'old': True})
        with patch.object(Path, 'replace', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                write_json(target, {'new': True})
        self.assertEqual({'old': True}, read_json(target))
        self.assertEqual([target], list(self.root.iterdir()))

    def test_portable_manifest_declares_catalog_roots(self):
        root = framework_root()
        includes = read_yaml(root / 'adapters/portable/package.yaml')['include']
        for capability in read_yaml(root / 'core/catalog.yaml')['capabilities']:
            self.assertIn(capability['path'].split('/')[0], includes)


class PublicPreflightTests(unittest.TestCase):
    def setUp(self):
        self.fixture = mixed.MixedExecutionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_known_unsupported_settings_have_public_safe_diagnostic(self):
        for selection in ({'effort': 'high'}, {'options': {'temperature': 0.2}}):
            with self.subTest(selection=selection):
                self.fixture.definitions['first']['efforts'] = ['high']
                self.fixture.bindings['first']['optionAllowlist'] = ['temperature']
                self.fixture.request['candidates'][0] = {'deployment': 'first', **selection}
                self.fixture.write_config()
                result = self.fixture.run_request()
                attempt = result['attempts'][0]
                self.assertEqual('unsupported-capability', attempt['failure'])
                self.assertIn('effort or options', attempt['diagnostic'])
                self.assertTrue(attempt['terminationConfirmed'])
                self.fixture.transport.assert_not_called()
                self.fixture.resolver.resolve.assert_not_called()

    def test_cli_reports_preflight_reason_without_calling_provider(self):
        from embraion.cli import main
        fixture = self.fixture
        fixture.definitions['first']['efforts'] = ['high']
        fixture.request['candidates'][0]['effort'] = 'high'
        fixture.write_config()
        output = io.StringIO()
        with (patch('embraion.cli.resolve_project_runtime', return_value=None),
              patch('embraion.execution.project_root', return_value=fixture.project),
              patch('sys.stdin', io.StringIO(json.dumps(fixture.request))),
              patch('embraion.adapters.litellm_execution.LiteLLMLoopbackAdapter.execute') as child,
              redirect_stdout(output)):
            code = main(['execute'])
        self.assertEqual(1, code)
        result = json.loads(output.getvalue())
        self.assertEqual('unsupported-capability', result['attempts'][0]['failure'])
        self.assertIn('effort or options', result['attempts'][0]['diagnostic'])
        child.assert_not_called()

    def test_unknown_and_post_preflight_errors_do_not_claim_safe_termination(self):
        from embraion.failures import UnsupportedExecutionSettings
        fixture = self.fixture
        for error in (RuntimeError('sensitive provider details'), UnsupportedExecutionSettings()):
            with self.subTest(error=type(error).__name__):
                fixture.transport.side_effect = error
                result = fixture.run_request()
                attempt = result['attempts'][0]
                self.assertEqual('unknown', attempt['failure'])
                self.assertFalse(attempt['terminationConfirmed'])
                self.assertNotIn('diagnostic', attempt)
                self.assertNotIn('sensitive provider details', json.dumps(result))
