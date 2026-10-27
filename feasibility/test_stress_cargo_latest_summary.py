#!/usr/bin/env python3
"""Synthetic, inert evidence-reader tests only; no products, Docker, mounts or builds."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from stress_cargo_latest_summary import (
    ARTIFACT_PHASES, BUILD_PHASES, MANIFEST_FILE, MANIFEST_SCHEMA, PACKAGES,
    PHASES, PINS, PRODUCTS, PROGRAM_OUTPUTS, PROTOCOL_SHA, SCHEMA, digest,
    normalize_tree, strict_json, summarize,
)


def dump(path, value):
    body = (json.dumps(value, indent=2) + '\n').encode()
    path.write_bytes(body)
    return digest(body)


def source_tree():
    return {'schema': 'cargo-full-tree-v1', 'entries': [
        {'path': '.', 'type': 'directory', 'mode': 0o750, 'mtime_ns': 1700000000000000000},
        {'path': 'Cargo.toml', 'type': 'file', 'mode': 0o640, 'mtime_ns': 1700000000000000000,
         'size': 1, 'sha256': digest(b'x')}], 'hardlink_groups': [['Cargo.toml']]}


def checkpoint_tree():
    tree = source_tree()
    stamp = 1700000000123456789
    for name in ('target', 'target/restore-probe'):
        tree['entries'].append({'path': name, 'type': 'directory', 'mode': 0o755, 'mtime_ns': stamp})
    for name in ('hardlink', 'original'):
        tree['entries'].append({'path': 'target/restore-probe/' + name, 'type': 'file', 'mode': 0o640,
                                'mtime_ns': stamp, 'size': len(b'cargo checkpoint hardlink probe\n'),
                                'sha256': digest(b'cargo checkpoint hardlink probe\n')})
    tree['entries'].append({'path': 'target/restore-probe/symlink', 'type': 'symlink', 'mode': 0o777,
                            'mtime_ns': stamp, 'target': 'original'})
    tree['entries'].sort(key=lambda entry: entry['path'])
    tree['hardlink_groups'].append(['target/restore-probe/hardlink', 'target/restore-probe/original'])
    return tree


def string_ns(tree):
    value = copy.deepcopy(tree)
    for entry in value['entries']:
        entry['mtime_ns'] = str(entry['mtime_ns'])
    return value


def fixture(base):
    results = base / 'results'
    records = base / 'records'
    results.mkdir()
    records.mkdir()
    manifest = {'schema': MANIFEST_SCHEMA,
                'sprig': {'sha': PINS['sprig-writable'], 'ref': 'main', 'binary': '/sources/sprig/target/release/sprig',
                          'sourcePath': '/sources/sprig', 'binarySha256': '1' * 64},
                'layerfs': {'sha': PINS['layerfs'], 'ref': 'main', 'binary': '/sources/layerfs/target/release/layerfs-daemon',
                            'sourcePath': '/sources/layerfs', 'binarySha256': '2' * 64,
                            'sdkPath': '/sources/layerfs/api/agent/src/index.js', 'sdkSha256': '3' * 64,
                            'nativeAddonPath': '/sources/layerfs/engine/crates/layerfs-node/layerfs.node', 'nativeAddonSha256': '4' * 64}}
    manifest_hash = dump(results / MANIFEST_FILE, manifest)
    initial = source_tree()
    fixture_manifest = {'schema': 'sprig-stress-cargo-v2', 'protocolSha256': PROTOCOL_SHA,
                        'crates': 16, 'totalPackages': 17, 'packages': PACKAGES, 'initial': initial,
                        'expectedStdoutBefore': '269\n', 'expectedStdoutAfter': '3400\n'}
    fixture_hash = dump(results / 'stress-cargo-manifest.json', fixture_manifest)
    dump(results / 'stress-cargo-oracle.json', initial)
    shared = {'image': 'sha256:' + 'a' * 64, 'productionSha': PINS['sprig-writable'], 'comparatorSha': PINS['layerfs'],
              'protocolSha256': PROTOCOL_SHA, 'fixtureManifestSha256': fixture_hash,
              'imageBytes': 4 * 1024**3, 'resourceProtocol': 'sprig-cargo-resource-4g-v1',
              'directManifest': manifest, 'directManifestSha256': manifest_hash,
              'sharedJobBudget': {'startedEpochSeconds': 100, 'deadlineEpochSeconds': 2500,
                                  'minimumSampleSeconds': 180, 'cleanupReserveSeconds': 300}}
    paths = []
    for mode in (0, 1):
        report = {'schema': SCHEMA, 'complete': True, 'status': 'passed', 'incremental': mode,
                  'rounds': 2, 'expectedRecords': 4, **copy.deepcopy(shared), 'records': []}
        if mode:
            report['previousGate'] = {'path': str(paths[0]), 'sha256': digest(paths[0].read_bytes())}
        for round_ in range(2):
            order = PRODUCTS[::-1] if (mode + round_) % 2 else PRODUCTS
            for product in order:
                layerfs = product == 'layerfs'
                item = manifest['layerfs' if layerfs else 'sprig']
                factor = 1.0 if layerfs else 1.1
                oracle = checkpoint_tree()
                sample = {key: True for key in ('ok', 'fullRestoredTreeVerified', 'originalMainViewUnchanged',
                                               'sourceUnchanged', 'allAcknowledgedIdsPresent')}
                sample.update(prototype_only=False, production_sha=item['sha'], incremental=mode,
                              image=shared['image'], protocolSha256=PROTOCOL_SHA,
                              workload='stress-cargo-dag16-v2', protocol='sprig-stress-cargo-protocol-v2', packages=PACKAGES,
                              backend='fuse' if layerfs else 'writable', remainingMounts=[], remainingContainers=[],
                              phase_seconds={phase: factor for phase in PHASES}, full_task_seconds=9 * factor,
                              activeSpace={'filesystemUsedBytes': int(1000000 * factor)},
                              fixtureOracle=string_ns(initial) if layerfs else copy.deepcopy(initial),
                              checkpointTreeOracle=string_ns(oracle) if layerfs else copy.deepcopy(oracle),
                              cargoBuildObservations=[], artifactChecks=[], commands=[], completeLogArchive=[],
                              compilerVersionOutput='rustc 1.90.0 (fixed)\nrelease: 1.90.0\ncargo 1.90.0 (fixed)\n')
                sample['phase_seconds']['checkpoint'] = 2 * factor
                if layerfs:
                    revision = '12' + 'b' * 64
                    sample.update(product='layerfs', fixtureManifestSha256=fixture_hash, initialHead='32' + 'c' * 64,
                                  checkpoint={'kind': 'Committed', 'head': revision, 'commit': {'id': revision}},
                                  restoredRevision=revision, remainingMountsKnown=True, remainingContainersKnown=True,
                                  fixtureOracleRaw=json.dumps(initial) + '\n',
                                  checkpointTreeOracleRaw=json.dumps(oracle) + '\n',
                                  compilerContainerIdentity={'id': 'd' * 64, 'image': shared['image'], 'project': 'synthetic'},
                                  snapshotOracleComparisons=[])
                    sample['checkpointTreeOracleSha256'] = digest(sample['checkpointTreeOracleRaw'].encode())
                    views = [{'name': name, 'sandbox': '1', 'path': f'/workspaces/{i + 1}', 'image': shared['image']}
                             for i, name in enumerate(('import-main', 'work', 'second'))]
                    sample['lifecycle'] = {'normalUnmountOnly': True, 'cleanup': {'complete': True},
                                           'committedHistoryRetained': True, 'fileTreesRetainedAtSpace': True,
                                           'activeAtSpace': {'views': views, 'controlProcessesRunning': 1,
                                               'workspaces': [{'path': view['path'], 'activity': 'Idle',
                                                               'base': revision if view['name'] != 'import-main' else None} for view in views],
                                               'sandboxes': [{'sandbox': '1', 'image': shared['image'], 'workspaces': 3}],
                                               'fileTreesRetained': True, 'cargoRestoreReadbackComplete': True,
                                               'allRuntimeLogsAndJournalsInsideMeasuredStore': True, 'verifiedAfterSpace': True}}
                    sample['phase_seconds']['compiler_image_verify'] = factor
                else:
                    sample.update(testOnly=False, binarySha256=item['binarySha256'], compressionPolicy='auto (default init)',
                                  checkpoint={'committed': True, 'revision': 'b' * 64}, restoredRevision='b' * 64,
                                  convenience_seconds={'checkpointCompilerQuiescePlusProduct': 2 * factor,
                                                       'restoreToCompilerReady': factor},
                                  compilerSessions=[{'removed': True, 'uncertain': False,
                                                     'naturalExitAndPidGoneVerified': True} for _ in range(4)],
                                  lifecycle={'cleanup': {'complete': True}, 'activeAtSpace': {
                                      'retainedGenerationCount': 4, 'foregroundFuseProcesses': [{}, {}, {}],
                                      'views': [{'name': 'main'}, {'name': 'work'},
                                                {'name': 'second', 'generation': 'g2', 'path': '/second'}],
                                      'compilerContainer': {'count': 1, 'image': shared['image'],
                                          'inspection': {'state': {'Running': True}}, 'generation': 'g2', 'tree': '/second'}}})
                    sample['phase_seconds']['transport_stop_before_checkpoint'] = factor
                directory = records / f'inc{mode}' / f'{product}-{round_}.jsonl.logs'
                directory.mkdir(parents=True)

                def command(purpose, stdout='', stderr=''):
                    index = len(sample['commands'])
                    row = {'purpose': purpose, 'returncode': 0, 'stdout': stdout, 'stderr': stderr}
                    for field in ('stdout', 'stderr'):
                        name = f'{index:06}-{purpose}.{field}'
                        source = f'/original/mount/{mode}/{product}/{round_}/logs/{name}'
                        body = row[field].encode()
                        (directory / name).write_bytes(body)
                        row[field + 'Path'] = source
                        sample['completeLogArchive'].append({'source': source,
                            'archived': f'/original/stress-cargo-records/inc{mode}/{product}-{round_}.jsonl.logs/{name}',
                            'bytes': len(body), 'sha256': digest(body)})
                    sample['commands'].append(row)
                    return row

                def build(purpose):
                    fresh = purpose in ('noop_build', 'restored_rebuild')
                    kind = 'Fresh' if fresh else 'Compiling'
                    row = command(purpose, stderr=''.join(f'   {kind} {name} v0.1.0 (/work/{name})\n' for name in PACKAGES))
                    sample['cargoBuildObservations'].append({'phase': purpose, 'returncode': 0,
                        'freshPackages': PACKAGES if fresh else [], 'compilingPackages': [] if fresh else PACKAGES,
                        'stdoutPath': row['stdoutPath'], 'stderrPath': row['stderrPath']})

                def artifacts(purpose):
                    value = {'ok': True, 'hardlinkProbe': True, 'exactMtime': True,
                             'buildValue': 1 if purpose in ('clean_artifacts', 'noop_artifacts') else 2,
                             'generatedFiles': ['target/debug/build/node000/out/generated.rs']}
                    command(purpose, json.dumps(value) + '\n')
                    sample['artifactChecks'].append({'phase': purpose, **value})

                if layerfs:
                    command('compiler_container_inspect', json.dumps([{'Id': 'd' * 64, 'Image': shared['image'],
                        'State': {'Running': True}, 'Config': {'Labels': {'layerfs.project': 'synthetic'}}}]) + '\n')
                command('fixture_verify', json.dumps(initial) + '\n')
                command('toolchain_verify', sample['compilerVersionOutput'])
                for prefix in ('clean', 'noop', 'edit'):
                    build(prefix + '_build')
                    artifacts(prefix + '_artifacts')
                    command(prefix + '_execute', PROGRAM_OUTPUTS[prefix + '_execute'])
                command('pre_checkpoint_oracle', json.dumps(oracle) + '\n')
                command('restore_verify', json.dumps(oracle) + '\n')
                artifacts('restored_artifacts')
                command('restored_execute', PROGRAM_OUTPUTS['restored_execute'])
                build('restored_rebuild')
                artifacts('restored_rebuild_artifacts')
                command('restored_rebuild_execute', PROGRAM_OUTPUTS['restored_rebuild_execute'])
                command('main_unchanged', json.dumps(initial) + '\n')
                command('source_unchanged', json.dumps(initial) + '\n')
                if layerfs:
                    for purpose, expected in (('fixture_verify', sample['fixtureOracleRaw']),
                                              ('main_unchanged', sample['fixtureOracleRaw']),
                                              ('restore_verify', sample['checkpointTreeOracleRaw'])):
                        raw = next(c['stdout'] for c in sample['commands'] if c['purpose'] == purpose)
                        sample['snapshotOracleComparisons'].append({'purpose': purpose, 'ok': True,
                            'entries': len(json.loads(raw)['entries']), 'snapshotSha256': digest(raw.encode()),
                            'expectedSha256': digest(expected.encode())})
                name = f'stress-cargo-{product}-inc{mode}-{round_}.json'
                raw_hash = dump(results / name, sample)
                admission = {'startedEpochSeconds': 100, 'deadlineEpochSeconds': 2500,
                             'remainingSeconds': 2100, 'workReserveSeconds': 180,
                             'cleanupReserveSeconds': 300, 'requiredSeconds': 480, 'admitted': True}
                report['records'].append({'product': product, 'round': round_, 'incremental': mode,
                    'correct': True, 'status': 'passed', 'sampleReturncode': 0, 'sample': copy.deepcopy(sample),
                    'rawReportPath': 'results/' + name, 'rawReportSha256': raw_hash,
                    'verifiedProductInputs': copy.deepcopy(item), 'budgetAdmission': copy.deepcopy(admission),
                    'postRuntimeBudgetAdmission': copy.deepcopy(admission),
                    'wholeSampleSubprocessWallSeconds': (10 + round_) * factor, 'runtimeSetupSeconds': factor})
        path = results / f'stress-cargo-comparison-{mode}.json'
        dump(path, report)
        paths.append(path)
    return paths, records


def change_report(paths, mode, mutate):
    report = json.loads(paths[mode].read_text())
    mutate(report)
    dump(paths[mode], report)
    if mode == 0:
        other = json.loads(paths[1].read_text())
        other['previousGate']['sha256'] = digest(paths[0].read_bytes())
        dump(paths[1], other)


def change_sample(paths, mode, index, mutate):
    report = json.loads(paths[mode].read_text())
    row = report['records'][index]
    raw = paths[mode].parent / Path(row['rawReportPath']).name
    sample = json.loads(raw.read_text())
    mutate(sample)
    row['rawReportSha256'] = dump(raw, sample)
    row['sample'] = copy.deepcopy(sample)
    dump(paths[mode], report)
    if mode == 0:
        other = json.loads(paths[1].read_text())
        other['previousGate']['sha256'] = digest(paths[0].read_bytes())
        dump(paths[1], other)


def change_manifest(paths, mutate):
    """Rebind both modes and inputs, so rejection tests exercise semantic gates."""
    manifest_path = paths[0].parent / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    mutate(manifest)
    manifest_hash = dump(manifest_path, manifest)
    for mode in (0, 1):
        def update(report):
            report.update(directManifest=copy.deepcopy(manifest), directManifestSha256=manifest_hash)
            for row in report['records']:
                key = 'sprig' if row['product'] == 'sprig-writable' else 'layerfs'
                row['verifiedProductInputs'] = copy.deepcopy(manifest[key])
        change_report(paths, mode, update)


def replace_command(sample, archives, mode, product, round_, purpose, field, value):
    row = next(c for c in sample['commands'] if c['purpose'] == purpose)
    row[field] = value
    item = next(a for a in sample['completeLogArchive'] if a['source'] == row[field + 'Path'])
    body = value.encode()
    (archives / f'inc{mode}' / f'{product}-{round_}.jsonl.logs' / Path(item['archived']).name).write_bytes(body)
    item.update(bytes=len(body), sha256=digest(body))


class LatestDirectSummaryTests(unittest.TestCase):
    def assert_blocked(self, result):
        self.assertFalse(result['complete'])
        self.assertIsNone(result['comparisons'])
        self.assertIsNone(result['unmatchedMetrics'])
        self.assertIsNone(result['slowerOrLargerPairs'])
        self.assertTrue(result['errors'])

    def test_all8_exact_main_pairing_separate_modes_and_unmatched_costs(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            result = summarize(paths, archives)
            self.assertTrue(result['complete'], result['errors'])
            self.assertEqual(result['schema'], 'sprig-stress-cargo-latest-direct-summary-v2')
            self.assertEqual(SCHEMA, 'sprig-stress-cargo-latest-direct-v2')
            self.assertEqual(MANIFEST_SCHEMA, 'sprig-cargo-latest-direct-identity-v2')
            self.assertEqual(PINS, {'sprig-writable': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
                                    'layerfs': 'caebd268dc376865e964f33f78047f7918763190'})
            self.assertEqual(len(result['records']), 8)
            self.assertEqual(result['missingRecords'], [])
            self.assertEqual(result['identity']['comparatorSha'], PINS['layerfs'])
            for mode in ('inc0', 'inc1'):
                metric = result['comparisons'][mode]['wholeSamplerSeconds']
                self.assertEqual(metric['sprig']['n'], 2)
                self.assertIsNone(metric['sprig']['p95'])
                self.assertIsNone(metric['layerfs']['p99'])
                self.assertAlmostEqual(metric['geometricMeanPairedRatio'], 1.1)
                self.assertEqual(len(metric['pairs']), 2)
                self.assertEqual(len(metric['orderStrata']['layerfs']), 1)
                self.assertTrue(result['slowerOrLargerPairs'][mode])
                self.assertNotIn('convenience.restoreToCompilerReady', result['comparisons'][mode])
                self.assertIn('convenience.restoreToCompilerReady', result['unmatchedMetrics'][mode]['sprig-writable'])
                self.assertIn('phase.compiler_image_verify', result['unmatchedMetrics'][mode]['layerfs'])
            self.assertEqual(result['comparisons']['inc0']['wholeSamplerSeconds']['pairs'][0]['firstProduct'], 'sprig-writable')
            self.assertEqual(result['comparisons']['inc1']['wholeSamplerSeconds']['pairs'][0]['firstProduct'], 'layerfs')

    def test_old_direct_report_and_manifest_schemas_are_not_latest(self):
        for kind in ('report', 'manifest'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                if kind == 'report':
                    for mode in (0, 1):
                        change_report(paths, mode, lambda r: r.update(schema='sprig-stress-cargo-latest-direct-v1'))
                else:
                    change_manifest(paths, lambda m: m.update(schema='sprig-cargo-latest-direct-identity-v1'))
                result = summarize(paths, archives)
                self.assert_blocked(result)
                self.assertEqual(len(result['records']), 8)
                self.assertTrue(any('schema' in error for error in result['errors']))

    def test_old_ad789_pin_is_rejected_at_each_independent_binding(self):
        old_pin = 'ad78914e36b258b360daf13aec164b5655814689'
        for kind in ('report', 'manifest', 'verified-input', 'raw', 'all'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                if kind in ('manifest', 'all'):
                    change_manifest(paths, lambda m: m['layerfs'].update(sha=old_pin))
                for mode in (0, 1):
                    if kind in ('report', 'all'):
                        change_report(paths, mode, lambda r: r.update(comparatorSha=old_pin))
                    if kind in ('verified-input', 'raw', 'all'):
                        report = json.loads(paths[mode].read_text())
                        for index, row in enumerate(report['records']):
                            if row['product'] != 'layerfs':
                                continue
                            if kind == 'verified-input':
                                change_report(paths, mode, lambda r, index=index:
                                    r['records'][index]['verifiedProductInputs'].update(sha=old_pin))
                            else:
                                change_sample(paths, mode, index, lambda s: s.update(production_sha=old_pin))
                result = summarize(paths, archives)
                self.assert_blocked(result)
                self.assertEqual(len(result['records']), 8)

    def test_old_layerfs_build_sdk_and_addon_paths_fail_even_when_rebound(self):
        old_paths = {'binary': '/sources/layerfs/core/target/release/layerfs-daemon',
                     'sdkPath': '/sources/layerfs/api/agent/sdk/src/index.js',
                     'nativeAddonPath': '/sources/layerfs/api/binding/layerfs.node'}
        for key, value in old_paths.items():
            with self.subTest(field=key), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_manifest(paths, lambda m: m['layerfs'].update({key: value}))
                result = summarize(paths, archives)
                self.assert_blocked(result)
                self.assertEqual(len(result['records']), 8)
                self.assertTrue(any('fixed source' in error for error in result['errors']))

    def test_decimal_string_ns_and_real_layerfs_absent_testonly_are_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            raw = json.loads((paths[0].parent / 'stress-cargo-layerfs-inc0-0.json').read_text())
            self.assertNotIn('testOnly', raw)
            self.assertNotIn('binarySha256', raw)
            self.assertIsInstance(raw['checkpointTreeOracle']['entries'][0]['mtime_ns'], str)
            self.assertIsInstance(json.loads(raw['checkpointTreeOracleRaw'])['entries'][0]['mtime_ns'], int)
            self.assertTrue(summarize(paths, archives)['complete'])

    def test_js_rounded_embedded_tree_is_not_authoritative(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            change_report(paths, 0, lambda report: report['records'][0]['sample']['checkpointTreeOracle']['entries'][0].update(mtime_ns=1700000000000000001))
            result = summarize(paths, archives)
            self.assertTrue(result['complete'], result['errors'])

    def test_layerfs_one_ns_structured_mismatch_fails_even_with_new_outer_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            change_sample(paths, 0, 1, lambda sample: sample['checkpointTreeOracle']['entries'][0].update(mtime_ns='1700000000000000001'))
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertTrue(any('exact-ns complete tree' in error for error in result['errors']))

    def test_layerfs_one_ns_archived_restore_mismatch_survives_rehashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            def mutate(sample):
                oracle = json.loads(next(c['stdout'] for c in sample['commands'] if c['purpose'] == 'restore_verify'))
                oracle['entries'][0]['mtime_ns'] += 1
                replace_command(sample, archives, 0, 'layerfs', 0, 'restore_verify', 'stdout', json.dumps(oracle) + '\n')
            change_sample(paths, 0, 1, mutate)
            self.assert_blocked(summarize(paths, archives))

    def test_integer_or_float_substitution_for_layerfs_structured_ns_is_refused(self):
        for value in (1700000000000000000, 1.7e18, True, '1.7e18', '01700000000000000000'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_sample(paths, 0, 1, lambda sample: sample['checkpointTreeOracle']['entries'][0].update(mtime_ns=value))
                self.assert_blocked(summarize(paths, archives))

    def test_failures_and_missing_attempts_retained_no_partial_ratios(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            def mutate(report):
                report.update(complete=False, status='failed', error={'message': 'first failure retained'})
                report['records'][2].update(correct=False, status='cleanup_blocked', error={'message': 'unknown exec'},
                                            recoveryMetadata={'cleanupAdmissionBlocked': 'unknown exec'})
                report['records'].pop()
            change_report(paths, 0, mutate)
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertEqual(len(result['records']), 7)
            self.assertEqual(len(result['missingRecords']), 1)
            self.assertEqual(result['records'][2]['error']['message'], 'unknown exec')
            self.assertEqual(result['reports'][0]['error']['message'], 'first failure retained')

    def test_missing_mode_retains_other_four_and_marks_four_unrecorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            paths[1].unlink()
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertEqual(len(result['records']), 4)
            self.assertEqual(len(result['missingRecords']), 4)

    def test_fixed_identity_order_budget_proof_and_raw_paths_fail_closed(self):
        mutations = [lambda r: r.update(schema='sprig-stress-cargo-comparison-v2'),
                     lambda r: r.update(rounds=3), lambda r: r.update(expectedRecords=8),
                     lambda r: r.update(comparatorSha='9f97a7ec95b662e9cb288704afa165feff132cfa'),
                     lambda r: r.update(imageBytes=8 * 1024**3),
                     lambda r: r.update(protocolSha256='0' * 64),
                     lambda r: r.update(experimentSpec={'profile': 'ordinary'}),
                     lambda r: r['sharedJobBudget'].update(deadlineEpochSeconds=2501),
                     lambda r: r['records'].reverse(),
                     lambda r: r['records'][0].update(round=False),
                     lambda r: r['records'][0].update(rawReportPath='../outside.json'),
                     lambda r: r['records'][0]['verifiedProductInputs'].update(binarySha256='0' * 64),
                     lambda r: r['records'][0]['postRuntimeBudgetAdmission'].update(remainingSeconds=479)]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_report(paths, 0, mutate)
                self.assert_blocked(summarize(paths, archives))

    def test_malformed_or_wrong_inc0_prerequisite_never_enables_ratios(self):
        for value in (None, [], True, {'sha256': '0' * 64}):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_report(paths, 1, lambda report: report.update(previousGate=value))
                result = summarize(paths, archives)
                self.assert_blocked(result)
                self.assertEqual(len(result['records']), 8)

    def test_manifest_hash_is_original_bytes_not_reserialized_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            file = paths[0].parent / MANIFEST_FILE
            file.write_bytes(file.read_bytes() + b' ')
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertTrue(any('direct manifest raw' in error for error in result['errors']))

    def test_raw_hash_archive_hash_and_missing_stderr_are_rejected(self):
        for kind in ('raw', 'archive', 'missing'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                if kind == 'raw':
                    file = paths[0].parent / 'stress-cargo-layerfs-inc0-0.json'
                    file.write_bytes(file.read_bytes() + b' ')
                else:
                    file = next(archives.glob('inc0/layerfs-0.jsonl.logs/*source_unchanged.stderr'))
                    file.unlink() if kind == 'missing' else file.write_bytes(b'changed')
                self.assert_blocked(summarize(paths, archives))

    def test_layerfs_cleanup_inventory_and_checkpoint_are_strict(self):
        mutations = [lambda s: s.update(testOnly=True), lambda s: s.update(remainingMountsKnown=False),
                     lambda s: s.update(remainingContainersKnown=False), lambda s: s.update(remainingContainers=['retained']),
                     lambda s: s['lifecycle']['cleanup'].update(complete=False),
                     lambda s: s['lifecycle'].update(committedHistoryRetained=False),
                     lambda s: s['lifecycle']['activeAtSpace']['workspaces'][1].update(base='12' + 'f' * 64),
                     lambda s: s['compilerContainerIdentity'].update(image='sha256:' + 'f' * 64),
                     lambda s: s['checkpoint'].update(head='12' + 'f' * 64),
                     lambda s: s.update(error={'uncertain': True}),
                     lambda s: s.update(convenience_seconds={'restoreToCompilerReady': 0})]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_sample(paths, 0, 1, mutate)
                self.assert_blocked(summarize(paths, archives))

    def test_raw_cargo_program_toolchain_and_source_are_independently_verified(self):
        replacements = [('noop_build', 'stderr', '   Fresh node000 v0.1.0 (/work/node000)\n'),
                        ('edit_execute', 'stdout', '269\n'),
                        ('toolchain_verify', 'stdout', 'rustc 1.99.1 (other)\ncargo 1.99.1 (other)\n'),
                        ('source_unchanged', 'stdout', json.dumps(checkpoint_tree()) + '\n')]
        for purpose, field, value in replacements:
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_sample(paths, 0, 1, lambda sample: replace_command(sample, archives, 0, 'layerfs', 0, purpose, field, value))
                self.assert_blocked(summarize(paths, archives))

    def test_sprig_uses_existing_exact_validator_and_all_common_evidence(self):
        mutations = [lambda s: s.update(testOnly=True), lambda s: s['compilerSessions'][0].update(uncertain=True),
                     lambda s: s['checkpointTreeOracle']['entries'][0].update(mtime_ns=1700000000000000001),
                     lambda s: s['cargoBuildObservations'][1].update(freshPackages=PACKAGES[:-1]),
                     lambda s: s['phase_seconds'].update(clean_build=True),
                     lambda s: s['artifactChecks'][0].update(exactMtime=False),
                     lambda s: s.update(normalPressure={})]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temporary:
                paths, archives = fixture(Path(temporary))
                change_sample(paths, 0, 0, mutate)
                self.assert_blocked(summarize(paths, archives))

    def test_duplicate_json_keys_and_nonfinite_json_rejected(self):
        for body in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                strict_json(body)

    def test_tree_paths_permissions_contents_and_hardlink_partition_are_strict(self):
        mutations = [lambda t: t['entries'].append(copy.deepcopy(t['entries'][0])),
                     lambda t: t['entries'][1].update(path='../escape'),
                     lambda t: t['entries'][1].update(mode=True),
                     lambda t: t['entries'][1].update(size=1.5),
                     lambda t: t['hardlink_groups'].pop(),
                     lambda t: t['entries'][4].update(sha256='f' * 64)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = checkpoint_tree()
                mutate(value)
                with self.assertRaises(ValueError):
                    normalize_tree(value, strings=False)

    def test_zero_denominator_retains_pair_without_geometric_ratio(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, archives = fixture(Path(temporary))
            for mode in (0, 1):
                change_report(paths, mode, lambda report: [row.update(runtimeSetupSeconds=0)
                    for row in report['records'] if row['product'] == 'layerfs'])
            result = summarize(paths, archives)
            self.assertTrue(result['complete'], result['errors'])
            metric = result['comparisons']['inc0']['runtimeSetupSeconds']
            self.assertIsNone(metric['geometricMeanPairedRatio'])
            self.assertEqual(len(metric['pairs']), 2)
            self.assertTrue(all(pair['sprigOverLayerfs'] is None for pair in metric['pairs']))


if __name__ == '__main__':
    unittest.main()
