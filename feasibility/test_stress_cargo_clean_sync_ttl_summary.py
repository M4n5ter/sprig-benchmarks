#!/usr/bin/env python3
"""Synthetic offline evidence only: these tests never execute products or mounts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from stress_cargo_ab_summary import PHASES
from stress_cargo_latest_summary import PROGRAM_OUTPUTS
from test_stress_cargo_latest_summary import source_tree, checkpoint_tree
from stress_cargo_clean_sync_ttl_summary import (
    CLEANUP, EDGES, EXPERIMENT, IMAGE_BYTES, MANIFEST_FILE, MIB, PACKAGES,
    PINS, PLAN_FILE, PLAN_SCHEMA, PRODUCTS, PROTOCOL_SHA, SCHEMA, SUMMARY_SCHEMA,
    digest, schedule, strict_json, summarize, validate_products,
)

DIRECTORY_PINS = {'sprig-baseline': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
                  'sprig-count': '104497aefcadc41b1528d7263039c977b77305f8',
                  'sprig-narrow': '5ef2539af3f07b0a2fc87b3d02f7324a827e8798'}


def dump(path, value):
    body = (json.dumps(value, indent=2) + '\n').encode()
    path.write_bytes(body)
    return digest(body)


def fixture(base):
    results, archives = base / 'results', base / 'records'
    results.mkdir()
    archives.mkdir()
    products = [{'label': label, 'sha': sha, 'binary': f'/sources/{label}/target/release/sprig',
                 'sourcePath': f'/sources/{label}', 'binarySha256': str(index + 1) * 64}
                for index, (label, sha) in enumerate(PINS.items())]
    initial = source_tree()
    fixture_manifest = {'schema': 'sprig-stress-cargo-v2', 'protocolSha256': PROTOCOL_SHA,
                        'crates': 16, 'totalPackages': 17, 'packages': PACKAGES, 'initial': initial,
                        'expectedStdoutBefore': '269\n', 'expectedStdoutAfter': '3400\n'}
    fixture_hash = dump(results / 'stress-cargo-manifest.json', fixture_manifest)
    dump(results / 'stress-cargo-oracle.json', initial)
    plan = {'schema': PLAN_SCHEMA, 'abcExperiment': copy.deepcopy(EXPERIMENT),
            'abcProducts': copy.deepcopy(products), 'records': schedule()}
    shared = {'image': 'sha256:' + 'a' * 64, 'protocolSha256': PROTOCOL_SHA,
              'fixtureManifestSha256': fixture_hash, 'imageBytes': IMAGE_BYTES,
              'resourceProtocol': 'sprig-cargo-resource-4g-v1', 'abcProducts': products,
              'abcManifestSha256': dump(results / MANIFEST_FILE, products),
              'abcPlanSha256': dump(results / PLAN_FILE, plan), 'abcExperiment': copy.deepcopy(EXPERIMENT),
              'sharedJobBudget': {'startedEpochSeconds': 100, 'deadlineEpochSeconds': 2500,
                                  'minimumSampleSeconds': 180, 'cleanupReserveSeconds': 300}}
    pilots = [{'incremental': mode, 'targetAllocatedBytes': 1024**2} for mode in (0, 1)]
    dump(results / 'stress-cargo-capacity.json', {'schema': 'sprig-stress-cargo-capacity-v1',
         **{key: shared[key] for key in ('image', 'protocolSha256', 'fixtureManifestSha256')},
         'toolchain': {'rustc': '1.90.0', 'cargo': '1.90.0'}, 'pilots': pilots})
    paths = []
    for mode in (0, 1):
        report = {'schema': SCHEMA, 'complete': True, 'status': 'passed', 'incremental': mode,
                  'rounds': 6, 'expectedRecords': 18, **copy.deepcopy(shared),
                  'capacityPilot': copy.deepcopy(pilots[mode]), 'records': [], 'previousGate': None}
        if mode:
            report['previousGate'] = {'path': str(paths[0]), 'sha256': digest(paths[0].read_bytes())}
        for expected in schedule(mode):
            label, round_ = expected['product'], expected['round']
            item = next(product for product in products if product['label'] == label)
            factor = {'sprig-baseline': 1.0, 'sprig-clean-sync': 1.1, 'sprig-read-ttl': 0.9}[label]
            oracle = checkpoint_tree()
            sample = {key: True for key in ('ok', 'fullRestoredTreeVerified', 'originalMainViewUnchanged',
                                           'sourceUnchanged', 'allAcknowledgedIdsPresent')}
            sample.update(testOnly=False, prototype_only=False, incremental=mode, production_sha=item['sha'],
                          binarySha256=item['binarySha256'], image=shared['image'], protocolSha256=PROTOCOL_SHA,
                          workload='stress-cargo-dag16-v2', protocol='sprig-stress-cargo-protocol-v2', packages=PACKAGES,
                          backend='writable', compressionPolicy='auto (default init)', remainingMounts=[], remainingContainers=[],
                          phase_seconds={phase: factor for phase in PHASES}, full_task_seconds=9 * factor,
                          convenience_seconds={'checkpointCompilerQuiescePlusProduct': 2 * factor, 'restoreToCompilerReady': factor},
                          activeSpace={'filesystemUsedBytes': int(1000000 * factor)}, fixtureOracle=copy.deepcopy(initial),
                          checkpointTreeOracle=oracle, checkpoint={'committed': True, 'revision': 'b' * 64}, restoredRevision='b' * 64,
                          compilerSessions=[{'removed': True, 'uncertain': False, 'naturalExitAndPidGoneVerified': True} for _ in range(4)],
                          lifecycle={'cleanup': {'complete': True}, 'activeAtSpace': {
                              'retainedGenerationCount': 4, 'foregroundFuseProcesses': [{}, {}, {}],
                              'views': [{'name': 'main'}, {'name': 'work'}, {'name': 'second', 'generation': 'g2', 'path': '/second'}],
                              'compilerContainer': {'count': 1, 'image': shared['image'], 'inspection': {'state': {'Running': True}},
                                                    'generation': 'g2', 'tree': '/second'}}},
                          cargoBuildObservations=[], artifactChecks=[], commands=[], completeLogArchive=[],
                          compilerVersionOutput='rustc 1.90.0 (fixed)\nrelease: 1.90.0\ncargo 1.90.0 (fixed)\n')
            sample['phase_seconds']['checkpoint'] = 2 * factor
            directory = archives / f'inc{mode}' / f'{label}-{round_}.jsonl.logs'
            directory.mkdir(parents=True)

            def command(purpose, stdout='', stderr=''):
                index = len(sample['commands'])
                row = {'purpose': purpose, 'returncode': 0, 'stdout': stdout, 'stderr': stderr}
                for field in ('stdout', 'stderr'):
                    name = f'{index:06}-{purpose}.{field}'
                    source = f'/original/mount/{mode}/{label}/{round_}/logs/{name}'
                    body = row[field].encode()
                    (directory / name).write_bytes(body)
                    row[field + 'Path'] = source
                    sample['completeLogArchive'].append({'source': source,
                        'archived': f'/original/stress-cargo-records/inc{mode}/{label}-{round_}.jsonl.logs/{name}',
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
            name = f'stress-cargo-{label}-inc{mode}-{round_}.json'
            admission = {'startedEpochSeconds': 100, 'deadlineEpochSeconds': 2500, 'remainingSeconds': 2100,
                         'workReserveSeconds': 180, 'cleanupReserveSeconds': 300, 'requiredSeconds': 480, 'admitted': True}
            report['records'].append({**copy.deepcopy(expected), 'correct': True, 'status': 'passed', 'sampleReturncode': 0,
                'sample': copy.deepcopy(sample), 'rawReportPath': 'results/' + name, 'rawReportSha256': dump(results / name, sample),
                'verifiedProductInputs': copy.deepcopy(item), 'verifiedProductInputsAfter': copy.deepcopy(item),
                'budgetAdmission': copy.deepcopy(admission), 'postRuntimeBudgetAdmission': copy.deepcopy(admission),
                'capacityAdmission': {'availableBytes': 2 * 1024**3, 'deviceBytes': IMAGE_BYTES,
                    'requiredBytes': 512 * MIB, 'targetAllocatedBytes': 1024**2, 'fixtureLogicalBytes': 1,
                    'pressureReserveBytes': 0, 'admitted': True},
                'runtimeReadySpace': {'availableBytes': 2 * 1024**3, 'deviceBytes': IMAGE_BYTES},
                'recoveryMetadata': {'runtimeAttempted': True, 'runtimeReady': True, 'sampleStarted': True,
                                     'cleanupAdmissionBlocked': None},
                'cleanup': copy.deepcopy(CLEANUP), 'isolatedImageRetained': None,
                'wholeSampleSubprocessWallSeconds': (10 + round_) * factor, 'runtimeSetupSeconds': factor})
        path = results / f'stress-cargo-clean-sync-ttl-{mode}.json'
        dump(path, report)
        paths.append(path)
    return paths, archives


def change_report(paths, mode, mutate):
    report = json.loads(paths[mode].read_text())
    mutate(report)
    dump(paths[mode], report)
    if mode == 0 and paths[1].exists():
        other = json.loads(paths[1].read_text())
        if isinstance(other.get('previousGate'), dict):
            other['previousGate']['sha256'] = digest(paths[0].read_bytes())
        dump(paths[1], other)


def change_sample(paths, mode, index, mutate):
    def change(report):
        row = report['records'][index]
        raw = paths[mode].parent / Path(row['rawReportPath']).name
        sample = json.loads(raw.read_text())
        mutate(sample)
        row['rawReportSha256'] = dump(raw, sample)
        row['sample'] = copy.deepcopy(sample)
    change_report(paths, mode, change)


def replace_command(sample, archives, mode, product, round_, purpose, field, value):
    row = next(command for command in sample['commands'] if command['purpose'] == purpose)
    row[field] = value
    archive = next(item for item in sample['completeLogArchive'] if item['source'] == row[field + 'Path'])
    body = value.encode()
    (archives / f'inc{mode}' / f'{product}-{round_}.jsonl.logs' / Path(archive['archived']).name).write_bytes(body)
    archive.update(bytes=len(body), sha256=digest(body))


def change_bound_file(paths, name, identity_key, mutate):
    file = paths[0].parent / name
    value = json.loads(file.read_text())
    mutate(value)
    sha = dump(file, value)
    for mode in (0, 1):
        change_report(paths, mode, lambda report: report.update({identity_key: sha}))


def rebind_product_source_claim(paths, product_index, source_sha):
    """Forge internally consistent synthetic claims; fixed reviewed pins must win."""
    results = paths[0].parent
    products = json.loads((results / MANIFEST_FILE).read_text())
    products[product_index]['sha'] = source_sha
    manifest_sha = dump(results / MANIFEST_FILE, products)
    plan = json.loads((results / PLAN_FILE).read_text())
    plan['abcProducts'] = copy.deepcopy(products)
    plan_sha = dump(results / PLAN_FILE, plan)
    selected = products[product_index]
    for mode in (0, 1):
        def mutate(report):
            report.update(abcProducts=copy.deepcopy(products), abcManifestSha256=manifest_sha,
                          abcPlanSha256=plan_sha)
            for row in report['records']:
                if row['product'] != selected['label']:
                    continue
                row['verifiedProductInputs'] = copy.deepcopy(selected)
                row['verifiedProductInputsAfter'] = copy.deepcopy(selected)
                raw_path = results / Path(row['rawReportPath']).name
                sample = json.loads(raw_path.read_text())
                sample['production_sha'] = source_sha
                row['rawReportSha256'] = dump(raw_path, sample)
                row['sample'] = copy.deepcopy(sample)
        change_report(paths, mode, mutate)


class CleanSyncTTLSummaryTests(unittest.TestCase):
    def assert_blocked(self, result):
        self.assertFalse(result['complete'])
        self.assertIsNone(result['comparisons'])
        self.assertIsNone(result['slowerOrLargerPairs'])
        self.assertTrue(result['errors'])

    def test_exact_new_identity_is_distinct_from_directory_abc(self):
        self.assertEqual(PINS, {
            'sprig-baseline': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
            'sprig-clean-sync': '29e25e439cc674152c29712c9d5d315d87f4b14c',
            'sprig-read-ttl': '23ef28d2a38b58da8a78be1e8fcdd193990371d1'})
        self.assertEqual(SCHEMA, 'sprig-stress-cargo-clean-sync-ttl-v1')
        self.assertEqual(SUMMARY_SCHEMA, 'sprig-stress-cargo-clean-sync-ttl-summary-v1')
        self.assertEqual(PLAN_SCHEMA, 'sprig-cargo-clean-sync-ttl-plan-v1')
        self.assertEqual(EXPERIMENT['schema'], 'sprig-cargo-clean-sync-ttl-experiment-v1')
        self.assertEqual(MANIFEST_FILE, 'stress-cargo-clean-sync-ttl-products.json')
        self.assertEqual(PLAN_FILE, 'stress-cargo-clean-sync-ttl-plan.json')

    def test_old_directory_labels_or_source_pins_never_validate(self):
        products = [{'label': label, 'sha': sha, 'binary': f'/sources/{label}/target/release/sprig',
                     'sourcePath': f'/sources/{label}', 'binarySha256': str(index + 1) * 64}
                    for index, (label, sha) in enumerate(PINS.items())]
        for index in (1, 2):
            for old_label, old_sha in list(DIRECTORY_PINS.items())[1:]:
                for fields in ({'label': old_label}, {'sha': old_sha}, {'label': old_label, 'sha': old_sha}):
                    with self.subTest(index=index, fields=fields):
                        changed = copy.deepcopy(products)
                        changed[index].update(fields)
                        with self.assertRaises(ValueError):
                            validate_products(changed)

    def test_original_directory_matrix_is_not_accepted_as_new_experiment(self):
        from test_stress_cargo_directory_abc_summary import fixture as directory_fixture
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = directory_fixture(Path(temp))
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertEqual(len(result['records']), 36)

    def test_old_schema_experiment_plan_and_filenames_are_not_aliases(self):
        for kind in ('schema', 'experiment', 'plan', 'manifest-name', 'report-name'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                if kind == 'schema':
                    change_report(paths, 0, lambda r: r.update(schema='sprig-stress-cargo-directory-abc-v1'))
                elif kind == 'experiment':
                    change_report(paths, 0, lambda r: r['abcExperiment'].update(schema='sprig-cargo-directory-abc-experiment-v1'))
                elif kind == 'plan':
                    change_bound_file(paths, PLAN_FILE, 'abcPlanSha256',
                                      lambda p: p.update(schema='sprig-cargo-directory-abc-plan-v1'))
                elif kind == 'manifest-name':
                    (paths[0].parent / MANIFEST_FILE).rename(paths[0].parent / 'stress-cargo-directory-abc-products.json')
                else:
                    old_path = paths[0].with_name('stress-cargo-directory-abc-0.json')
                    paths[0].rename(old_path)
                    paths[0] = old_path
                self.assert_blocked(summarize(paths, archives))

    def test_consistently_rehashed_old_sources_still_fail_immutable_pins(self):
        for index in (1, 2):
            for old_sha in list(DIRECTORY_PINS.values())[1:]:
                with self.subTest(index=index, sha=old_sha), tempfile.TemporaryDirectory() as temp:
                    paths, archives = fixture(Path(temp))
                    rebind_product_source_claim(paths, index, old_sha)
                    result = summarize(paths, archives)
                    self.assert_blocked(result)
                    self.assertTrue(any('fixed source pin' in error for error in result['errors']))

    def test_mixed_raw_source_elf_and_before_after_proofs_fail(self):
        for kind in ('old-source', 'other-new-source', 'binary', 'before', 'after', 'old-archive-label'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                if kind in ('before', 'after'):
                    field = 'verifiedProductInputs' if kind == 'before' else 'verifiedProductInputsAfter'
                    change_report(paths, 0, lambda r: r['records'][1][field].update(sha=DIRECTORY_PINS['sprig-count']))
                elif kind == 'old-archive-label':
                    change_sample(paths, 0, 1, lambda s: s['completeLogArchive'][0].update(
                        archived=s['completeLogArchive'][0]['archived'].replace('sprig-clean-sync-0', 'sprig-count-0')))
                elif kind == 'binary':
                    change_sample(paths, 0, 1, lambda s: s.update(binarySha256='3' * 64))
                else:
                    wrong_sha = DIRECTORY_PINS['sprig-count'] if kind == 'old-source' else PINS['sprig-read-ttl']
                    change_sample(paths, 0, 1, lambda s: s.update(production_sha=wrong_sha))
                self.assert_blocked(summarize(paths, archives))

    def test_schedule_matches_reviewed_six_permutations_and_reverse_mode1(self):
        letters = {label: letter for label, letter in zip(PRODUCTS, 'ABC')}
        observed = lambda mode: [''.join(letters[label] for label in row['order']) for row in schedule(mode)[::3]]
        self.assertEqual(observed(0), ['ABC', 'CBA', 'BAC', 'CAB', 'ACB', 'BCA'])
        self.assertEqual(observed(1), ['BCA', 'ACB', 'CAB', 'BAC', 'CBA', 'ABC'])
        self.assertEqual(len(schedule()), 36)

    def test_all36_exact_three_edges_balanced_order_and_positions(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            result = summarize(paths, archives)
            self.assertTrue(result['complete'], result['errors'])
            self.assertEqual(len(result['records']), 36)
            self.assertEqual(result['missingRecords'], [])
            self.assertEqual(result['notRunRecords'], [])
            self.assertEqual(result['identity']['abcProducts'][2]['sha'], PINS['sprig-read-ttl'])
            for mode in ('inc0', 'inc1'):
                for edge, reference, candidate in EDGES:
                    comparison = result['comparisons'][mode][edge]
                    self.assertEqual(comparison['referenceProduct'], reference)
                    self.assertEqual(comparison['candidateProduct'], candidate)
                    metric = comparison['metrics']['wholeSamplerSeconds']
                    self.assertEqual(metric['reference']['n'], 6)
                    self.assertIsNone(metric['reference']['p95'])
                    self.assertIsNone(metric['candidate']['p99'])
                    self.assertEqual(len(metric['pairs']), 6)
                    self.assertEqual(len(metric['orderStrata'][reference]), 3)
                    self.assertEqual(len(metric['orderStrata'][candidate]), 3)
                    for label in (reference, candidate):
                        self.assertEqual([metric['positionStrata'][label][str(p)]['n'] for p in range(3)], [2, 2, 2])
                self.assertAlmostEqual(result['comparisons'][mode]['A-to-B']['metrics']['wholeSamplerSeconds']['geometricMeanPairedRatio'], 1.1)
                self.assertAlmostEqual(result['comparisons'][mode]['A-to-C']['metrics']['wholeSamplerSeconds']['geometricMeanPairedRatio'], 0.9)
                self.assertAlmostEqual(result['comparisons'][mode]['B-to-C']['metrics']['wholeSamplerSeconds']['geometricMeanPairedRatio'], 0.9 / 1.1)
                self.assertTrue(result['slowerOrLargerPairs'][mode]['A-to-B'])
            self.assertEqual([r['order'] for r in result['records'][::3]][:6],
                             [r['order'] for r in schedule(0)[::3]])

    def test_single_bad_sample_blocks_every_edge_and_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            change_sample(paths, 1, 17, lambda sample: sample.update(ok=False))
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertEqual(len(result['records']), 36)

    def test_every_failed_not_run_and_missing_slot_is_retained_without_ratios(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            def mutate(report):
                report.update(complete=False, status='failed', error={'message': 'retained outer failure'})
                report['records'][2].update(correct=False, status='failed', error={'message': 'unknown compiler exit'},
                                            originalError={'message': 'original'}, cleanupErrors=['retained mount'])
                for index in range(3, 18):
                    report['records'][index] = {**schedule(0)[index], 'correct': False, 'status': 'not-run'}
                report['records'].pop()
            change_report(paths, 0, mutate)
            paths[1].unlink()
            result = summarize(paths, archives)
            self.assert_blocked(result)
            self.assertEqual(len(result['records']), 17)
            self.assertEqual(len(result['notRunRecords']), 14)
            self.assertEqual(len(result['missingRecords']), 19)
            self.assertEqual(result['records'][2]['error']['message'], 'unknown compiler exit')
            self.assertEqual(result['records'][2]['originalError']['message'], 'original')
            self.assertEqual(result['records'][2]['cleanupErrors'], ['retained mount'])
            self.assertEqual(result['reports'][0]['error']['message'], 'retained outer failure')

    def test_absent_or_malformed_mode_still_accounts_for_all18_missing_positions(self):
        for kind in ('absent', 'malformed', 'duplicate-key'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                if kind == 'absent':
                    paths[1].unlink()
                else:
                    paths[1].write_text('{' if kind == 'malformed' else '{"x":1,"x":2}')
                result = summarize(paths, archives)
                self.assert_blocked(result)
                self.assertEqual(len(result['records']), 18)
                self.assertEqual(len(result['missingRecords']), 18)

    def test_input_count_wrong_name_extra_duplicate_or_reordered_records(self):
        mutations = [lambda r: r['records'].reverse(), lambda r: r['records'].append(copy.deepcopy(r['records'][0])),
                     lambda r: r['records'].__setitem__(1, copy.deepcopy(r['records'][0])),
                     lambda r: r['records'][0].update(round=False), lambda r: r['records'][0].update(position=False),
                     lambda r: r['records'][0].update(incremental=False), lambda r: r['records'][0]['order'].reverse()]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_report(paths, 0, mutate)
                self.assert_blocked(summarize(paths, archives))
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            self.assert_blocked(summarize(paths[:1], archives))
            self.assert_blocked(summarize(paths[::-1], archives))
            self.assert_blocked(summarize([], archives))

    def test_exact_fixed_identity_and_pressure_trace_mixing_rejected(self):
        mutations = [lambda r: r.update(schema='sprig-stress-cargo-own-ab-v2'), lambda r: r.update(rounds=4),
                     lambda r: r.update(expectedRecords=8), lambda r: r.update(imageBytes=8 * 1024**3),
                     lambda r: r.update(protocolSha256='0' * 64), lambda r: r['abcExperiment'].update(roundsPerMode=4),
                     lambda r: r['abcExperiment'].update(incrementalModes=[False, True]),
                     lambda r: r['abcProducts'][1].update(sha=PINS['sprig-read-ttl']),
                     lambda r: r['abcProducts'][1].update(binarySha256='1' * 64),
                     lambda r: r['abcProducts'][0].update(binary='/sources/../escape'),
                     lambda r: r['abcProducts'][0].update(ref='main'),
                     lambda r: r.update(experimentSpec={'profile': 'ordinary'}), lambda r: r.update(directManifest={}),
                     lambda r: r.update(trace=True), lambda r: r['abcExperiment'].update(pressure={}),
                     lambda r: r.update(image='sha256:' + 'b' * 64),
                     lambda r: r['sharedJobBudget'].update(deadlineEpochSeconds=2501)]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_report(paths, 0, mutate)
                self.assert_blocked(summarize(paths, archives))

    def test_manifest_plan_and_fixture_bind_actual_bytes_not_json_reserialization(self):
        for name in (MANIFEST_FILE, PLAN_FILE, 'stress-cargo-manifest.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                file = paths[0].parent / name
                file.write_bytes(file.read_bytes() + b' ')
                self.assert_blocked(summarize(paths, archives))

    def test_rehashed_plan_cannot_change_global_predeclared_schedule(self):
        mutations = [lambda p: p['records'].pop(), lambda p: p['records'].reverse(),
                     lambda p: p['records'][18]['order'].reverse(), lambda p: p['records'][0].update(position=False),
                     lambda p: p['records'][0].update(status='not-run'), lambda p: p.update(extra=True),
                     lambda p: p['abcExperiment'].update(profile='pressure'),
                     lambda p: p['abcProducts'][1].update(sha=PINS['sprig-read-ttl'])]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_bound_file(paths, PLAN_FILE, 'abcPlanSha256', mutate)
                self.assert_blocked(summarize(paths, archives))

    def test_prerequisite_exact_original_inc0_bytes_and_every_identity(self):
        for gate in (None, [], True, {'path': '/tmp/stress-cargo-clean-sync-ttl-0.json', 'sha256': '0' * 64},
                     {'path': '../stress-cargo-clean-sync-ttl-0.json', 'sha256': '0' * 64}):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_report(paths, 1, lambda report: report.update(previousGate=gate))
                self.assert_blocked(summarize(paths, archives))
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            paths[0].write_bytes(paths[0].read_bytes() + b' ')
            self.assertTrue(any('prerequisite hash' in e for e in summarize(paths, archives)['errors']))

    def test_before_after_product_proof_and_capacity_budget_cleanup_are_required(self):
        mutations = [lambda r: r.pop('verifiedProductInputs'), lambda r: r.pop('verifiedProductInputsAfter'),
                     lambda r: r['verifiedProductInputsAfter'].update(binarySha256='0' * 64),
                     lambda r: r['budgetAdmission'].update(admitted=False), lambda r: r['postRuntimeBudgetAdmission'].update(remainingSeconds=479),
                     lambda r: r['postRuntimeBudgetAdmission'].update(remainingSeconds=2200),
                     lambda r: r['budgetAdmission'].update(deadlineEpochSeconds=2600),
                     lambda r: r['capacityAdmission'].update(pressureReserveBytes=128 * MIB),
                     lambda r: r['capacityAdmission'].update(deviceBytes=8 * 1024**3),
                     lambda r: r['capacityAdmission'].update(requiredBytes=1),
                     lambda r: r['capacityAdmission'].update(targetAllocatedBytes=1),
                     lambda r: r['capacityAdmission'].update(fixtureLogicalBytes=0),
                     lambda r: r['runtimeReadySpace'].update(availableBytes=1), lambda r: r['cleanup'].pop(),
                     lambda r: r.update(isolatedImageRetained='/retained/new.img'),
                     lambda r: r['recoveryMetadata'].update(cleanupAdmissionBlocked='unknown state')]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_report(paths, 0, lambda report: mutate(report['records'][0]))
                self.assert_blocked(summarize(paths, archives))

    def test_raw_file_hash_archive_hash_missing_stderr_and_archive_symlink(self):
        for kind in ('raw', 'archive', 'missing', 'symlink', 'path'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                if kind == 'path':
                    change_report(paths, 0, lambda r: r['records'][0].update(rawReportPath='../outside.json'))
                elif kind == 'raw':
                    file = paths[0].parent / 'stress-cargo-sprig-baseline-inc0-0.json'
                    file.write_bytes(file.read_bytes() + b' ')
                else:
                    file = next(archives.glob('inc0/sprig-baseline-0.jsonl.logs/*source_unchanged.stderr'))
                    if kind == 'archive':
                        file.write_bytes(b'changed')
                    else:
                        body = file.read_bytes()
                        file.unlink()
                        if kind == 'symlink':
                            target = Path(temp) / 'external.stderr'
                            target.write_bytes(body)
                            file.symlink_to(target)
                self.assert_blocked(summarize(paths, archives))

    def test_shared_raw_cargo_program_toolchain_source_and_integer_ns_gates(self):
        replacements = [('noop_build', 'stderr', '   Fresh node000 v0.1.0 (/work/node000)\n'),
                        ('edit_execute', 'stdout', '269\n'),
                        ('toolchain_verify', 'stdout', 'rustc 1.99.1 (other)\ncargo 1.99.1 (other)\n'),
                        ('source_unchanged', 'stdout', json.dumps(checkpoint_tree()) + '\n')]
        for purpose, field, value in replacements:
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_sample(paths, 0, 0, lambda s: replace_command(s, archives, 0, PRODUCTS[0], 0, purpose, field, value))
                self.assert_blocked(summarize(paths, archives))
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            change_sample(paths, 0, 0, lambda s: s['checkpointTreeOracle']['entries'][0].update(mtime_ns=1700000000000000001))
            self.assert_blocked(summarize(paths, archives))

    def test_sprig_full_tree_cleanup_compiler_quiescence_and_ordinary_only(self):
        mutations = [lambda s: s.update(testOnly=True), lambda s: s['compilerSessions'][0].update(uncertain=True),
                     lambda s: s['compilerSessions'][0].update(naturalExitAndPidGoneVerified=False),
                     lambda s: s['lifecycle']['cleanup'].update(complete=False), lambda s: s.update(remainingMounts=['retained']),
                     lambda s: s['lifecycle']['activeAtSpace']['compilerContainer'].update(generation='wrong'),
                     lambda s: s['checkpoint'].update(revision='f' * 64),
                     lambda s: s['checkpointTreeOracle']['hardlink_groups'].pop(),
                     lambda s: s['artifactChecks'][0].update(exactMtime=False), lambda s: s.update(normalPressure={}),
                     lambda s: s.update(lifecycleTrace=True), lambda s: s['phase_seconds'].update(normal_pressure=0),
                     lambda s: s['phase_seconds'].update(clean_build=True), lambda s: s['convenience_seconds'].update(restoreToCompilerReady=-1)]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_sample(paths, 0, 0, mutate)
                self.assert_blocked(summarize(paths, archives))

    def test_js_rounded_embedded_tree_not_authoritative_but_safe_flags_are(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            change_report(paths, 0, lambda r: r['records'][0]['sample']['checkpointTreeOracle']['entries'][0].update(mtime_ns=1700000000000000001))
            change_report(paths, 0, lambda r: r['records'][0]['sample']['phase_seconds'].update(clean_build=1))
            self.assertTrue(summarize(paths, archives)['complete'])
            change_report(paths, 0, lambda r: r['records'][0]['sample'].update(ok=1))
            self.assert_blocked(summarize(paths, archives))

    def test_zero_denominators_and_outliers_retained_without_fake_ratios(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            for mode in (0, 1):
                change_report(paths, mode, lambda r: [row.update(runtimeSetupSeconds=0)
                    for row in r['records'] if row['product'] == PRODUCTS[0]])
            change_report(paths, 0, lambda r: r['records'][1].update(wholeSampleSubprocessWallSeconds=10000))
            result = summarize(paths, archives)
            self.assertTrue(result['complete'], result['errors'])
            metric = result['comparisons']['inc0']['A-to-B']['metrics']['runtimeSetupSeconds']
            self.assertEqual(len(metric['pairs']), 6)
            self.assertTrue(all(pair['candidateOverReference'] is None for pair in metric['pairs']))
            self.assertIsNone(metric['geometricMeanPairedRatio'])
            self.assertTrue(metric['undefinedRatioReason'])
            wall = result['comparisons']['inc0']['A-to-B']['metrics']['wholeSamplerSeconds']
            self.assertEqual(wall['candidate']['values'][0], 10000)
            self.assertTrue(any(pair['candidate'] == 10000 for pair in result['slowerOrLargerPairs']['inc0']['A-to-B']))

    def test_finite_but_overflowing_ratio_blocks_all_statistics(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            change_report(paths, 0, lambda r: r['records'][0].update(runtimeSetupSeconds=1e-300))
            change_report(paths, 0, lambda r: r['records'][1].update(runtimeSetupSeconds=1e300))
            self.assert_blocked(summarize(paths, archives))

    def test_duplicate_nonfinite_json_and_metric_set_changes_fail_closed(self):
        for body in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                strict_json(body)
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            change_sample(paths, 1, 17, lambda s: s['phase_seconds'].update(extra_unmatched=1))
            self.assert_blocked(summarize(paths, archives))


if __name__ == '__main__':
    unittest.main()
