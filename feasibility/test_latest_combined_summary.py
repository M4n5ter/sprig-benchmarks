#!/usr/bin/env python3
"""Inert offline evidence tests: tmp JSON/log bytes only, never product/workload I/O."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import latest_combined_summary as audit


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def usage(used):
    return {'filesystemUsedBytes': used, 'deviceBytes': audit.IMAGE_BYTES,
            'usageRaw': f'Device size: {audit.IMAGE_BYTES}\nUsed: {used}\n',
            'groupsRaw': 'Data,single: Size:1048576, Used:4096\nMetadata,DUP: Size:1048576, Used:4096\nSystem,DUP: Size:65536, Used:4096\n'}


def success(oracle):
    return ''.join(row['path'] + ': OK\n' for row in oracle)


class EvidenceFixture:
    """Model actual adapter contracts; original runner paths intentionally do not exist."""
    def __init__(self, directory):
        self.root = Path(directory)
        self.results = self.root / 'results'; self.results.mkdir()
        self.archive = self.root / 'records'; self.archive.mkdir()
        self.input = self.results / 'latest-combined-comparison.json'
        self.image = 'sha256:' + '9' * 64
        self.identity = {'schema': audit.IDENTITY_SCHEMA,
            'sprig': {'sha': audit.PINS['sprig-native'], 'ref': 'main', 'sourcePath': '/inert/checkouts/sprig',
                      'binary': '/inert/checkouts/sprig/target/release/sprig', 'binarySha256': '1' * 64},
            'layerfs': {'sha': audit.PINS['layerfs'], 'ref': 'main', 'sourcePath': '/inert/checkouts/layerfs',
                        'binary': '/inert/checkouts/layerfs/core/target/release/layerfs-daemon', 'binarySha256': '2' * 64,
                        'sdkPath': '/inert/checkouts/layerfs/api/agent/sdk/src/index.js', 'sdkSha256': '3' * 64,
                        'nativeAddonPath': '/inert/checkouts/layerfs/api/binding/layerfs.node', 'nativeAddonSha256': '4' * 64}}
        self.manifest = {'schema': audit.FIXTURE_SCHEMA, 'cases': []}
        for case in audit.CASES:
            oracle, steps = audit.frozen_fixture(case)
            name = 'latest-combined-' + case
            oracle_bytes = encoded(oracle)
            (self.results / (name + '-oracle.json')).write_bytes(oracle_bytes)
            entry = {'case': case, 'sourcePath': '/inert/fixtures/' + case,
                     'oraclePath': '/inert/results/' + name + '-oracle.json', 'oracleSha256': audit.digest(oracle_bytes)}
            if steps:
                step_bytes = encoded(steps)
                (self.results / (name + '-steps.json')).write_bytes(step_bytes)
                final = {r['path']: dict(r) for r in oracle}
                for step in steps:
                    final[step['path']]['sha256'] = step['sha256']
                final_bytes = encoded(list(final.values()))
                (self.results / (name + '-final.json')).write_bytes(final_bytes)
                entry.update(stepsPath='/inert/results/' + name + '-steps.json', stepsSha256=audit.digest(step_bytes),
                             finalPath='/inert/results/' + name + '-final.json', finalSha256=audit.digest(final_bytes))
            self.manifest['cases'].append(entry)
        identity_bytes, manifest_bytes = encoded(self.identity), encoded(self.manifest)
        (self.results / 'latest-combined-identity.json').write_bytes(identity_bytes)
        (self.results / 'latest-combined-fixtures.json').write_bytes(manifest_bytes)
        self.driver = {'schema': audit.SCHEMA, 'complete': True, 'status': 'passed', 'backend': 'native', 'mode': 'smoke',
                       'rounds': 1, 'expectedRecords': 4, 'image': self.image, 'imageBytes': audit.IMAGE_BYTES,
                       'productionSha': audit.PINS['sprig-native'], 'comparatorSha': audit.PINS['layerfs'],
                       'identity': self.identity, 'identitySha256': audit.digest(identity_bytes),
                       'fixtureManifest': self.manifest, 'fixtureManifestSha256': audit.digest(manifest_bytes),
                       'sharedJobBudget': {'startedEpochSeconds': 1000, 'deadlineEpochSeconds': 3400,
                                           'minimumSampleSeconds': 180, 'cleanupReserveSeconds': 300},
                       'limits': {'artifactBytes': audit.ARTIFACT_BYTES, 'pendingReportReserveBytes': audit.REPORT_RESERVE,
                                  'collectionManifestReserveBytes': audit.MANIFEST_RESERVE}, 'records': []}
        self.samples = {}
        for position, (record_id, product, case) in enumerate(audit.ORDER):
            record, sample, files = self.build(record_id, product, case, position)
            self.driver['records'].append(record); self.samples[record_id] = sample
            target = self.archive / (record_id + '.jsonl.logs'); target.mkdir()
            for name, body in files.items():
                (target / name).write_bytes(body)
        self.original_driver = copy.deepcopy(self.driver)
        self.original_samples = copy.deepcopy(self.samples)
        self.save()

    def save(self):
        for record in self.driver['records']:
            sample = self.samples.get(record['id'])
            if sample is not None:
                body = encoded(sample)
                (self.results / ('latest-combined-' + record['id'] + '.json')).write_bytes(body)
                record['rawReportSha256'] = audit.digest(body)
        self.input.write_bytes(encoded(self.driver))

    def reset(self):
        self.driver = copy.deepcopy(self.original_driver)
        self.samples = copy.deepcopy(self.original_samples)
        self.save()

    def build(self, record_id, product, case, position):
        native, count = product == 'sprig-native', 100 if case == 'history-distributed' else 0
        oracle, steps = audit.frozen_fixture(case)
        manifest = next(e for e in self.manifest['cases'] if e['case'] == case)
        outer = '/inert/runner/latest-combined-' + record_id + '-ABC123'
        mount = outer + '/mount'; root = mount + '/store'
        ledger = '/inert/runner/latest-combined-records/' + record_id + '.jsonl'
        allowance = audit.ARTIFACT_BYTES - 1000 - audit.REPORT_RESERVE - audit.MANIFEST_RESERVE
        admission = {'startedEpochSeconds': 1000, 'deadlineEpochSeconds': 3400, 'remainingSeconds': 2300,
                     'workReserveSeconds': 180, 'cleanupReserveSeconds': 300, 'requiredSeconds': 480, 'admitted': True}
        record = {'id': record_id, 'product': product, 'case': case, 'position': position, 'status': 'passed', 'correct': True,
                  'rawReportPath': 'results/latest-combined-' + record_id + '.json',
                  'budgetAdmission': admission, 'postRuntimeBudgetAdmission': {**admission, 'remainingSeconds': 2290},
                  'preSampleArtifactInventory': {'bytes': 1000}, 'archiveAllowanceBytes': allowance,
                  'finalArtifactInventory': {'bytes': 10 * 1024**2},
                  'hostAdmission': {'requiredBytes': audit.IMAGE_BYTES + audit.ARTIFACT_BYTES + 512 * 1024**2, 'availableBytes': 8 * 1024**3},
                  'filesystem': {'directory': outer, 'mount': mount, 'image': outer + '/new.img',
                                 'runtimeState': outer + '/runtime-state.json', 'empty': usage(65536)},
                  'verifiedProductInputs': self.identity['sprig' if native else 'layerfs'],
                  'cleanup': {'blocked': None, 'originalImageRetained': True, 'normalOnly': True, 'complete': True, 'unmounted': True},
                  # Embedded JS sample is not authoritative; rounded or absent fields must not replace raw JSON.
                  'sample': {'untrustedEmbeddedSample': True, 'unsafeInteger': 9007199254740992}}
        sample = {'schema': 'sprig-latest-combined-native-sample-v1' if native else 'sprig-latest-combined-layerfs-sample-v1',
                  'ok': True, 'testOnly': False, 'product': product, 'backend': 'native' if native else 'fuse', 'case': case,
                  'production_sha': audit.PINS[product], 'prototype_only': False, 'workload_only_verification': True,
                  'complete_metadata_verification': False, 'initializationIncludedInImport': False,
                  'root': root, 'source': manifest['sourcePath'], 'recordsFile': ledger, 'recordsIncludedInActiveSpace': False,
                  'oracleFiles' if native else 'files': len(oracle), 'logicalBytes': sum(r['bytes'] for r in oracle),
                  'fullHistoricalSnapshotReadbacks': count, 'sourceUnchanged': True, 'originalMainViewUnchanged': True,
                  'originalSecondViewUnchanged': True, 'allAcknowledgedIdsPresent': True,
                  'remainingMountsKnown': True, 'remainingMounts': [], 'activeSpace': usage(1048576), 'postHistorySpace': usage(2097152),
                  'commands': [], 'lifecycle': {'normalUnmountOnly': True, 'cleanup': {'complete': True}}}
        outputs, sdk = {}, []

        def command(output='', **fields):
            number = len(sample['commands']) + 1
            row = {'sequence': number, 'returncode': 0, **fields}
            if native:
                row.update(outcomeKnown=True, withinAcceptanceLimits=True)
            else:
                row['signal'] = None
            for stream, text in (('stdout', output), ('stderr', '')):
                name = (f'command-{number:06}-{stream}.log' if native else f'{number:05}-' + row['purpose'] + '.' + stream)
                source = root + '/logs/' + name
                body = text.encode()
                outputs[source] = body
                row.update({stream + 'Path': source, stream + 'Bytes': len(body), stream + 'Sha256': audit.digest(body)})
            sample['commands'].append(row)
            return row

        def cli(action, *args, result=None):
            return command(json.dumps({'schema_version': 1, 'result': result}) + '\n',
                           argv=[self.identity['sprig']['binary'], '--store', root + '/library', '--json', action, *args], cwd=None)

        def shell(text, path, output='', purpose=None):
            if native or purpose == 'source_unchanged':
                return command(output, argv=['bash', '-c', text], cwd=path, **({} if native else {'purpose': purpose}))
            return command(output, purpose=purpose, command=text, workspace={'path': path, 'sandbox': 'sandbox-one'})

        def read(oracle, path, purpose=None):
            return shell(audit.checksum(oracle), path, success(oracle), purpose)

        def space(key, purpose):
            for action, field in (('usage', 'usageRaw'), ('df', 'groupsRaw')):
                command(sample[key][field], argv=['btrfs', 'filesystem', action, '-b', root if native else mount],
                        **({} if native else {'purpose': purpose + '_' + ('usage' if action == 'usage' else 'groups')}))

        initial = '0' * 64 if native else '32' + '0' * 64
        ids = [f'{i + 1:064x}' if native else '12' + f'{i + 1:064x}' for i in range(count)]
        sample['initialHead'] = initial
        names = ['main' if native else 'import-main', 'work', 'second']
        views = []
        for i, name in enumerate(names):
            if native:
                views.append({'name': name, 'path': root + '/library/native/g-' + name + '/tree', 'generation': 'g-' + name,
                              'backend': {'kind': 'native'}, 'base_revision': ids[-1] if name == 'work' and count else initial})
            else:
                views.append({'name': name, 'path': '/workspaces/' + str(i + 1), 'sandbox': 'sandbox-one'})
        by_name = {v['name']: v for v in views}
        common_boundary = {'views': views, 'fileTreesRetained': True, 'allRuntimeLogsAndJournalsInsideMeasuredStore': True,
                           'controlProcessesRunning': 0 if native else 1}
        if native:
            common_boundary.update(foregroundFuseProcesses=[], retainedGenerations={'projection': [], 'writable': []})
        else:
            common_boundary.update(workspaces=[{'path': v['path'], 'activity': 'Idle'} for v in views],
                                   sandboxes=[{'sandbox': 'sandbox-one', 'workspaces': 3}])
        active = {**common_boundary, 'historicalReadbacksStarted': False, 'historicalReadbacksCompleted': 0}
        post = {**common_boundary, 'historicalReadbacksStarted': bool(count), 'historicalReadbacksCompleted': count,
                'historicalReadbacksComplete': True}
        sample['lifecycle']['activeAtSpace'] = active
        if native:
            generations = sorted([v['generation'] for v in views] + [f'g-history-{i + 1:03}' for i in range(count)])
            post.update(generationDirectories=generations, retainedGenerationCount=len(generations))
            sample['lifecycle']['activeAfterHistory'] = post
            sample['lifecycle']['cleanup'].update(blocked=False, harnessProcessesKilled=False, processesKilled=0, forceOrLazyUnmountUsed=False)
            sample.update(status='passed', uncertain=False, remainingServersKnown=True, remainingServers=[],
                          binary=self.identity['sprig']['binary'], binarySha256=self.identity['sprig']['binarySha256'],
                          binaryHashVerified=True, binaryBytes=123456, binarySourcePinVerifiedBySampler=False,
                          temporaryDirectory={'path': root + '/tmp', 'environment': 'TMPDIR', 'insideMeasuredRoot': True, 'setBeforeProductCLI': True},
                          historyExpectedSteps=count, metadata_branch_seconds=None, metadata_branch_available=True,
                          metadata_branch_probe='omitted', metadata_branch_unavailable_reason=None,
                          init_seconds=.001, import_seconds=.002, first_fork_seconds=.003, first_read_seconds=.004,
                          total_import_fork_read_seconds=.009, warm_fork_seconds=.005, warm_read_seconds=.006, warm_total_seconds=.011,
                          write_seconds=count * .001, checkpoint_seconds=count * .002, restore_seconds=count * .003,
                          restore_read_seconds=count * .004, restore_cleanup_seconds=0.0,
                          checkpoint_steps=[], historical_restore_steps=[], history_distinct_revisions=count,
                          wholeTaskSeconds=10.0, wholeSampleIncludingSetupCleanupSeconds=12.0, sourceFilesRetained=True)
            record['sampleReturncode'] = 0
            cli('init', result={'created': True})
            cli('import', sample['source'], 'main', result={'base_revision': initial, 'path': by_name['main']['path']})
            cli('fork', 'main', 'work', result={'base_revision': initial, 'path': by_name['work']['path']})
        else:
            sample['postHistoryBoundary'] = post
            sample['lifecycle'].update(uncertain=False, committedHistoryRetained=True, volumeRetained=True)
            sample.update(image=self.image, sdkPath=self.identity['layerfs']['sdkPath'], daemonPath=self.identity['layerfs']['binary'],
                          oracleSha256=manifest['oracleSha256'], stepsSha256=manifest.get('stepsSha256'),
                          remainingContainersKnown=True, remainingContainers=[], initMs=2.0, importMs=4.0, forkToWorkspaceMs=6.0,
                          firstFullReadVerifyMs=8.0, totalImportForkReadMs=18.0, warmForkToWorkspaceMs=10.0, warmFirstFullReadMs=12.0,
                          warmForkReadMs=22.0, initInclusiveImportForkReadMs=20.0,
                          historicalRestoreMs=count * 6.0, historicalRestoreReadMs=count * 8.0, historicalRestoreCleanupMs=count * 1.0,
                          historicalRestoreSamples=[], sdkOperations=sdk, fullTaskSeconds=14.0)
            record['runtime'] = {'image': self.image, 'dockerRoot': mount + '/runtime/docker', 'containerdRoot': mount + '/runtime/containerd'}
            record['runtimeReadySpace'] = usage(131072); record['runtimeLeave'] = {'restored': True}
            sdk.extend([{'operation': 'LayerFS.init', 'result': {'created': {'layer': initial}}},
                        {'operation': 'sandbox.create', 'result': {'sandbox': 'sandbox-one'}}])
        read(oracle, by_name['work']['path'], 'first_full_read')
        if native:
            cli('fork', 'main', 'second', result={'base_revision': initial, 'path': by_name['second']['path']})
        read(oracle, by_name['second']['path'], 'warm_full_read')
        if count:
            if native:
                cli('log', 'work', result=[{'revision': initial, 'parents': []}])
            else:
                sdk.append({'operation': 'branch.list_commits', 'result': {'items': [], 'hasMore': False}})
                sample['historyCheck'] = {'samples': [], 'expectedSamples': 100, 'baselineHistoryRecords': 0, 'completed': True,
                    'totalWriteMs': 200.0, 'totalCommitMs': 400.0, 'acknowledgedCommits': 100, 'historyRecords': 100,
                    'allAcknowledgedIdsPresent': True, 'finalFullByteVerification': True, 'changedFileReadbackAfterEveryCommit': True}
        previous, current = initial, {r['path']: dict(r) for r in oracle}
        for step, revision in zip(steps, ids):
            n = step['step']
            shell(audit.writer(step), by_name['work']['path'], purpose='history_write_' + str(n))
            if native:
                checkpoint = {'committed': True, 'branch': 'work', 'previous_head': previous, 'revision': revision}
                cli('checkpoint', 'work', '--expected-head', previous, '--message', 'Frozen history step ' + str(n), result=checkpoint)
                sample['checkpoint_steps'].append({'step': n, 'revision': revision, 'base': previous,
                    'checkpoint': checkpoint, 'changedFileReadback': True, 'write_seconds': .001, 'checkpoint_seconds': .002,
                    'checkpoint_cli_seconds': .002, 'checkpoint_ready_seconds': 0.0, 'generation_before': 'g-work',
                    'generation_after': 'g-work', 'workspace_path_after': by_name['work']['path']})
            else:
                checkpoint = {'kind': 'Committed', 'commit': {'id': revision}, 'head': revision}
                sdk.append({'operation': 'workspace.commit', 'result': checkpoint})
                sample['historyCheck']['samples'].append({'step': n, 'commitId': revision, 'commit': checkpoint, 'writeMs': 2.0, 'commitMs': 4.0})
            shell(audit.changed(step), by_name['work']['path'], success([step]), 'history_changed_read_' + str(n))
            current[step['path']]['sha256'] = step['sha256']; previous = revision
        if count:
            read(list(current.values()), by_name['work']['path'], 'history_final_full_read')
        if native:
            chain = list(reversed(ids)) + [initial]
            cli('log', 'work', result=[{'revision': revision, 'parents': chain[i + 1:i + 2]} for i, revision in enumerate(chain)])
        elif count:
            sdk.append({'operation': 'branch.list_commits', 'result': {'items': [{'id': revision} for revision in ids], 'hasMore': False}})
        space('activeSpace', 'active_space')
        current, historical_paths = {r['path']: dict(r) for r in oracle}, []
        for step, revision in zip(steps, ids):
            n = step['step']; current[step['path']]['sha256'] = step['sha256']
            if native:
                generation = f'g-history-{n:03}'; historical_path = root + '/library/native/' + generation + '/tree'
                cli('restore', revision, 'history-%03d' % n, result={'path': historical_path, 'base_revision': revision})
                sample['historical_restore_steps'].append({'step': n, 'revision': revision, 'generation': generation,
                    'restore_seconds': .003, 'restore_read_seconds': .004, 'restore_cleanup_seconds': 0.0, 'cleanup_operation': 'none; native tree retained'})
            else:
                historical_path = '/workspaces/' + str(n + 3)
                sample['historicalRestoreSamples'].append({'step': n, 'commitId': revision, 'verified': True,
                                                           'restoreMs': 6.0, 'readMs': 8.0, 'cleanupMs': 1.0})
                sdk.append({'operation': 'workspace.unmount', 'result': None})
            historical_paths.append(historical_path)
            read(list(current.values()), historical_path, 'historical_full_read_' + str(n))
        read(oracle, by_name[names[0]]['path'], 'main_unchanged')
        read(oracle, by_name['second']['path'], 'second_unchanged')
        read(oracle, sample['source'], 'source_unchanged')
        if native:
            cli('list', result={'branches': {'main': initial, 'second': initial, 'work': previous}})
        else:
            sample['lifecycle']['attemptedUnmounts'] = sample['lifecycle']['confirmedUnmounts'] = historical_paths + [v['path'] for v in views]
            sdk.extend([{'operation': 'workspace.unmount', 'result': None} for _ in range(3)])
            sdk.extend([{'operation': 'sandbox.close', 'result': None}, {'operation': 'client.close', 'result': None}])
        space('postHistorySpace', 'post_history_space')
        outputs[root + '/logs/lifecycle.jsonl'] = b'{"event":"complete_inert_evidence"}\n'
        if native:
            outputs[ledger] = b'{"event":"inert_external_ledger"}\n'
        rows, files = [], {}
        for index, (source, body) in enumerate(sorted(outputs.items())):
            name = (f'{index:06}-' if native else '') + Path(source).name
            rows.append({'source': source, 'archived': ledger + '.logs/' + name, 'bytes': len(body), 'sha256': audit.digest(body)})
            files[name] = body
        total = sum(len(b) for b in files.values())
        sample['completeLogArchive'] = rows
        sample['archiveAdmission'] = {'allowanceBytes': allowance, 'plannedBytes': total, 'admitted': True,
            'plannedFiles': len(rows) if native else [{k: row[k] for k in ('source', 'archived', 'bytes')} for row in rows]}
        sample['archiveCopy'] = {'complete': True, 'completedFiles': len(rows), 'sourceFilesRetained': True}
        if native:
            sample['archiveCopy'].update(copiedBytes=total, destination=ledger + '.logs')
        else:
            sample.update(sourceLogBytes=total, externalLedgerBytes=100)
        return record, sample, files


class LatestCombinedSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixture = EvidenceFixture(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.fixture.reset()
        self.restorations = []

    def tearDown(self):
        for path, body in reversed(self.restorations):
            if path.is_symlink() or path.exists():
                path.unlink()
            if body is not None:
                path.write_bytes(body)

    def sample(self, index=0):
        return self.fixture.samples[audit.ORDER[index][0]]

    def record(self, index=0):
        return self.fixture.driver['records'][index]

    def summary(self, save=True):
        if save:
            self.fixture.save()
        return audit.summarize(self.fixture.input, self.fixture.archive)

    def reject(self, save=True):
        value = self.summary(save=save)
        self.assertFalse(value['complete'], value)
        self.assertIsNone(value['ratios'])
        self.assertTrue(value['errors'] or any(r['errors'] for r in value['records']))
        return value

    def replace_file(self, path, body):
        self.restorations.append((path, path.read_bytes() if path.exists() else None))
        if path.exists() or path.is_symlink():
            path.unlink()
        if body is not None:
            path.write_bytes(body)

    def test_valid_four_realistic_raw_samples_and_200_readbacks(self):
        value = self.summary()
        self.assertTrue(value['complete'], value)
        self.assertEqual(value['verifiedRecords'], 4)
        self.assertEqual(value['verifiedHistoricalReadbacks'], 200)
        self.assertEqual(value['ratios']['identical']['values']['importForkReadMs'], 2)
        self.assertIsNone(value['ratios']['identical']['values']['historicalCleanupMs'])
        self.assertIn('nativeExecuteIncludingPostHistorySeconds', value['records'][0]['unmatchedScopes'])
        self.assertIn('layerfsFullAdapterIncludingSetupCleanupSeconds', value['records'][1]['unmatchedScopes'])
        self.assertEqual(value['records'][0]['metrics']['initInclusiveImportForkReadMs'], 10)
        self.assertNotEqual(value['records'][2]['metrics']['activeUsedBytes'], value['records'][2]['metrics']['postHistoryUsedBytes'])
        self.assertTrue(any('NOT exact metadata or hardlink parity' in s for s in value['limitations']))

    def test_missing_or_not_run_records_are_retained_without_ratios(self):
        self.record(2).update(status='failed', correct=False, error={'message': 'deliberate failure'})
        self.record(3).update(status='not_run', correct=False)
        self.fixture.driver.update(complete=False, status='failed')
        value = self.reject()
        self.assertEqual([r['status'] for r in value['records']], ['passed', 'passed', 'failed', 'not_run'])
        self.assertEqual(value['verifiedRecords'], 2)
        self.fixture.driver['records'].pop()
        self.assertEqual(self.reject()['records'][3]['status'], 'missing')

    def test_wrong_record_order_or_extra_record_cannot_be_completed(self):
        self.fixture.driver['records'][0], self.fixture.driver['records'][1] = self.fixture.driver['records'][1], self.fixture.driver['records'][0]
        self.reject()
        self.fixture.reset()
        self.fixture.driver['records'].append(copy.deepcopy(self.record(0)))
        self.reject()

    def test_authoritative_raw_bytes_hash_required(self):
        self.fixture.save()
        path = self.fixture.results / ('latest-combined-' + audit.ORDER[0][0] + '.json')
        self.replace_file(path, path.read_bytes() + b' ')
        self.reject(save=False)

    def test_embedded_sample_is_not_an_authority(self):
        self.record(0)['sample'] = {'ok': False, 'wrongJavascriptRoundedValue': 9007199254740992}
        self.assertTrue(self.summary()['complete'])

    def test_manifest_raw_hash_and_exact_fixed_pin_required(self):
        self.fixture.driver['identitySha256'] = '0' * 64
        self.reject()
        self.fixture.reset()
        identity = copy.deepcopy(self.fixture.identity)
        identity['sprig']['sha'] = 'f' * 40
        body = encoded(identity)
        self.replace_file(self.fixture.results / 'latest-combined-identity.json', body)
        self.fixture.driver.update(identity=identity, identitySha256=audit.digest(body))
        self.reject()

    def test_self_consistent_oracle_mutation_cannot_change_frozen_recipe(self):
        oracle, _ = audit.frozen_fixture('identical')
        oracle = copy.deepcopy(oracle); oracle[0]['sha256'] = 'a' * 64
        body = encoded(oracle)
        self.replace_file(self.fixture.results / 'latest-combined-identical-oracle.json', body)
        manifest = copy.deepcopy(self.fixture.manifest); manifest['cases'][0]['oracleSha256'] = audit.digest(body)
        manifest_body = encoded(manifest)
        self.replace_file(self.fixture.results / 'latest-combined-fixtures.json', manifest_body)
        self.fixture.driver.update(fixtureManifest=manifest, fixtureManifestSha256=audit.digest(manifest_body))
        self.reject()

    def test_copied_recipe_and_final_oracle_actual_bytes_are_bound(self):
        for name in ('steps', 'final'):
            with self.subTest(name=name):
                path = self.fixture.results / ('latest-combined-history-distributed-' + name + '.json')
                old = path.read_bytes()
                path.write_bytes(old + b' ')
                self.reject()
                path.write_bytes(old)

    def test_wrong_source_schema_backend_pin_or_injected_test_mode_fails(self):
        for key, value in (('source', '/inert/wrong-fixture'), ('schema', 'old-combined'), ('backend', 'projection'),
                           ('production_sha', 'e' * 40), ('testOnly', True), ('complete_metadata_verification', True)):
            with self.subTest(key=key):
                old = self.sample()[key]; self.sample()[key] = value
                self.reject(); self.sample()[key] = old

    def test_native_omitted_metadata_marker_is_explicit_not_missing_or_other_null(self):
        self.assertTrue(self.summary()['complete'])
        for key, value in (('metadata_branch_available', False), ('metadata_branch_probe', 'measured'),
                           ('metadata_branch_seconds', 0.0), ('init_seconds', None), ('wholeTaskSeconds', None)):
            with self.subTest(key=key):
                old = self.sample()[key]; self.sample()[key] = value
                self.reject(); self.sample()[key] = old
        del self.sample()['metadata_branch_seconds']; self.reject()

    def test_numeric_timings_reject_boolean_negative_and_nonfinite(self):
        for value in (True, -1, '0.01'):
            with self.subTest(value=value):
                old = self.sample()['init_seconds']; self.sample()['init_seconds'] = value
                self.reject(); self.sample()['init_seconds'] = old
        for value in (float('nan'), float('inf'), True, -1):
            with self.assertRaises(ValueError):
                audit.number(value, 'test')
        with self.assertRaises(ValueError):
            audit.strict_json(b'{"value":NaN}')

    def test_duplicate_json_keys_and_malformed_input_are_failed_reports(self):
        body = self.fixture.input.read_bytes()
        self.replace_file(self.fixture.input, b'{"schema":"a","schema":"b"}')
        self.reject(save=False)
        self.fixture.input.write_bytes(b'[')
        value = self.reject(save=False)
        self.assertEqual(len(value['records']), 4)
        self.fixture.input.write_bytes(body)

    def test_cleanup_requires_known_zero_normal_outer_and_runtime_restoration(self):
        changes = [(0, 'remainingMountsKnown', False), (0, 'remainingServers', [{'pid': 7}]),
                   (1, 'remainingContainersKnown', False), (1, 'remainingContainers', ['still-running'])]
        for index, key, value in changes:
            with self.subTest(index=index, key=key):
                old = self.sample(index)[key]; self.sample(index)[key] = value
                self.reject(); self.sample(index)[key] = old
        self.record(1)['runtimeLeave']['restored'] = False; self.reject()
        self.record(1)['runtimeLeave']['restored'] = True
        self.record(0)['cleanup']['complete'] = False; self.reject()

    def test_budget_resource_and_archive_admission_fail_closed(self):
        for target, key, value in ((self.record()['postRuntimeBudgetAdmission'], 'admitted', False),
                                  (self.record()['budgetAdmission'], 'remainingSeconds', 479),
                                  (self.record(), 'archiveAllowanceBytes', 1),
                                  (self.sample()['archiveAdmission'], 'admitted', False),
                                  (self.fixture.driver, 'imageBytes', 4 * 1024**3)):
            with self.subTest(key=key):
                old = target[key]; target[key] = value
                self.reject(); target[key] = old

    def test_archive_corruption_missing_extra_symlink_and_hardlink_refused(self):
        row = self.sample()['completeLogArchive'][0]
        path = self.fixture.archive / (audit.ORDER[0][0] + '.jsonl.logs') / Path(row['archived']).name
        old = path.read_bytes()
        self.replace_file(path, old + b'x'); self.reject()
        path.unlink(); self.reject()
        path.symlink_to(self.fixture.results / 'latest-combined-identity.json'); self.reject()
        path.unlink(); path.write_bytes(old)
        extra = path.parent / 'extra.stdout'
        self.replace_file(extra, b'extra'); self.reject()
        extra.unlink()
        os.link(path, extra); self.reject()

    def test_archive_and_command_source_parent_or_filename_substitution_refused(self):
        for key, value in (('source', '/inert/other/logs/lifecycle.jsonl'),
                           ('archived', '/inert/runner/latest-combined-records/wrong.jsonl.logs/000000-lifecycle.jsonl')):
            old = self.sample()['completeLogArchive'][0][key]
            self.sample()['completeLogArchive'][0][key] = value
            self.reject(); self.sample()['completeLogArchive'][0][key] = old
        command = self.sample()['commands'][0]
        command['stdoutPath'] = command['stderrPath']; self.reject()

    def test_command_hash_bytes_and_missing_complete_streams_rejected(self):
        command = self.sample()['commands'][0]
        for key, value in (('stdoutSha256', 'f' * 64), ('stdoutBytes', True), ('outcomeKnown', False), ('returncode', 1)):
            old = command[key]; command[key] = value
            self.reject(); command[key] = old
        self.sample()['commands'].pop(); self.reject()

    def test_self_consistent_wrong_checksum_stdout_cannot_claim_full_read(self):
        sample = self.sample(3)
        command = next(r for r in sample['commands'] if r.get('purpose') == 'historical_full_read_40')
        entry = next(r for r in sample['completeLogArchive'] if r['source'] == command['stdoutPath'])
        path = self.fixture.archive / (audit.ORDER[3][0] + '.jsonl.logs') / Path(entry['archived']).name
        old_body = path.read_bytes()
        changed_body = old_body.replace(b': OK\n', b': NO\n', 1)
        self.assertEqual(len(old_body), len(changed_body))
        self.replace_file(path, changed_body)
        entry['sha256'] = command['stdoutSha256'] = audit.digest(changed_body)
        self.reject()

    def test_history_duplicate_id_missing_row_and_readback_flags_rejected(self):
        native = self.sample(2); layer = self.sample(3)
        native['checkpoint_steps'][1]['revision'] = native['checkpoint_steps'][0]['revision']; self.reject()
        self.fixture.reset(); native = self.sample(2); layer = self.sample(3)
        native['historical_restore_steps'].pop(); self.reject()
        self.fixture.reset(); layer = self.sample(3)
        layer['historicalRestoreSamples'][40]['verified'] = False; self.reject()
        self.fixture.reset(); layer = self.sample(3)
        layer['historyCheck']['samples'][2]['commitId'] = layer['historyCheck']['samples'][1]['commitId']; self.reject()

    def test_native_103_generations_and_both_three_live_view_boundaries_required(self):
        post = self.sample(2)['lifecycle']['activeAfterHistory']
        post['generationDirectories'].pop(); post['retainedGenerationCount'] -= 1; self.reject()
        self.fixture.reset()
        self.sample(3)['postHistoryBoundary']['views'].pop(); self.reject()
        self.fixture.reset()
        self.sample(2)['lifecycle']['activeAtSpace']['historicalReadbacksStarted'] = True; self.reject()

    def test_frozen_writer_and_full_history_checksum_command_cannot_be_weakened(self):
        target = next(r for r in self.sample(3)['commands'] if r.get('purpose') == 'historical_full_read_40')
        target['command'] = 'true'; self.reject()
        self.fixture.reset()
        target = next(r for r in self.sample(2)['commands'] if r.get('argv', [])[:2] == ['bash', '-c'] and 'conv=notrunc,fsync' in r['argv'][2])
        target['argv'][2] = target['argv'][2].replace('conv=notrunc,fsync', 'conv=notrunc'); self.reject()

    def test_space_sample_cannot_be_swapped_or_substituted(self):
        self.sample()['postHistorySpace']['filesystemUsedBytes'] += 1; self.reject()
        self.fixture.reset()
        self.sample()['activeSpace'], self.sample()['postHistorySpace'] = self.sample()['postHistorySpace'], self.sample()['activeSpace']
        self.reject()

    def test_native_nonzero_transport_and_layerfs_missing_runtime_restore_rejected(self):
        self.record()['sampleReturncode'] = 1; self.reject()
        self.fixture.reset()
        del self.record(1)['runtimeLeave']; self.reject()

    def test_cli_writes_complete_failure_summary_and_never_overwrites(self):
        self.record(3).update(status='not_run', correct=False); self.fixture.save()
        output = self.fixture.root / 'failed-summary.json'
        self.replace_file(output, None)
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = audit.main(['--input', str(self.fixture.input), '--archive-root', str(self.fixture.archive), '--output', str(output)])
        self.assertEqual(code, 1)
        failed = json.loads(output.read_text())
        self.assertEqual(len(failed['records']), 4); self.assertIsNone(failed['ratios'])
        before = output.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(['--input', str(self.fixture.input), '--archive-root', str(self.fixture.archive), '--output', str(output)]), 1)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(json.loads(stdout.getvalue())['verifiedRecords'], 3)

    def test_json_parser_caps_distinguish_raw_and_driver_and_failed_summary_is_bounded(self):
        self.assertEqual(audit.RAW_LIMIT, 16 * 1024**2)
        self.assertEqual(audit.DRIVER_LIMIT, 64 * 1024**2)
        path = self.fixture.root / 'oversized.json'
        self.replace_file(path, b'')
        with path.open('wb') as stream:
            stream.truncate(audit.RAW_LIMIT + 1)
        with self.assertRaises(ValueError):
            audit.read_json(path)
        with self.assertRaises(ValueError):
            audit.admit_output(self.fixture.input, self.fixture.archive, self.fixture.root / 'summary.json', b'x' * (audit.RAW_LIMIT + 1))

    def test_ci_output_admission_uses_actual_complete_inventory_plus_manifest_reserve(self):
        output = self.fixture.results / 'latest-combined-summary.json'
        archive = self.fixture.root / 'latest-combined-records'
        with patch('latest_combined_collect.inventory', return_value={'bytes': audit.ARTIFACT_BYTES - audit.MANIFEST_RESERVE,
                                                                      'completeNamedInventory': True}) as inventory:
            with self.assertRaises(ValueError):
                audit.admit_output(self.fixture.input, archive, output, b'{}\n')
            inventory.assert_called_once_with(self.fixture.results, self.fixture.root)
        with patch('latest_combined_collect.inventory', return_value={'bytes': 1000, 'completeNamedInventory': True}):
            audit.admit_output(self.fixture.input, archive, output, b'{}\n')

    def test_reader_never_invokes_subprocess_or_workload(self):
        with patch('subprocess.Popen', side_effect=AssertionError('offline reader must not spawn')), \
             patch('subprocess.run', side_effect=AssertionError('offline reader must not spawn')):
            self.assertTrue(self.summary()['complete'])


if __name__ == '__main__':
    unittest.main()
