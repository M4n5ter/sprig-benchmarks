#!/usr/bin/env python3
"""Inert adapter tests: mocked children/inventories, never a product/kernel run."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import latest_sample
import latest_combined_sample as module
from cas_sample import SampleError


def options(root):
    return SimpleNamespace(backend='native', production_sha=module.PRODUCTION_SHA,
        binary_sha256=hashlib.sha256(b'inert executable fixture').hexdigest(),
        case='identical', steps=None, archive_allowance_bytes=module.ARCHIVE_LIMIT,
        root=str(root / 'sample'), source=str(root / 'identical'),
        oracle=str(root / 'identical.json'), binary=str(root / 'sprig'),
        records=str(root / 'records.jsonl'))


def identical():
    return [dict(path=f'files/f{i:04}.dat', bytes=1048576, sha256='a' * 64) for i in range(100)]


def history():
    rows = []
    for i in range(200):
        if i < 64:
            path = f'wide/s000-f{i:03}.dat'
        elif i < 199:
            path = f'regular/s000/f{i:03}.dat'
        else:
            path = 'spine/' + '/'.join(f'd{n:03}' for n in range(1, 129)) + '/s000.dat'
        rows.append(dict(path=path, bytes=1024 if i < 128 else 8192 if i < 192 else 49152,
                         sha256='a' * 64))
    steps = [dict(step=i+1, path=row['path'], offset=row['bytes']//2-32,
                  data=base64.b64encode(b'x' * 64).decode(), sha256='b' * 64)
             for i, row in enumerate(rows[:100])]
    return rows, steps


def ready(root):
    sample = module.LatestCombinedSample(module.production_report())
    sample.root = root / 'sample'
    sample.root.mkdir()
    sample.library = sample.root / 'library'
    sample.library.mkdir()
    sample.logs = sample.root / 'logs'
    sample.logs.mkdir()
    sample.records = root / 'records.jsonl'
    sample.records.write_bytes(b'')
    sample.backend = 'native'
    sample.command_env = dict(TMPDIR=str(sample.root / 'tmp'))
    sample.archive_allowance = module.ARCHIVE_LIMIT
    sample.report['ok'] = True
    return sample


def child(stdout=b'complete stdout\n', stderr=b'complete stderr\n', code=0, wait_error=None):
    process = Mock()
    process.wait.side_effect = wait_error
    process.wait.return_value = code

    def spawn(argv, **kwargs):
        kwargs['stdout'].write(stdout)
        kwargs['stderr'].write(stderr)
        return process
    return process, spawn


def clean(sample):
    with patch.object(module, 'mount_table', return_value=[]), patch.object(sample, 'processes', return_value=[]):
        sample.cleanup()


class LatestCombinedSampleTests(unittest.TestCase):
    def test_report_uses_new_pin_without_modifying_frozen_globals(self):
        old_sha, old_class, old_report = latest_sample.PRODUCTION_SHA, latest_sample.CurrentSample, latest_sample.production_report
        report = module.production_report()
        self.assertEqual(report['schema'], 'sprig-latest-combined-native-sample-v1')
        self.assertEqual(report['production_sha'], module.PRODUCTION_SHA)
        self.assertIsNone(report['postHistorySpace'])
        self.assertFalse(report['complete_metadata_verification'])
        self.assertFalse(report['remainingMountsKnown'])
        self.assertEqual((latest_sample.PRODUCTION_SHA, latest_sample.CurrentSample, latest_sample.production_report),
                         (old_sha, old_class, old_report))
        self.assertTrue(any('do not pool' in note for note in report['measurementNotes']))

    def test_only_exact_native_options_and_allowance_are_admitted(self):
        args = options(Path('/inert'))
        with patch.dict(os.environ, {}, clear=True):
            module.validate_options(args)
            for field, value in [('backend', 'projection'), ('backend', 'writable'),
                                 ('production_sha', '9' * 40), ('binary_sha256', 'A' * 64),
                                 ('case', 'unique'), ('steps', '/inert/steps.json'),
                                 ('archive_allowance_bytes', -1), ('archive_allowance_bytes', True),
                                 ('archive_allowance_bytes', module.ARCHIVE_LIMIT+1),
                                 ('records', 'relative.jsonl'), ('root', '/inert/../elsewhere')]:
                with self.subTest(field=field, value=value):
                    bad = copy.copy(args)
                    setattr(bad, field, value)
                    with self.assertRaises(SampleError):
                        module.validate_options(bad)
            args.archive_allowance_bytes = 0
            module.validate_options(args)
        with patch.dict(os.environ, {'SPRIG_LIFECYCLE_TRACE': '1'}):
            with self.assertRaises(SampleError):
                module.validate_options(args)

    def test_frozen_smoke_shapes_reject_wrong_counts_sizes_and_edit_pattern(self):
        module.validate_fixture('identical', identical(), [])
        rows, steps = history()
        module.validate_fixture('history-distributed', rows, steps)
        for case, oracle, edits in [('identical', identical()[:-1], []),
                                    ('identical', identical(), steps),
                                    ('history-distributed', rows, steps[:-1])]:
            with self.assertRaises(SampleError):
                module.validate_fixture(case, oracle, edits)
        bad = identical()
        bad[-1]['bytes'] -= 1
        with self.assertRaises(SampleError):
            module.validate_fixture('identical', bad, [])
        for key, value in [('offset', 0), ('data', base64.b64encode(b'x').decode()),
                           ('path', steps[0]['path'])]:
            bad = copy.deepcopy(steps)
            bad[1][key] = value
            with self.assertRaises(SampleError):
                module.validate_fixture('history-distributed', rows, bad)

    def test_prepare_hashes_binary_and_sets_owned_tmpdir_before_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            args = options(root)
            Path(args.binary).write_bytes(b'inert executable fixture')
            sample = module.LatestCombinedSample(module.production_report())

            def frozen_prepare(self, given):
                self.root = Path(given.root)
                self.root.mkdir()
                self.logs = self.root / 'logs'
                self.logs.mkdir()
                self.binary = Path(given.binary)
                self.oracle, self.steps = identical(), []
            with patch.object(module.Base, 'prepare', frozen_prepare), patch.dict(os.environ, {}, clear=True), \
                    patch.object(module.subprocess, 'Popen') as spawn:
                sample.prepare(args)
            spawn.assert_not_called()
            self.assertTrue(sample.report['binaryHashVerified'])
            self.assertEqual(sample.command_env['TMPDIR'], str(sample.root / 'tmp'))
            self.assertTrue((sample.root / 'tmp').is_dir())
            self.assertTrue(sample.report['temporaryDirectory']['setBeforeProductCLI'])

    def test_wrong_binary_hash_fails_before_product_or_tmpdir(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            args = options(root)
            Path(args.binary).write_bytes(b'wrong binary')
            sample = module.LatestCombinedSample(module.production_report())

            def frozen_prepare(self, given):
                self.root = Path(given.root)
                self.root.mkdir()
                self.logs = self.root / 'logs'
                self.logs.mkdir()
                self.binary = Path(given.binary)
                self.oracle, self.steps = identical(), []
            with patch.object(module.Base, 'prepare', frozen_prepare), patch.dict(os.environ, {}, clear=True), \
                    patch.object(module.subprocess, 'Popen') as spawn:
                with self.assertRaises(SampleError):
                    sample.prepare(args)
            spawn.assert_not_called()
            self.assertFalse((sample.root / 'tmp').exists())

    def test_readonly_cargo_binary_may_have_build_hardlink_but_logs_may_not(self):
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / 'sprig'
            binary.write_bytes(b'fixed binary')
            os.link(binary, Path(d) / 'sprig-deps')
            digest, size = module.hash_regular(binary, allow_links=True)
            self.assertEqual(digest, hashlib.sha256(b'fixed binary').hexdigest())
            self.assertEqual(size, len(b'fixed binary'))
            with self.assertRaises(SampleError):
                module.hash_regular(binary)

    def test_complete_streams_metadata_hashes_and_wait_has_no_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            process, spawn = child(stdout=b'full stdout\xff\n', stderr=b'warning\n')
            with patch.object(module.subprocess, 'Popen', side_effect=spawn) as popen:
                result = sample.command(['/inert/sprig', '--json'])
            self.assertEqual(result, 'full stdout\ufffd\n')
            process.wait.assert_called_once_with()
            process.terminate.assert_not_called()
            process.kill.assert_not_called()
            kwargs = popen.call_args.kwargs
            self.assertNotIn('timeout', kwargs)
            self.assertEqual(kwargs['env'], sample.command_env)
            row = sample.report['commands'][0]
            self.assertNotIn('stdout', row)
            self.assertTrue(row['outcomeKnown'])
            self.assertEqual(Path(row['stdoutPath']).read_bytes(), b'full stdout\xff\n')
            self.assertEqual(row['stdoutSha256'], hashlib.sha256(b'full stdout\xff\n').hexdigest())
            self.assertEqual(row['stderrBytes'], len(b'warning\n'))

    def test_known_nonzero_retains_full_error_streams_and_allows_readonly_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            _, spawn = child(code=7)
            with patch.object(module.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaises(SampleError):
                    sample.command(['/inert/fail'])
            self.assertFalse(sample.uncertain)
            row = sample.report['commands'][0]
            self.assertEqual(row['returncode'], 7)
            self.assertTrue(row['outcomeKnown'])
            clean(sample)
            self.assertTrue(sample.report['lifecycle']['cleanup']['complete'])
            sample.preserve_logs()
            self.assertTrue(sample.report['archiveCopy']['complete'])
            self.assertTrue(all(Path(item['source']).exists() for item in sample.report['completeLogArchive']))

    def test_spawn_uncertainty_is_sticky_and_does_not_claim_archive(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            with patch.object(module.subprocess, 'Popen', side_effect=OSError('ambiguous spawn')) as spawn:
                with self.assertRaises(OSError):
                    sample.command(['/inert/child'])
                with self.assertRaises(SampleError):
                    sample.command(['/inert/second'])
            spawn.assert_called_once()
            with patch.object(sample, 'processes') as processes, patch.object(module, 'mount_table') as mounts:
                sample.cleanup()
            processes.assert_not_called()
            mounts.assert_not_called()
            sample.preserve_logs()
            self.assertTrue(sample.report['uncertain'])
            self.assertTrue(sample.report['cleanupAdmissionBlocked'])
            self.assertFalse(sample.report['remainingServersKnown'])
            self.assertFalse(sample.report['archiveCopy']['complete'])
            self.assertNotIn('completeLogArchive', sample.report)
            self.assertFalse(sample.records.with_name(sample.records.name+'.logs').exists())

    def test_wait_exception_retains_child_and_never_signals_or_retries(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            process, spawn = child(wait_error=InterruptedError('wait unknown'))
            with patch.object(module.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaises(InterruptedError):
                    sample.command(['/inert/child'])
            self.assertIn(process, sample.active_children)
            process.wait.assert_called_once_with()
            process.kill.assert_not_called()
            process.terminate.assert_not_called()
            self.assertFalse(sample.report['commands'][0]['outcomeKnown'])
            self.assertEqual(Path(sample.report['commands'][0]['stderrPath']).read_bytes(), b'complete stderr\n')

    def test_oversize_stream_is_persisted_completely_then_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            data = b'x' * 129
            _, spawn = child(stdout=data, stderr=b'')
            with patch.object(module, 'STREAM_LIMIT', 128), patch.object(module.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaises(SampleError):
                    sample.command(['/inert/large'])
            row = sample.report['commands'][0]
            self.assertEqual(Path(row['stdoutPath']).read_bytes(), data)
            self.assertFalse(row['withinAcceptanceLimits'])
            self.assertFalse(sample.uncertain)

    def test_combined_stream_limit_is_not_individual_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            _, spawn = child(stdout=b'a'*70, stderr=b'b'*70)
            with patch.object(module, 'SOURCE_LOG_LIMIT', 128), patch.object(module.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaises(SampleError):
                    sample.command(['/inert/large'], record_event=False)
            row = sample.report['commands'][0]
            self.assertEqual(row['stdoutBytes'] + row['stderrBytes'], 140)
            self.assertEqual(Path(row['stderrPath']).read_bytes(), b'b'*70)

    def test_fixed_preflight_only_and_full_evidence_survives(self):
        with tempfile.TemporaryDirectory() as d:
            sample = module.LatestCombinedSample(module.production_report())
            sample.preflight_argv = ['stat', '-f', '-c', '%T', d]
            sample.preflight_logs = Path(d) / 'sample.preflight-logs'
            with self.assertRaises(SampleError):
                sample.command(['/inert/not-stat'])
            _, spawn = child(stdout=b'btrfs\n', stderr=b'')
            with patch.object(module.subprocess, 'Popen', side_effect=spawn):
                self.assertEqual(sample.command(sample.preflight_argv), 'btrfs\n')
            self.assertEqual(Path(sample.report['commands'][0]['stdoutPath']).read_bytes(), b'btrfs\n')
            with self.assertRaises(SampleError):
                sample.command(sample.preflight_argv)

    def test_native_cleanup_never_calls_generic_unmount_and_requires_known_empty(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            with patch.object(module.Base, 'cleanup') as generic, patch.object(sample, 'command') as command:
                clean(sample)
            generic.assert_not_called()
            command.assert_not_called()
            self.assertTrue(sample.report['remainingMountsKnown'])
            self.assertTrue(sample.report['remainingServersKnown'])
            self.assertEqual(sample.report['remainingServers'], [])
            with patch.object(module, 'mount_table', return_value=[]), patch.object(sample, 'processes', return_value=[{'pid': 7}]):
                sample.cleanup()
            self.assertFalse(sample.report['lifecycle']['cleanup']['complete'])
            self.assertFalse(sample.report['ok'])
            self.assertEqual(sample.report['lifecycle']['daemons'], [{'pid': 7}])

    def test_inventory_error_keeps_known_false_and_blocks_complete_archive(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            with patch.object(module, 'mount_table', side_effect=OSError('inventory unavailable')), \
                    patch.object(sample, 'processes', return_value=[]):
                sample.cleanup()
            self.assertFalse(sample.report['remainingMountsKnown'])
            self.assertTrue(sample.report['remainingServersKnown'])
            sample.preserve_logs()
            self.assertNotIn('completeLogArchive', sample.report)
            self.assertFalse(sample.report['archiveCopy']['complete'])

    def test_metadata_ledger_bound_checked_before_append(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            sample.step_record({'event': 'first'})
            before = sample.records.read_bytes()
            with patch.object(module, 'LEDGER_LIMIT', len(before)):
                with self.assertRaises(SampleError):
                    sample.step_record({'event': 'second'})
            self.assertEqual(sample.records.read_bytes(), before)

    def test_whole_archive_admission_precedes_directory_and_copy(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            (sample.logs / 'small.log').write_bytes(b'1234')
            (sample.logs / 'large.log').write_bytes(b'123456')
            sample.archive_allowance = 9
            clean(sample)
            with self.assertRaises(SampleError):
                sample.preserve_logs()
            self.assertEqual(sample.report['archiveAdmission'],
                             dict(allowanceBytes=9, plannedBytes=10, plannedFiles=3, admitted=False))
            self.assertEqual(sample.report['archiveCopy']['completedFiles'], 0)
            self.assertFalse(sample.records.with_name(sample.records.name+'.logs').exists())
            self.assertNotIn('completeLogArchive', sample.report)

    def test_full_archive_includes_every_file_and_ledger_without_removing_sources(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            nested = sample.logs / 'nested'
            nested.mkdir()
            (nested / 'stdout.log').write_bytes(b'raw\x00\xff\n')
            (sample.logs / 'stderr.log').write_bytes(b'')
            sample.step_record({'event': 'acknowledged', 'revision': 'a'*64})
            clean(sample)
            sample.preserve_logs()
            manifest = sample.report['completeLogArchive']
            self.assertEqual(len(manifest), 3)
            self.assertTrue(sample.report['archiveCopy']['complete'])
            self.assertTrue(sample.report['archiveCopy']['sourceFilesRetained'])
            self.assertNotIn('partialLogArchive', sample.report)
            self.assertEqual({item['source'] for item in manifest},
                             {str(nested / 'stdout.log'), str(sample.logs / 'stderr.log'), str(sample.records)})
            for item in manifest:
                data = Path(item['source']).read_bytes()
                self.assertEqual(Path(item['archived']).read_bytes(), data)
                self.assertEqual(item['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(item['bytes'], len(data))

    def test_source_mutation_after_plan_never_becomes_complete_archive(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            source = sample.logs / 'raw.log'
            source.write_bytes(b'original')
            clean(sample)
            original_hash = module.hash_regular
            altered = False

            def change_after_hash(path, expected=None):
                nonlocal altered
                result = original_hash(path, expected)
                if path == source and not altered:
                    altered = True
                    source.write_bytes(b'changed!')
                return result
            with patch.object(module, 'hash_regular', side_effect=change_after_hash):
                with self.assertRaises(SampleError):
                    sample.preserve_logs()
            self.assertFalse(sample.report['archiveCopy']['complete'])
            self.assertNotIn('completeLogArchive', sample.report)
            self.assertTrue(source.exists())

    def test_archive_rejects_symlink_and_hardlink_instead_of_omitting(self):
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                sample = ready(Path(d))
                source = sample.logs / 'original.log'
                source.write_bytes(b'complete')
                if kind == 'symlink':
                    (sample.logs / 'alias.log').symlink_to(source)
                else:
                    os.link(source, sample.logs / 'alias.log')
                clean(sample)
                with self.assertRaises(SampleError):
                    sample.preserve_logs()
                self.assertNotIn('completeLogArchive', sample.report)
                self.assertFalse(sample.records.with_name(sample.records.name+'.logs').exists())

    def test_execute_preserves_inherited_task_then_post_history_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            sample.report['binaryHashVerified'] = True
            calls = []
            with patch.object(module.Base, 'execute', side_effect=lambda: calls.append('original')), \
                    patch.object(sample, 'sample_post_history_space', side_effect=lambda: calls.append('post-history')):
                sample.execute()
            self.assertEqual(calls, ['original', 'post-history'])
            self.assertGreaterEqual(sample.report['wholeTaskSeconds'], 0)
            self.assertIs(module.LatestCombinedSample.retained_snapshot,
                          module.PostHistoryContract.retained_snapshot)
            self.assertIs(module.LatestCombinedSample.sample_post_history_space,
                          module.PostHistoryContract.sample_post_history_space)

    def test_actual_borrowed_post_history_contract_retains103_native_directories(self):
        with tempfile.TemporaryDirectory() as d:
            sample = ready(Path(d))
            native = sample.library / 'native'
            native.mkdir()
            for number in range(103):
                (native / f'g{number:03}').mkdir()
            sample.steps = [{}] * 100
            sample.report['fullHistoricalSnapshotReadbacks'] = 100
            sample.report['activeSpace'] = {'filesystemUsedBytes': 123}
            with patch.object(sample, 'retained_snapshot', return_value={}), \
                    patch.object(sample, 'command', side_effect=['', 'Used: 456\n', 'Data: diagnostic\n']) as command:
                sample.sample_post_history_space()
            self.assertEqual(sample.report['activeSpace']['filesystemUsedBytes'], 123)
            self.assertEqual(sample.report['postHistorySpace']['filesystemUsedBytes'], 456)
            self.assertEqual(sample.report['lifecycle']['activeAfterHistory']['retainedGenerationCount'], 103)
            self.assertTrue(sample.report['lifecycle']['activeAfterHistory']['historicalReadbacksComplete'])
            self.assertEqual(len(list(native.iterdir())), 103)
            self.assertEqual(command.call_count, 3)
            (native / 'g102').rmdir()
            with patch.object(sample, 'retained_snapshot', return_value={}), patch.object(sample, 'command') as command:
                with self.assertRaises(SampleError):
                    sample.sample_post_history_space()
            command.assert_not_called()

    def test_post_history_never_accepts_missing_full_readback(self):
        sample = module.LatestCombinedSample(module.production_report())
        sample.steps = [{}] * 100
        sample.report['fullHistoricalSnapshotReadbacks'] = 99
        with patch.object(sample, 'retained_snapshot') as retained, patch.object(sample, 'command') as command:
            with self.assertRaises(SampleError):
                sample.sample_post_history_space()
        retained.assert_not_called()
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
