"""Inert filesystem fixtures only; never invoke a sampler, runtime or benchmark."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import latest_combined_collect as collector


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).resolve()
        self.results = self.base / 'results'
        self.temporary = self.base / 'temporary'
        self.results.mkdir()
        self.temporary.mkdir()
        self.destination = self.base / 'evidence'

    def collect(self):
        return collector.collect(self.results, self.temporary, self.destination,
                                 os.getuid(), os.getgid())

    def write_json(self, name, value):
        path = self.results / name
        path.write_text(json.dumps(value) + '\n')
        return path

    def sample(self, row_id=collector.ORDER[0], ok=True, partial=False):
        product, case = next((p, c) for p in collector.PRODUCTS for c in collector.CASES
                             if f'{p}-{c}' == row_id)
        directory = self.temporary / 'latest-combined-records' / f'{row_id}.jsonl.logs'
        directory.mkdir(parents=True, exist_ok=True)
        log = directory / '000001-command.stdout'
        data = b'complete log including final newline\n'
        log.write_bytes(data)
        entry = {'source': str(self.base / 'private-runtime' / log.name),
                 'archived': str(log), 'bytes': len(data),
                 'sha256': hashlib.sha256(data).hexdigest()}
        value = {'schema': collector.SAMPLE_SCHEMAS[product], 'product': product,
                 'backend': 'native' if product == 'sprig-native' else 'fuse',
                 'case': case, 'production_sha': collector.PINS[product],
                 'testOnly': False, 'ok': ok,
                 'partialLogArchive' if partial else 'completeLogArchive': [entry]}
        return value, log

    def save_sample(self, sample, row_id=collector.ORDER[0]):
        return self.write_json(f'latest-combined-{row_id}.json', sample)

    def driver(self, passed=False):
        records = []
        for position, row_id in enumerate(collector.ORDER):
            product, case = next((p, c) for p in collector.PRODUCTS for c in collector.CASES
                                 if f'{p}-{c}' == row_id)
            record = {'id': row_id, 'product': product, 'case': case, 'position': position,
                      'status': 'not_run', 'correct': False}
            if passed:
                sample, _ = self.sample(row_id)
                raw = self.save_sample(sample, row_id)
                record.update(status='passed', correct=True, sample=sample,
                              rawReportPath='results/' + raw.name,
                              rawReportSha256=hashlib.sha256(raw.read_bytes()).hexdigest())
            records.append(record)
        return {'schema': collector.DRIVER_SCHEMA, 'complete': passed,
                'status': 'passed' if passed else 'failed', 'records': records}

    def failed_manifest(self):
        with self.assertRaisesRegex(collector.CollectionError, 'collection failed'):
            self.collect()
        manifest = json.loads((self.destination / 'collection.json').read_text())
        self.assertFalse(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])
        self.assertEqual(manifest['status'], 'failed')
        return manifest

    def test_exact_allowlist_no_rounds_or_other_products(self):
        for row_id in collector.IDS:
            for extension in ('json', 'stdout', 'stderr'):
                self.assertTrue(collector.allowed('results', (f'latest-combined-{row_id}.{extension}',)))
            self.assertTrue(collector.allowed('records', (f'{row_id}.jsonl',)))
            for extension in ('stdout', 'stderr', 'log', 'jsonl'):
                self.assertTrue(collector.allowed('records', (f'{row_id}.jsonl.logs', f'000001-command.{extension}')))
        for name in collector.SETUP_RESULTS:
            self.assertTrue(collector.allowed('results', (name,)))
            self.assertFalse(collector.allowed('results', (name + '.extra',)))
        for name in collector.PENDING_RESULTS:
            self.assertTrue(collector.allowed('results', (name,)))
        self.assertFalse(collector.allowed('results', ('latest-combined-summary.json.new',)))
        self.assertFalse(collector.allowed('results', ('latest-combined-other.json.new',)))
        for name in ('latest-combined-sprig-writable-identical.json',
                     'latest-combined-layerfs-identical-0.json',
                     'latest-combined-layerfs-other.json', 'private-token.txt',
                     'daemon.json.original', 'source.img', 'collection.json'):
            self.assertFalse(collector.allowed('results', (name,)))
        for parts in (('../environment.txt',), ('..', 'environment.txt'),
                      ('/environment.txt',), ('environment.txt', 'extra'),
                      ('environment.txt\0',), ('environment\\txt',)):
            self.assertFalse(collector.allowed('results', parts))
        for parts in (('driver.jsonl.logs', '../000001.stdout'),
                      ('driver.jsonl.logs', '000001-command.stdout'),
                      ('driver.jsonl.logs', '000001.log'),
                      ('driver.jsonl.logs', '00001.stdout'),
                      ('sprig-native-identical.jsonl.logs', '.private.log'),
                      ('sprig-native-identical.jsonl.logs', 'nested', 'data.log')):
            self.assertFalse(collector.allowed('records', parts))
        self.assertTrue(collector.allowed('records', ('driver.jsonl',)))
        self.assertTrue(collector.allowed('records', ('driver.jsonl.logs', '000001.stderr')))

    def test_setup_only_and_no_run_are_preserved_not_called_complete(self):
        original = self.write_json('latest-combined-comparison.json', self.driver())
        (self.results / 'environment.txt').write_text('public setup output')
        (self.results / 'daemon.json.original').write_text('private config')
        runtime = self.temporary / 'runtime'
        runtime.mkdir(mode=0o700)
        secret = runtime / 'private-token.txt'
        secret.write_text('do not read or copy')
        original_bytes = original.read_bytes()
        manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertTrue(manifest['copyComplete'])
        self.assertFalse(manifest['benchmarkComplete'])
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual((self.destination / 'results' / original.name).read_bytes(), original_bytes)
        self.assertFalse((self.destination / 'results/daemon.json.original').exists())
        self.assertEqual(stat.S_IMODE(runtime.stat().st_mode), 0o700)
        self.assertEqual(secret.read_text(), 'do not read or copy')
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((self.destination / 'collection.json').stat().st_mode), 0o644)

    def test_empty_or_missing_results_collect_without_claiming_benchmark(self):
        self.results.rmdir()
        self.assertEqual(collector.inventory(self.results, self.temporary)['bytes'], 0)
        manifest = self.collect()
        self.assertEqual(manifest['files'], [])
        self.assertTrue(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])

    def test_inventory_does_not_create_outputs_or_read_bodies(self):
        (self.results / 'environment.txt').write_bytes(b'x' * 123)
        with patch.object(collector, '_copy_one', side_effect=AssertionError('copy during inventory')):
            value = collector.inventory(self.results, self.temporary)
        self.assertEqual(value['bytes'], 123)
        self.assertEqual(value['fileCount'], 1)
        self.assertFalse(self.destination.exists())

    def test_valid_four_rows_verify_all_raw_and_embedded_archives(self):
        self.write_json('latest-combined-comparison.json', self.driver(passed=True))
        manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertTrue(manifest['benchmarkComplete'])
        coverage = manifest['declaredArchiveVerification']
        self.assertEqual(coverage['sampleDeclarations'], 8)
        self.assertEqual(coverage['verifiedUniqueFiles'], 4)
        self.assertEqual(coverage['errors'], [])
        for row in manifest['files']:
            copied = self.destination / row['path']
            self.assertEqual(copied.stat().st_size, row['bytes'])
            self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), row['sha256'])

    def test_driver_ledger_full_streams_are_preserved_without_sample_declaration(self):
        records = self.temporary / 'latest-combined-records'
        logs = records / 'driver.jsonl.logs'
        logs.mkdir(parents=True)
        (records / 'driver.jsonl').write_bytes(b'{"returncode":1}\n')
        (logs / '000001.stdout').write_bytes(b'full output\n')
        (logs / '000001.stderr').write_bytes(b'full error\n')
        manifest = self.collect()
        self.assertEqual(len(manifest['files']), 3)
        self.assertEqual(manifest['declaredArchiveVerification']['sampleDeclarations'], 0)
        self.assertFalse(manifest['benchmarkComplete'])

    def test_pending_atomic_report_is_raw_evidence_and_blocks_completion(self):
        self.write_json('latest-combined-comparison.json', self.driver(passed=True))
        pending = self.results / 'latest-combined-comparison.json.new'
        pending.write_bytes(b'{"partial write, not complete JSON')
        manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])
        self.assertEqual(manifest['declaredArchiveVerification']['pendingReportWrites'],
                         ['results/latest-combined-comparison.json.new'])
        self.assertEqual((self.destination / 'results' / pending.name).read_bytes(), pending.read_bytes())

    def test_driver_has_separate_bounded_parser_limit(self):
        self.write_json('latest-combined-comparison.json', self.driver())
        with patch.object(collector, 'REPORT_LIMIT', 1):
            manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])

    def test_symlink_regular_and_dangling_inputs_rejected_before_copy(self):
        secret = self.base / 'secret'
        secret.write_bytes(b'no')
        link = self.results / 'environment.txt'
        for target in (secret, self.base / 'missing'):
            with self.subTest(target=target):
                link.symlink_to(target)
                with self.assertRaises((OSError, ValueError)):
                    self.collect()
                self.assertFalse(self.destination.exists())
                link.unlink()
        self.assertEqual(secret.read_bytes(), b'no')

    def test_hardlink_and_fifo_inputs_rejected_before_copy(self):
        secret = self.base / 'secret'
        secret.write_bytes(b'no')
        target = self.results / 'environment.txt'
        os.link(secret, target)
        with self.assertRaisesRegex(ValueError, 'independent regular'):
            self.collect()
        self.assertFalse(self.destination.exists())
        target.unlink()
        os.mkfifo(target)
        with self.assertRaisesRegex(ValueError, 'independent regular'):
            self.collect()
        self.assertFalse(self.destination.exists())

    def test_symlink_ancestor_and_log_directory_rejected(self):
        real = self.base / 'real'
        real.mkdir()
        link = self.base / 'alias'
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            collector.inventory(link / 'results', self.temporary)
        records = self.temporary / 'latest-combined-records'
        records.mkdir()
        (records / f'{collector.ORDER[0]}.jsonl.logs').symlink_to(real, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            self.collect()
        self.assertFalse(self.destination.exists())

    def test_unsafe_archive_member_does_not_trigger_runtime_traversal(self):
        _, log = self.sample(ok=False)
        (log.parent / 'nested').mkdir()
        (log.parent / 'nested/private.log').write_text('private')
        with self.assertRaisesRegex(ValueError, 'unexpected name'):
            self.collect()
        self.assertFalse(self.destination.exists())
        self.assertEqual((log.parent / 'nested/private.log').read_text(), 'private')

    def test_destination_must_be_new_outside_both_sources(self):
        for target in (self.results / 'evidence', self.temporary / 'evidence', self.results):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'standalone'):
                collector.collect(self.results, self.temporary, target, os.getuid(), os.getgid())
        self.destination.symlink_to(self.base / 'nonexistent')
        with self.assertRaisesRegex(ValueError, 'standalone'):
            self.collect()

    def test_full_plan_oversize_refused_before_mkdir_or_copy(self):
        source = self.results / f'latest-combined-{collector.ORDER[0]}.stdout'
        with source.open('wb') as stream:
            stream.truncate(collector.CAP - collector.COLLECTION_RESERVE + 1)
        before = source.stat()
        with patch.object(collector, '_copy_one', side_effect=AssertionError('must not copy')):
            with self.assertRaisesRegex(ValueError, 'full planned evidence'):
                self.collect()
        self.assertFalse(self.destination.exists())
        self.assertEqual(source.stat().st_size, before.st_size)
        self.assertEqual(source.stat().st_ino, before.st_ino)

    def test_manifest_reserve_admission_is_before_mkdir(self):
        with patch.object(collector, 'COLLECTION_RESERVE', 65535):
            with self.assertRaisesRegex(ValueError, 'manifest exceeds reserved'):
                self.collect()
        self.assertFalse(self.destination.exists())

    def test_final_manifest_has_explicit_cap_check(self):
        source = self.results / 'environment.txt'
        source.write_text('retain this')
        original = collector._encoded

        def oversized(value):
            if value.get('schema') == 'sprig-latest-combined-evidence-copy-v1':
                return b' ' * (collector.COLLECTION_RESERVE + 1)
            return original(value)

        with patch.object(collector, '_encoded', side_effect=oversized):
            with self.assertRaisesRegex(collector.CollectionError, 'explicit artifact bound'):
                self.collect()
        self.assertEqual(source.read_text(), 'retain this')
        self.assertEqual((self.destination / 'results/environment.txt').read_text(), 'retain this')
        self.assertFalse((self.destination / 'collection.json').exists())

    def test_oversize_failed_raw_transport_and_ledger_not_trimmed(self):
        row_id = collector.ORDER[0]
        records = self.temporary / 'latest-combined-records'
        records.mkdir()
        paths = [(self.results / f'latest-combined-{row_id}.stderr', 128 * 1024**2 + 1),
                 (records / f'{row_id}.jsonl', 8 * 1024**2 + 1)]
        for path, size in paths:
            with path.open('wb') as stream:
                stream.truncate(size)
                stream.seek(size - 1)
                stream.write(b'!')
        manifest = self.collect()
        self.assertEqual(manifest['copiedBytes'], sum(size for _, size in paths))
        self.assertFalse(manifest['benchmarkComplete'])
        for source, size in paths:
            group = 'results' if source.parent == self.results else 'records'
            copy = self.destination / group / source.name
            self.assertEqual(copy.stat().st_size, size)
            with copy.open('rb') as stream:
                stream.seek(size - 1)
                self.assertEqual(stream.read(1), b'!')
            self.assertEqual(source.stat().st_size, size)

    def test_failed_partial_archive_and_undeclared_safe_bytes_preserved(self):
        sample, log = self.sample(ok=False, partial=True)
        (log.parent / '000002-extra.stderr').write_bytes(b'partial failure stream')
        raw = self.save_sample(sample)
        manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])
        self.assertEqual(manifest['declaredArchiveVerification']['successfulSampleIds'], [])
        self.assertEqual(manifest['declaredArchiveVerification']['failedSampleIds'], [collector.ORDER[0]])
        self.assertEqual((self.destination / 'results' / raw.name).read_bytes(), raw.read_bytes())
        self.assertTrue((self.destination / 'records' / log.parent.name / '000002-extra.stderr').is_file())

    def test_failed_preparation_without_archive_or_case_is_preserved(self):
        sample, _ = self.sample(ok=False)
        del sample['completeLogArchive']
        del sample['case']
        self.save_sample(sample)
        manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])

    def test_partial_marker_allowed_only_for_actual_failed_partial_archive(self):
        sample, _ = self.sample(ok=False, partial=True)
        sample['partialLogArchive'][0]['partial'] = True
        self.save_sample(sample)
        manifest = self.collect()
        self.assertTrue(manifest['evidenceOk'])
        self.assertFalse(manifest['benchmarkComplete'])

    def test_archive_missing_hash_size_and_paths_fail_closed_after_copy(self):
        failures = ('missing', 'hash', 'size', 'bool_size', 'no_source', 'null_path',
                    'traversal', 'other_sample', 'relative_source', 'duplicate',
                    'non_array', 'empty', 'undeclared', 'identity', 'partial_success', 'complete_partial')
        for failure in failures:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                old = self.base, self.results, self.temporary, self.destination
                self.base = Path(root).resolve()
                self.results = self.base / 'results'; self.results.mkdir()
                self.temporary = self.base / 'temporary'; self.temporary.mkdir()
                self.destination = self.base / 'evidence'
                try:
                    sample, log = self.sample()
                    entry = sample['completeLogArchive'][0]
                    if failure == 'missing': log.unlink()
                    if failure == 'hash': entry['sha256'] = '0' * 64
                    if failure == 'size': entry['bytes'] += 1
                    if failure == 'bool_size': entry['bytes'] = True
                    if failure == 'no_source': del entry['source']
                    if failure == 'null_path': entry['archived'] = None
                    if failure == 'traversal': entry['archived'] = str(log.parent) + '/../' + log.parent.name + '/' + log.name
                    if failure == 'other_sample': entry['archived'] = str(log).replace('sprig-native-identical', 'layerfs-identical')
                    if failure == 'relative_source': entry['source'] = 'runtime/source.log'
                    if failure == 'duplicate': sample['completeLogArchive'].append(dict(entry))
                    if failure == 'non_array': sample['completeLogArchive'] = {}
                    if failure == 'empty': sample['completeLogArchive'] = []
                    if failure == 'undeclared': (log.parent / '000002-extra.log').write_text('not declared')
                    if failure == 'identity': sample['product'] = 'layerfs'
                    if failure == 'partial_success': sample['partialLogArchive'] = [dict(entry)]
                    if failure == 'complete_partial': entry['partial'] = True
                    raw = self.save_sample(sample)
                    original = raw.read_bytes()
                    manifest = self.failed_manifest()
                    self.assertFalse(manifest['declaredArchiveVerification']['ok'])
                    self.assertEqual(raw.read_bytes(), original)
                    self.assertEqual((self.destination / 'results' / raw.name).read_bytes(), original)
                finally:
                    self.base, self.results, self.temporary, self.destination = old

    def test_malformed_raw_json_is_copied_and_failure_manifest_written(self):
        raw = self.results / f'latest-combined-{collector.ORDER[0]}.json'
        raw.write_bytes(b'{"ok":false, BROKEN\n')
        manifest = self.failed_manifest()
        self.assertTrue(manifest['copyComplete'])
        self.assertEqual((self.destination / 'results' / raw.name).read_bytes(), raw.read_bytes())

    def test_json_parser_bound_preserves_oversize_report(self):
        raw = self.results / f'latest-combined-{collector.ORDER[0]}.json'
        raw.write_bytes(b'{"ok":false,"padding":"' + b'x' * 200 + b'"}')
        with patch.object(collector, 'REPORT_LIMIT', 128):
            manifest = self.failed_manifest()
        self.assertIn('bounded JSON parser', str(manifest['declaredArchiveVerification']['errors']))
        self.assertEqual((self.destination / 'results' / raw.name).read_bytes(), raw.read_bytes())

    def test_embedded_archive_is_verified_even_without_standalone_or_earlier_valid_row(self):
        driver = self.driver()
        sample, log = self.sample(collector.ORDER[-1], ok=False)
        sample['completeLogArchive'][0]['sha256'] = '0' * 64
        driver['records'][-1].update(status='failed', sample=sample)
        driver['records'][0]['position'] = 99
        self.write_json('latest-combined-comparison.json', driver)
        manifest = self.failed_manifest()
        self.assertEqual(manifest['declaredArchiveVerification']['sampleDeclarations'], 1)
        self.assertIn('mismatched declared archive', str(manifest['declaredArchiveVerification']['errors']))
        self.assertTrue((self.destination / 'records' / log.parent.name / log.name).exists())

    def test_driver_complete_claim_missing_raw_hash_is_rejected(self):
        driver = self.driver(passed=True)
        del driver['records'][0]['rawReportSha256']
        self.write_json('latest-combined-comparison.json', driver)
        self.failed_manifest()

    def test_driver_cannot_promote_no_run_or_mismatched_raw(self):
        driver = self.driver()
        driver.update(complete=True, status='passed')
        self.write_json('latest-combined-comparison.json', driver)
        self.failed_manifest()

    def test_source_change_after_copy_fails_without_deleting_sources(self):
        source = self.results / 'environment.txt'
        source.write_bytes(b'first')
        original = collector._copy_one

        def mutate(*args):
            row = original(*args)
            source.write_bytes(b'changed')
            return row

        with patch.object(collector, '_copy_one', side_effect=mutate):
            manifest = self.failed_manifest()
        self.assertFalse(manifest['copyComplete'])
        self.assertEqual(source.read_bytes(), b'changed')
        self.assertEqual((self.destination / 'results/environment.txt').read_bytes(), b'first')

    def test_ownership_and_modes_applied_only_to_owned_copies(self):
        source = self.results / 'environment.txt'
        source.write_text('keep mode and owner')
        source.chmod(0o600)
        before = source.stat()
        fchmod, fchown = os.fchmod, os.fchown

        def checked(function):
            def operation(fd, *args):
                target = Path(os.readlink(f'/proc/self/fd/{fd}'))
                self.assertTrue(target == self.destination or target.is_relative_to(self.destination))
                return function(fd, *args)
            return operation

        with patch.object(collector.os, 'fchmod', side_effect=checked(fchmod)), \
                patch.object(collector.os, 'fchown', side_effect=checked(fchown)), \
                patch.object(collector.os, 'chmod', side_effect=AssertionError('path chmod forbidden')), \
                patch.object(collector.os, 'chown', side_effect=AssertionError('path chown forbidden')):
            self.collect()
        after = source.stat()
        self.assertEqual((after.st_ino, after.st_mode, after.st_uid, after.st_gid),
                         (before.st_ino, before.st_mode, before.st_uid, before.st_gid))

    def test_collect_cli_refuses_non_github_and_wrong_current_roots(self):
        args = ['collect', '--results', str(self.results), '--temporary', str(self.temporary),
                '--destination', str(self.destination), '--uid', '1000', '--gid', '1000']
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false', 'RUNNER_TEMP': str(self.temporary)}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(collector.main(args), 1)
        with patch.object(collector.os, 'geteuid', return_value=0), \
                patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'RUNNER_TEMP': str(self.temporary)}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(collector.main(args), 1)
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
