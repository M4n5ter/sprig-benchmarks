#!/usr/bin/env python3
"""Non-kernel checks; these do not establish product acceptance."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cas_sample import SampleError
from lifecycle_sample import production_report
from stress_fixture import generate
from stress_sample import StressSample, BudgetAbort, validate_fixture


def fixture(root, **kwargs):
    value = generate(root, files=4, links=4, steps=3, **kwargs)
    listed = [dict(path=e['path'], bytes=e['size'], sha256=e['sha256'])
              for e in value['initial']['entries'] if e['type']=='file']
    return value, listed


class SampleTests(unittest.TestCase):
    def test_validates_actual_hardlink_recipe(self):
        with tempfile.TemporaryDirectory() as d:
            value, listed = fixture(Path(d)/'fixture')
            self.assertEqual(validate_fixture(value, listed), listed)
            broken = copy.deepcopy(value)
            broken['edits'][0]['aliases'] = [broken['edits'][0]['path']]
            with self.assertRaises(SampleError): validate_fixture(broken, listed)
            broken = copy.deepcopy(value)
            broken['edits'][0]['offset'] = 999999
            with self.assertRaises(SampleError): validate_fixture(broken, listed)
            with self.assertRaises(SampleError): validate_fixture(value, listed[:-1])

    def test_actual_bash_writer_preserves_aliases_and_exact_metadata(self):
        import subprocess
        from cas_sample import write_command
        from stress_fixture import expected_after
        from tree_oracle import snapshot, differences
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'fixture'
            value, _ = fixture(root)
            for number, edit in enumerate(value['edits'],1):
                subprocess.run(['bash','-c',write_command(edit)],cwd=root,check=True)
                self.assertEqual(differences(expected_after(value,number),snapshot(root)),[])

    def test_primary_rejects_ambient_tracing_before_product_setup(self):
        import os
        from types import SimpleNamespace
        s = StressSample(production_report())
        args = SimpleNamespace(budget_seconds=600,records='/unused',diagnostic=False)
        with patch.dict(os.environ, {'SPRIG_LIFECYCLE_TRACE':'1'}):
            with self.assertRaises(SampleError): s.prepare(args)
        self.assertIsNone(s.root)

    def test_noop_uses_same_revision_but_writable_replaces_generation(self):
        with tempfile.TemporaryDirectory() as d:
            value, listed = fixture(Path(d)/'fixture')
            for backend in ('native','writable'):
                with self.subTest(backend=backend):
                    s = StressSample(production_report())
                    s.backend, s.fixture = backend, value
                    old = dict(generation='old', merged=Path(d)/'old')
                    new = dict(generation='new' if backend=='writable' else 'old',
                               merged=Path(d)/('new' if backend=='writable' else 'old'),
                               base_revision='a'*64)
                    s.views = [old]
                    s.report['checkpointOperationCount'] = 0
                    s.guard = lambda _: None
                    s.step_record = lambda _: None
                    s.verify_tree = lambda *a: 0.0
                    s.view = lambda x: x
                    s.cli = lambda action,*args: (dict(committed=True,branch='work',previous_head='a'*64,
                        revision='a'*64) if action=='checkpoint' else new)
                    with patch('stress_sample.exact_mount',return_value=None):
                        got, revision = s.checkpoint(old,1,None,'a'*64,set())
                    self.assertEqual(got,new)
                    self.assertEqual(revision,'a'*64)
                    self.assertTrue(s.report['checkpoint_steps'][0]['noop'])
                    self.assertEqual(s.report['history_distinct_revisions'],0)

    def test_unchanged_rejects_fabricated_revision(self):
        s = StressSample(production_report())
        s.guard = lambda _: None
        s.step_record = lambda _: None
        s.cli = lambda *a: dict(committed=True,branch='work',previous_head='a'*64,revision='b'*64)
        with self.assertRaises(SampleError): s.checkpoint({},1,None,'a'*64,set())

    def test_budget_abort_does_not_start_command(self):
        s = StressSample(production_report())
        s.deadline, s.budget_seconds = 0, 1
        with self.assertRaises(BudgetAbort): s.guard('next-mutation')

    def test_diagnostic_env_only_for_cli_and_success_stderr_retained(self):
        import os
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            s = StressSample(production_report())
            s.binary, s.logs, s.diagnostic = Path('/test/sprig'), Path(d), True
            result = SimpleNamespace(returncode=0,stdout='{}',stderr='complete diagnostic\n')
            with patch.dict(os.environ, {'SPRIG_LIFECYCLE_TRACE':'1'}), patch('stress_sample.subprocess.run',return_value=result) as run:
                s.command([s.binary,'show'],record_event=False)
                self.assertEqual(run.call_args.kwargs['env']['SPRIG_LIFECYCLE_TRACE'],'1')
                s.command(['/usr/bin/python3','oracle'],record_event=False)
                self.assertNotIn('SPRIG_LIFECYCLE_TRACE',run.call_args.kwargs['env'])
            self.assertEqual((Path(d)/'command-000001-stderr.log').read_text(),'complete diagnostic\n')

    def test_diagnostic_requires_valid_archived_records(self):
        import json
        for emitted, expected in [(False,False),(True,True)]:
            with self.subTest(emitted=emitted), tempfile.TemporaryDirectory() as d:
                s = StressSample(production_report())
                s.root = Path(d)/'root'; s.root.mkdir()
                s.logs = s.root/'logs'; s.logs.mkdir()
                s.records = Path(d)/'steps.jsonl'
                s.diagnostic = True
                s.report['ok'] = True
                if emitted:
                    row = dict(version=1,pid=123,phase='test',elapsed_ns=0,retries=0,ok=None)
                    (s.logs/'command-000001-stderr.log').write_text('SPRIG_LIFECYCLE_TRACE '+json.dumps(row)+'\n')
                if expected:
                    s.preserve_logs()
                    self.assertEqual(s.report['lifecycleTraceEvidence']['counts']['cli'],1)
                    self.assertTrue(Path(s.report['completeLogArchive'][0]['archived']).is_file())
                else:
                    with self.assertRaises(SampleError): s.preserve_logs()
                    self.assertEqual(s.report['lifecycleTraceEvidence']['validRecords'],0)

    def test_trace_schema_validation(self):
        import json
        from stress_sample import parse_trace_line
        row = dict(version=1,pid=123,phase='test',elapsed_ns=0,retries=0,ok=True)
        self.assertEqual(parse_trace_line('SPRIG_LIFECYCLE_TRACE '+json.dumps(row)),row)
        self.assertIsNone(parse_trace_line('normal stderr'))
        for key,bad in [('version',True),('pid',0),('elapsed_ns',-1),('retries',False),('ok','true')]:
            broken = dict(row); broken[key] = bad
            with self.assertRaises(SampleError): parse_trace_line('SPRIG_LIFECYCLE_TRACE '+json.dumps(broken))

    def test_capacity_reserves_and_exact_image(self):
        s = StressSample(production_report())
        s.root = Path('/unused')
        s.command = lambda *a: 'Device size: 2147483648\nUsed: 100000000\n'
        s.capacity_guard(10000000)
        with self.assertRaises(BudgetAbort): s.capacity_guard(2000000000)
        s.command = lambda *a: 'Device size: 4294967296\nUsed: 100000000\n'
        with self.assertRaises(SampleError): s.capacity_guard(10000000)

    def test_full_oracle_rejects_broken_hardlink(self):
        with tempfile.TemporaryDirectory() as d:
            value, _ = fixture(Path(d)/'fixture')
            root = Path(d)/'fixture'
            s = StressSample(production_report())
            s.report['fullTreeChecks'] = []
            s.step_record = lambda _: None
            self.assertGreaterEqual(s.verify_tree(root,value['initial'],'good'),0)
            alias = root/'links/l000000.dat'
            blob = alias.read_bytes(); old = alias.stat()
            alias.unlink(); alias.write_bytes(blob)
            import os
            os.chmod(alias,old.st_mode & 0o777)
            os.utime(alias,ns=(old.st_atime_ns,old.st_mtime_ns))
            with self.assertRaises(SampleError): s.verify_tree(root,value['initial'],'bad-link')


if __name__ == '__main__': unittest.main()
