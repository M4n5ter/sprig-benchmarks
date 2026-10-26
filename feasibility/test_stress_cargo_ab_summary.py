#!/usr/bin/env python3
"""Offline synthetic summary fixtures only: no Cargo, Docker, mounts or Rust."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from stress_cargo_ab_summary import EXPERIMENT, PACKAGES, PHASES, PINS, SCHEMA, strict_json, summarize


def dump(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(base):
    results = base/'results'; results.mkdir()
    archives = base/'records'; archives.mkdir()
    products = [{'label': name, 'sha': sha, 'binary': f'/fixed/{name}',
                 'sourcePath': f'/sources/{name}', 'binarySha256': str(i+1)*64}
                for i, (name, sha) in enumerate(PINS.items())]
    shared = {'image': 'sha256:'+'a'*64, 'protocolSha256': 'b'*64, 'fixtureManifestSha256': 'c'*64,
              'imageBytes': 4*1024**3, 'resourceProtocol': 'sprig-cargo-resource-4g-v1',
              'abManifestSha256': 'd'*64, 'abProducts': products, 'experimentSpec': copy.deepcopy(EXPERIMENT),
              'sharedJobBudget': {'startedEpochSeconds': 100, 'deadlineEpochSeconds': 2500,
                                  'minimumSampleSeconds': 180, 'cleanupReserveSeconds': 300}}
    paths = []
    for mode in (0, 1):
        report = {'schema': SCHEMA, 'complete': True, 'status': 'passed', 'incremental': mode,
                  'rounds': 4, 'expectedRecords': 8, **copy.deepcopy(shared), 'records': []}
        if mode:
            report['previousGate'] = {'path': str(paths[0]), 'sha256': hashlib.sha256(paths[0].read_bytes()).hexdigest()}
        for round_ in range(4):
            order = products[::-1] if (round_+mode)%2 else products
            for product in order:
                label = product['label']; factor = 1.1 if label == 'sprig-candidate' else 1
                oracle = {'schema': 'cargo-full-tree-v1', 'entries': [
                    {'path': '.', 'type': 'directory', 'mode': 493, 'mtime_ns': 1700000000123456789},
                    {'path': 'target/probe', 'type': 'file', 'mode': 416, 'mtime_ns': 1700000000123456789, 'size': 1, 'sha256': 'e'*64},
                    {'path': 'target/link', 'type': 'file', 'mode': 416, 'mtime_ns': 1700000000123456789, 'size': 1, 'sha256': 'e'*64}],
                    'hardlink_groups': [['target/link', 'target/probe']]}
                sample = {key: True for key in ('ok', 'fullRestoredTreeVerified', 'originalMainViewUnchanged', 'sourceUnchanged', 'allAcknowledgedIdsPresent')}
                sample.update(testOnly=False, incremental=mode, production_sha=product['sha'], binarySha256=product['binarySha256'],
                              image=shared['image'], protocolSha256=shared['protocolSha256'], backend='writable', compressionPolicy='auto (default init)',
                              remainingMounts=[], remainingContainers=[], full_task_seconds=9*factor,
                              phase_seconds={p: factor for p in PHASES},
                              convenience_seconds={'checkpointCompilerQuiescePlusProduct': 2*factor, 'restoreToCompilerReady': factor},
                              activeSpace={'filesystemUsedBytes': int(1000000*factor)}, checkpointTreeOracle=oracle,
                              compilerSessions=[{'removed': True, 'uncertain': False, 'naturalExitAndPidGoneVerified': True} for _ in range(4)],
                              lifecycle={'cleanup': {'complete': True}, 'activeAtSpace': {'retainedGenerationCount': 4,
                                         'foregroundFuseProcesses': [{}, {}, {}], 'views': [{'name': 'main'}, {'name': 'work'}, {'name': 'second', 'generation': 'g2', 'path': '/second'}],
                                         'compilerContainer': {'count': 1, 'image': shared['image'], 'inspection': {'state': {'Running': True}}, 'generation': 'g2', 'tree': '/second'}}},
                              cargoBuildObservations=[], artifactChecks=[], commands=[], completeLogArchive=[])
                sample['phase_seconds']['checkpoint'] = 2*factor
                for phase in ('clean_build', 'noop_build', 'edit_build', 'restored_rebuild'):
                    fresh = phase in ('noop_build', 'restored_rebuild')
                    sample['cargoBuildObservations'].append({'phase': phase, 'returncode': 0,
                        'freshPackages': PACKAGES if fresh else [], 'compilingPackages': [] if fresh else PACKAGES})
                for phase in ('clean_artifacts', 'noop_artifacts', 'edit_artifacts', 'restored_artifacts', 'restored_rebuild_artifacts'):
                    sample['artifactChecks'].append({'phase': phase, 'ok': True, 'hardlinkProbe': True,
                        'exactMtime': True, 'generatedFiles': ['generated.rs'], 'buildValue': 1 if phase in ('clean_artifacts', 'noop_artifacts') else 2})
                log_dir = archives/f'inc{mode}'/f'{label}-{round_}.jsonl.logs'; log_dir.mkdir(parents=True)
                for index, purpose in enumerate(('pre_checkpoint_oracle', 'restore_verify')):
                    source = f'/original/mount/{mode}/{label}/{round_}/{purpose}.stdout'
                    stdout = json.dumps(oracle)+'\n'; body = stdout.encode()
                    name = f'{index:06}-{purpose}.stdout'; (log_dir/name).write_bytes(body)
                    sample['completeLogArchive'].append({'source': source, 'archived': f'/original/stress-cargo-records/inc{mode}/{label}-{round_}.jsonl.logs/{name}',
                                                        'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
                    sample['commands'].append({'purpose': purpose, 'returncode': 0, 'stdoutPath': source, 'stdout': stdout})
                name = f'stress-cargo-{label}-inc{mode}-{round_}.json'
                sha = dump(results/name, sample)
                report['records'].append({'product': label, 'round': round_, 'incremental': mode, 'correct': True,
                    'status': 'passed', 'sampleReturncode': 0, 'sample': copy.deepcopy(sample),
                    'rawReportPath': 'results/'+name, 'rawReportSha256': sha,
                    'wholeSampleSubprocessWallSeconds': (10+round_)*factor, 'runtimeSetupSeconds': factor})
        path = results/f'stress-cargo-own-ab-{mode}.json'; dump(path, report); paths.append(path)
    return paths, archives


def change_report(paths, mode, change):
    report = json.loads(paths[mode].read_text()); change(report); dump(paths[mode], report)
    if mode == 0:
        other = json.loads(paths[1].read_text()); other['previousGate']['sha256'] = hashlib.sha256(paths[0].read_bytes()).hexdigest(); dump(paths[1], other)


def change_sample(paths, mode, index, change):
    report = json.loads(paths[mode].read_text()); row = report['records'][index]
    raw = paths[mode].parent/Path(row['rawReportPath']).name
    sample = json.loads(raw.read_text()); change(sample)
    row['rawReportSha256'] = dump(raw, sample); row['sample'] = copy.deepcopy(sample)
    dump(paths[mode], report)
    if mode == 0:
        other = json.loads(paths[1].read_text()); other['previousGate']['sha256'] = hashlib.sha256(paths[0].read_bytes()).hexdigest(); dump(paths[1], other)


def enable_pressure(paths,archives):
    from stress_cargo_pressure import SPEC, SCHEMA as PRESSURE_SCHEMA, pressure_identity
    from stress_cargo_ab_summary import digest
    for mode,path in enumerate(paths):
        report=json.loads(path.read_text())
        report['experimentSpec']={**copy.deepcopy(EXPERIMENT),'profile':SPEC['profile'],'pressure':pressure_identity()}
        for row in report['records']:
            label=row['product'];round_=row['round'];raw_path=path.parent/Path(row['rawReportPath']).name
            sample=json.loads(raw_path.read_text())
            pressure=dict(schema=PRESSURE_SCHEMA,profile=SPEC['profile'],spec=SPEC,ok=True,allWitnessesVerified=True,workerLifetimeOverlapNs=90,
                          workers=[dict(worker=w,startedNs=w*10,finishedNs=100+w*10,completedIterations=128,
                                        samplesNanoseconds={name:[w+1]*(256 if name=='rename' else 128) for name in ('rename','write','read','metadata')}) for w in (0,1)])
            output=json.dumps(pressure,sort_keys=True)+'\n'
            sample.update(normalPressure=pressure,normalPressureScriptSha256=pressure_identity()['scriptSha256'],normalPressureRawSha256=digest(output.encode()))
            sample['phase_seconds']['normal_pressure']=1.0
            oracle=sample['checkpointTreeOracle']
            def entry(name,**extra):
                return dict(path=name,type='file',mode=420,mtime_ns=int(SPEC['witnessMtimeNs']),size=64,sha256='e'*64,**extra)
            oracle['entries'].append(entry('pressure-rename2/observations.json'))
            oracle['entries'][-1]['sha256']=digest(output.encode())
            for worker in (0,1):
                base=f'pressure-rename2/worker-{worker}'
                oracle['entries'] += [entry(base+f'/unrelated/{i:04d}') for i in range(1024)]
                for name in ('witness','witness-link'):
                    value=entry(base+'/active/'+name);value['mode']=0o640;oracle['entries'].append(value)
                value=entry(base+'/active/symlink');value.update(type='symlink',target='witness');oracle['entries'].append(value)
                oracle['hardlink_groups'].append([base+'/active/witness',base+'/active/witness-link'])
            log_dir=archives/f'inc{mode}'/f'{label}-{round_}.jsonl.logs'
            for command in sample['commands']:
                command['stdout']=json.dumps(oracle)+'\n'
                item=next(item for item in sample['completeLogArchive'] if item['source']==command['stdoutPath'])
                body=command['stdout'].encode();(log_dir/Path(item['archived']).name).write_bytes(body)
                item.update(bytes=len(body),sha256=digest(body))
            source=f'/original/{mode}/{label}/{round_}/pressure.stdout';name='000002-normal_pressure.stdout'
            (log_dir/name).write_text(output)
            sample['completeLogArchive'].append(dict(source=source,archived=f'/original/stress-cargo-records/inc{mode}/{label}-{round_}.jsonl.logs/{name}',bytes=len(output.encode()),sha256=digest(output.encode())))
            sample['commands'].append(dict(purpose='normal_pressure',returncode=0,stdout=output,stdoutPath=source,stdinSha256=pressure_identity()['scriptSha256']))
            row['sample']=sample;row['rawReportSha256']=dump(raw_path,sample)
        dump(path,report)
    report=json.loads(paths[1].read_text());report['previousGate']['sha256']=digest(paths[0].read_bytes());dump(paths[1],report)


class SummaryTests(unittest.TestCase):
    def test_all16_strict_paired_statistics_and_regressions(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp)); result = summarize(paths, archives)
            self.assertTrue(result['complete'], result['errors']); self.assertEqual(len(result['records']), 16)
            self.assertTrue(all(r['archivedFilesVerified'] == 2 for r in result['records']))
            metric = result['comparisons']['inc0']['wholeSamplerSeconds']
            self.assertEqual(metric['baseline']['values'], [10, 11, 12, 13])
            self.assertEqual(metric['baseline']['n'], 4)
            self.assertIsNone(metric['baseline']['p95']); self.assertIsNone(metric['candidate']['p99'])
            self.assertAlmostEqual(metric['geometricMeanPairedRatio'], 1.1)
            self.assertAlmostEqual(metric['medianPairedRatio'], 1.1)
            self.assertTrue(all(p['percentChange'] > 9.99 for p in metric['pairs']))
            self.assertEqual([p['round'] for p in metric['orderStrata']['sprig-baseline']], [0, 2])
            self.assertEqual([p['round'] for p in result['comparisons']['inc1']['wholeSamplerSeconds']['orderStrata']['sprig-baseline']], [1, 3])

    def test_failures_and_missing_rows_retained_without_any_ratios(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            def change(report):
                report['complete'] = False; report['status'] = 'failed'; report['error'] = {'message': 'retained failure'}
                report['records'][2].update(correct=False, status='failed', error={'message': 'one bad sample'})
                report['records'].pop()
            change_report(paths, 0, change); result = summarize(paths, archives)
            self.assertFalse(result['complete']); self.assertIsNone(result['comparisons'])
            self.assertEqual(len(result['records']), 15)
            self.assertEqual(result['records'][2]['error']['message'], 'one bad sample')
            self.assertEqual(result['reports'][0]['error']['message'], 'retained failure')
            self.assertTrue(any('expected eight' in error for error in result['errors']))

    def test_bad_identity_order_round_and_gate_never_pooled(self):
        mutations = [lambda r: r.update(schema='sprig-stress-cargo-own-ab-v1'),
                     lambda r: r.update(rounds=1), lambda r: r['experimentSpec'].update(profile='concurrent'),
                     lambda r: r.update(image='sha256:'+'f'*64), lambda r: r['abProducts'][0].update(sha='0'*40),
                     lambda r: r['sharedJobBudget'].update(deadlineEpochSeconds=2800),
                     lambda r: r['records'].reverse(), lambda r: r['records'][0].update(round=False),
                     lambda r: r['records'][0].update(product='sprig-candidate'),
                     lambda r: r['records'][0].update(rawReportPath='../outside.json')]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp)); change_report(paths, 0, mutate)
                result = summarize(paths, archives); self.assertFalse(result['complete']); self.assertIsNone(result['comparisons'])
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp)); change_report(paths, 1, lambda r: r['previousGate'].update(sha256='0'*64))
            self.assertTrue(any('prerequisite hash' in e for e in summarize(paths, archives)['errors']))

    def test_malformed_previous_gate_still_emits_incomplete_summary(self):
        for gate in (None, [], 'bad', 1, True):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp))
                change_report(paths, 1, lambda report: report.update(previousGate=gate))
                result = summarize(paths, archives)
                self.assertFalse(result['complete']); self.assertIsNone(result['comparisons'])
                self.assertEqual(len(result['records']), 16)
                self.assertTrue(any('prerequisite hash' in e for e in result['errors']))

    def test_raw_hash_and_archive_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp)); raw = paths[0].parent/'stress-cargo-sprig-baseline-inc0-0.json'
            raw.write_bytes(raw.read_bytes()+b' ')
            result = summarize(paths, archives); self.assertFalse(result['complete'])
            self.assertTrue(any('raw report hash' in e for e in result['errors']))
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp)); file = next(archives.glob('inc0/sprig-baseline-0.jsonl.logs/*.stdout')); file.write_bytes(b'changed')
            result = summarize(paths, archives); self.assertFalse(result['complete'])
            self.assertTrue(any('archive bytes/hash' in e for e in result['errors']))

    def test_one_ns_fulltree_mismatch_survives_json_integer_precision(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp))
            change_sample(paths, 0, 0, lambda sample: sample['checkpointTreeOracle']['entries'][1].update(mtime_ns=1700000000123456790))
            result = summarize(paths, archives); self.assertFalse(result['complete'])
            self.assertTrue(any('exact-ns full restored tree mismatch' in e for e in result['errors']))

    def test_cleanup_cargo_and_witness_gates(self):
        mutations = [lambda s: s.update(testOnly=True), lambda s: s['lifecycle']['cleanup'].update(complete=False),
                     lambda s: s.update(remainingContainers=['retained']), lambda s: s['compilerSessions'][0].update(uncertain=True),
                     lambda s: s['cargoBuildObservations'][1].update(freshPackages=PACKAGES[:-1]),
                     lambda s: s['artifactChecks'][0].update(exactMtime=False),
                     lambda s: s['phase_seconds'].update(clean_build=-1),
                     lambda s: s['phase_seconds'].update(clean_build=True),
                     lambda s: s['convenience_seconds'].update(restoreToCompilerReady=None)]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temp:
                paths, archives = fixture(Path(temp)); change_sample(paths, 0, 0, mutate)
                result = summarize(paths, archives); self.assertFalse(result['complete']); self.assertIsNone(result['comparisons'])

    def test_missing_or_malformed_input_keeps_available_records(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp)); paths[1].unlink()
            result = summarize(paths, archives); self.assertFalse(result['complete']); self.assertEqual(len(result['records']), 8)
        with tempfile.TemporaryDirectory() as temp:
            paths, archives = fixture(Path(temp)); paths[1].write_text('{')
            result = summarize(paths, archives); self.assertFalse(result['complete']); self.assertEqual(len(result['records']), 8)

    def test_separate_pressure_profile_has_dependent_operation_tails_not_whole_task_tails(self):
        with tempfile.TemporaryDirectory() as temp:
            paths,archives=fixture(Path(temp));enable_pressure(paths,archives)
            result=summarize(paths,archives)
            self.assertTrue(result['complete'],result['errors'])
            self.assertEqual(result['experimentSpec']['profile'],'normal-rename2-v1')
            operations=result['records'][0]['normalPressureOperations']
            self.assertEqual(operations['rename']['n'],512)
            self.assertEqual(operations['read']['n'],256)
            self.assertIsNotNone(operations['rename']['p99'])
            self.assertIsNone(result['comparisons']['inc0']['wholeSamplerSeconds']['baseline']['p99'])
            self.assertIn('pressure.rename.p99Seconds',result['comparisons']['inc0'])
            # Immutable helper/profile changes cannot be pooled into this run.
            change_report(paths,1,lambda r:r.update(experimentSpec=copy.deepcopy(EXPERIMENT)))
            blocked=summarize(paths,archives);self.assertFalse(blocked['complete']);self.assertIsNone(blocked['comparisons'])

    def test_pressure_observation_witness_and_helper_identity_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            paths,archives=fixture(Path(temp));enable_pressure(paths,archives)
            change_sample(paths,0,0,lambda s:s.update(normalPressureRawSha256='0'*64))
            result=summarize(paths,archives);self.assertFalse(result['complete'])
            self.assertTrue(any('raw pressure timing evidence' in error for error in result['errors']))

    def test_json_nonfinite_and_duplicate_keys_rejected(self):
        for body in ('{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'):
            with self.subTest(body=body), self.assertRaises(ValueError): strict_json(body)
        self.assertEqual(strict_json('{"mtime_ns":1700000000123456789}')['mtime_ns'], 1700000000123456789)


if __name__ == '__main__':
    unittest.main()
