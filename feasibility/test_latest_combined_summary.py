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


# Reduced raw-contract fixtures from immutable run40338242966 / af859651.
# Original identical SHA256:3134ad17c66af760ec0a0b23a9fd090b281991098d1fd1dd8db4940ad4417ccb
# Original history SHA256:c2233433f0fedde7d6bca1fb04e0906b33521ee5592645e34ef4614c02ecefd3
# These preserve actual IDs, page envelopes/cursors and failure flags; commit
# metadata unrelated to this parser regression is intentionally not duplicated.
CAPTURED_LAYERFS_CLOSE = {'operation': 'client.close', 'mutation': False}
CAPTURED_HISTORY_NEWEST_FIRST = '''
12fb6ed74e9fb87c4f0e5eb822d1f023b110096d786fc904a3b52d1861b4310f8b
127a085af0852bca11499c2af260cb002057cdf22b1048df6918c927f56c9b4a0a
12300e8743510670a1f6ca52d55d98a857ec0bbd54b4d2397b1a076066332065ab
1229e948584fa478a3e64ac0ad907adca0f96374b6cdde8486ea3487b90c52367f
1293888408746ad9fa0d8a107c329de969b348c3a1fc2a8440743d1b16cc05772d
1234148228f077e928e0c71d9093e43e97f4f8748138ba2af1481785bbac117de8
12e41665675603c64e56b68bb2d7f6207412cd5be6dcb9907bb5341d1239c7e395
12e479bf7e10e4c96808b7d555004df6a538d1addf7f1d30e7e99f9cc526fcdae7
129fe5b7649528bf21239efe4ec711909b75882dc1603b262e112c276b6390ce17
12fb1953bd2592b6d299902a37991a5f2ef3fb8c4778369edef19396e0c78e2be0
12fcf432ae67179008cac68d5ddd17e3dd9755edd101462a9638026de1d505fb44
12eaaa4cf4413b3f445987c391dce63efd2d9a367321849bd125decef4f766afb3
125ae04d5578b577be35598dfd481f9e47be6d3de59cfe79fa79ce4c550d0b440d
129750f7fc2661b6d29b26befcb697e721e8f9808e61f218fae63959e983d59ee0
12a76687b18b79a60617e1a1cfa3763ece673f0e22900d9e736309b577688487a2
12ea3d8e54674c2ab993fe311c175c348a7b01cd795c4400878543b8c2716933ed
12d60a4ebb5c3d2ad51282581f1bccccc7adee7d45991979755b9bb0bc8ddfeb6d
12be49f6477be162f5333cf49b2b1621423b69499f083ab3c5470e06bb8a45c579
1283e721230178db1693ace94366efafab10a22d36a751d23aeadbd23e9167adfc
122ccc24c8387f4c19e85ace0f330e4cb1ccbf80094505263771d7f073d6befa36
129c662e765f6751806751243d1f82265d96c68c4538088e872644c62ce005dc3e
12d4c04281f88e550939abcc29bd03c557fcb360084c3186b2a89b320606427509
12c29f946cc253a759789633c3521c51e5c0314f5a2399bcd0b5ead4894c08e38f
12d722c298a3e9e8cd3d674d5a8ce346be2d55653cff9e25055ec574bc75071f59
1236aa39ab58536a05abe92484cb3864047dbc17018462cc862364547ac08ef9c4
121dc174abe4891f62d47750d0d89946591b1d6dfa0a4b9da36cd47a17a8992d2d
12d272fc312148df33f59171900ede7b0bdf9f3aa395d3fc8479030d688e5806d0
1220daf0ef5ea0d6964629cd89da2cb89ae06076856c4d5097779f740977834a57
1267f6dfe08ee0284c827da60d4226b2ec3160abb73b114cbf8803fcf24facb82a
1277e65f04f4302473f5c79391853a5a896f219407df16562f3ae8f30fdd722ddc
12f839d6cb6ca6c620910f7119697e2158800d0c6298abc7f4e7b89bd50c239e4d
120796cc7f5938fb0a89b713e86425d27aa8447f4fd1bbbe337e4512f48ccf12fd
12cec73966370b9c25a3dace12f3cce1e8c9e29aa8d5a45b71e3ab199c1e798fce
121844e0315d31c2b440ccecd021ecc18bb89f8190079616719670f436f794068e
123a51e3cfcc2f846d996903c2db845afbd0d37fe5a57ae0cc19d16e7b15588fab
1252f19aab534b655c68565f2a206054d8d1ca06c419ddc1d2319451c8c1f6a7e0
12b59c256055d56e2eaded06a0eed959f829855fef9d08f2302149d91a693c1187
1210b3146d3a9c44343fa2930843905839f9b64898b7eb471b6a3575f4fbcf8a09
12f12807b1bab4945dcd204e7135e81e3bf4e11bdde1b9b94411298e3ea602a5a7
1217cffc1481d6377e5e1960f5367fc3002268f1c881f9ac4f9300215c904588cc
12f4d431206f300aa8b890ee8918e2f04114adb636114c1e6139eee9c6468faa2e
121b7a1ddc9869908651d869ba65e01f41817ecb8cb109e601e0ab98d0d9a07823
1236e599401521f8f4a583dca0732f9a2f6b8e54cb30798d181404567483e84449
127fb128dba4ecdbc8906a998dd2bf4b9f5c269cc91267efb18da86cfb0c388eed
12b4b76ecff14e1d1c63e47358743bf80a3ada16d7daaa7435575405df10b3cb5a
12c3b6439e639b4d0c56f372ef8d852eafdb42ba0a59714efcb8ddf4b0b1b67a03
12ce6bd3eb7dfda1905831fd1695e951f68e22e90077048f8a55488f5b10cfb48d
12a73c5e51f275018df2d34cdbec3a037f3f89714747621c60beb9fd3828e589e0
12221209f36e5caa51554910a16387163aa84d536a00814593626fd1a5dc3677d7
12a42b2492117551a77d3d39f0c530367abcac0c1a091f703da4443e025cf44247
1260d8cedfc7dfe9762925a40055ff1be5b9dafc793b5420be9defca3f603b74f0
1291a63b3e794c446c3f9e7d9e2aec879cb5b302d5c606dc4e192d18009b071215
121d3484afd06b2967e8ddce8ff4f7b8594e3161b5cd54271b6ce2e1d021679d83
12cc6f7014830d3a7a4196491a773ab7a8d810041ff0dbc5ec66dc0021d3290be2
1230fa8d1967f14c7cbf8cdcf13799db1c4a2d6432e852561a8df74cb641c6ae37
1295ed6ef96c566a2fee2b09fb4ceb0ddd612141a455e5e06035a22cb9717bbe89
124ef65bb46e823585cf389058530d2051f16c83376f1504b0a712b04c222d5ea6
127f064350ce252115f6afda5a6a53e394e25b6a6a30e1d8a30e2270cc7c5f293c
121a89d9570b17d091371222eeb74b089158371a1e8f5a1f03c8ecdd692319b6db
12481258015be74eeea7c01f56407618adcd1f3e9c69d75ecf85cc3e12440d6ce3
1241e520278d19cfd6b23f5b677576dd8be72487981486789c1a7f0062f7fee480
12225c3028ed6e17c611cd840cd8097406174de9aeba0f0ca765c3d030a57e6a46
122c8f055a92d2432edd2292c747b71f3d793c6d6d99157ef7a2aab70ae183ee9a
124bcbf8181292e8548a37a34a09b2cda718d7b2e8a89661cf9a47c2e25b8076ae
1287acec882a0805d21fb185919ccf84457e2f413f1d63f73ca2cfdcfa8b5688a8
1299a9f6715ab8335166159602fd30ed8369d2d74edae0fd64be09ce1353cac4ae
12755037d32f8743c3b661b8127113a7ed97cb7475d389c13955693964dde6b6bc
128dfc215fdd0ee2a1668dfe5d4548a0444da54ca45ad5f487ddfe708a9834716f
12c370e0e23a5e163cccd692fa87a0c2b901120a02e4c055a38c7280c7212018a9
128dae6b19e786e2bc97d4b1b0bd6ba138085980046175151a856055eb06e8f4e2
12d1ad037b7888bc1a6c963ea41bb87433660f88f01df9c20382f7348fc20b2e5b
12e349a020874598ec100d434f18860c1584b3cfe4c2e2e236af332d09eedb936a
127571da56ab9d0976e931ee2b4ca8fc755e6131d4aa0ffdee88d1f9857e5cba88
12cdb044985788df72202caaaee9815c836fb0687e5fdd1e648af1f512f2cdbd9e
12a4ceb021386fe8e04d2532f89dd42891184db8c16c59c3c9b4d7d74a5489054a
12b328f47c3b4137adf1b2c76477115418b2ffa2241368c19ae2e2d0d763e27345
12c14ce2dc6ca30a221d85750c71b64d5a22436d950ba8b8258edc89f8efe966d3
12f25323e352039654e7ede8d100130bd8314d187f6ad949885735775313750fb1
12e71930e861961bc7416239ca270ec16c14f9a66dbe61969930af3236af60617a
12ae8da08f8f7bb478f963d6794d793f4e435a21361ba2f2cd185f0e2f3604ce26
12b410d4e218155919e6b338072f70f392cc24d5ccc886d4524cc7641f94a86a13
12201c1e25ebf5b0396690648a1777624d1b5b5236713994345d1b8daf7ad17aef
1208622bbb5be66acd5761717aaa73399b73271633c8245e57501d75f4a13a63f4
1257ca660fe557a79c1944f43506d94279802e004f18ad40e6f5ba1298f6f9b246
127fcdc7a0439454e6bb4c268a64ad3aa5a7ee490d7920c3333fbb220075cdcb2f
129b96ae50b72c6206f3968fb6ecb7661047269af794415fc06120c8f3f52a8786
12428338899e1aa083f1278916eab367ef637c0856074485239b05e4a19703b3cd
121e6575718e17064717644eab30ec68d3a93714300d6d519e013a440168841c2f
1295450781b41b8be696bc1dfdfe34fb6f4c799468f3fe265dded3a9f28176762f
121276ca3c5589b5d2b1dabd39f193d12dea8f3288e3377309fcc110648427165d
1269008c631811b11486c6bcd9bd23bfa5bea52f41f64099f702bf233fa7d6978d
12edee0e0824b8c97cff74b3189e91288777255b2a63e27e6a1a6f812cc0adfc9c
12428f862ac9d092ecc1b7fc6efb37311e7f8cb82488a0123bece0cf825b3e5bea
12ef8ba652c2997f0e782c2a375cbdb04afaf44d6babbe0363f3f315f8b6155054
121289fa96023c1190492d875d6d0b91ad681afdaedbf023d10cfeb085aeed1176
127dd1f8a05be0cd2d817c6a1a629faa4f860e878bafde7c68c8b7284582d75220
122647baae0e80886d3cd2640c68ee5d5dd1c2459e8b6cc6dce47e420fae9cc5ef
12479d78093561be7bd60b721834c9db4da9dcb23d404dd818cdb892984fc1965e
12ae6b54a150f523bd448639040354476591155f0d38115eaec4675f632d442716
1293e43ad808ace52f425093369f3bb6089b89b387502d78bcbbd149a8ac8bcc69
'''.split()
CAPTURED_HISTORY_LAYOUT = ((0, False, None), (46, True, 46), (46, True, 92), (8, False, None))
CAPTURED_HISTORY_FAILURE = json.loads(r'''{"ok":false,"error":{"type":"LayerFSError","uncertain":true},"fullHistoricalSnapshotReadbacks":100,"postHistorySpace":null,"postHistoryBoundary":null,"remainingMountsKnown":false,"remainingContainersKnown":false,"remainingContainers":null,"cleanupErrors":[{"message":"SDK mutation/exec outcome unknown; retain all live state without retry"}]}''')


def captured_history_pages():
    pages, offset = [], 0
    for count, more, cursor in CAPTURED_HISTORY_LAYOUT:
        pages.append({'operation': 'branch.list_commits', 'mutation': False,
                      'result': {'items': [{'id': value} for value in CAPTURED_HISTORY_NEWEST_FIRST[offset:offset + count]],
                                 'hasMore': more, 'nextPagePos': cursor}})
        offset += count
    return pages


def captured_sdk_history():
    pages = captured_history_pages()
    commits = [{'operation': 'workspace.commit', 'mutation': True,
                'result': {'kind': 'Committed', 'head': value, 'commit': {'id': value}}}
               for value in reversed(CAPTURED_HISTORY_NEWEST_FIRST)]
    return [pages[0], *commits, *pages[1:]]


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
        ids = ([f'{i + 1:064x}' for i in range(count)] if native else
               list(reversed(CAPTURED_HISTORY_NEWEST_FIRST)) if count else [])
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
                sdk.append(captured_history_pages()[0])
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
            sdk.extend(captured_history_pages()[1:])
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
                sdk.append({'operation': 'workspace.unmount', 'result': {'kind': 'Unmounted'}})
            historical_paths.append(historical_path)
            read(list(current.values()), historical_path, 'historical_full_read_' + str(n))
        read(oracle, by_name[names[0]]['path'], 'main_unchanged')
        read(oracle, by_name['second']['path'], 'second_unchanged')
        read(oracle, sample['source'], 'source_unchanged')
        if native:
            cli('list', result={'branches': {'main': initial, 'second': initial, 'work': previous}})
        else:
            sample['lifecycle']['attemptedUnmounts'] = sample['lifecycle']['confirmedUnmounts'] = historical_paths + [v['path'] for v in views]
            sdk.extend([{'operation': 'workspace.unmount', 'result': {'kind': 'Unmounted'}} for _ in range(3)])
            sdk.extend([{'operation': 'sandbox.close', 'result': {'kind': 'Closed', 'sandbox': 'sandbox-one'}},
                        copy.deepcopy(CAPTURED_LAYERFS_CLOSE)])
            for operation in sdk:
                operation['mutation'] = operation['operation'] not in {'client.close', 'branch.list_commits'}
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

    def test_captured_post_readback_eof_failure_never_acquires_metrics_or_ratios(self):
        # The real history sample completed100 readbacks but then lost the
        # sandbox.list_workspaces reply (UnexpectedEof) before post-history space.
        # Applying only its captured failure shape must not promote it to success.
        sample = self.sample(3)
        sample.update(copy.deepcopy(CAPTURED_HISTORY_FAILURE))
        sample['remainingMounts'] = copy.deepcopy(sample['lifecycle']['activeAtSpace']['views'])
        sample['lifecycle']['uncertain'] = True
        sample['lifecycle']['cleanup']['complete'] = False
        sample['sdkOperations'] = [r for r in sample['sdkOperations'] if r['operation'] not in {'client.close', 'sandbox.close'}]
        for _ in range(3):
            self.assertEqual(sample['sdkOperations'].pop()['operation'], 'workspace.unmount')
        self.assertEqual(sum(r['operation'] == 'workspace.unmount' for r in sample['sdkOperations']), 100)
        self.fixture.driver.update(complete=False, status='failed')
        self.record(3).update(status='failed', correct=False, error={'message': 'post-readback sandbox.list_workspaces UnexpectedEof'})
        value = self.reject()
        self.assertEqual(sample['fullHistoricalSnapshotReadbacks'], 100)
        self.assertEqual(value['verifiedRecords'], 3)
        self.assertEqual(value['verifiedHistoricalReadbacks'], 100)
        self.assertEqual(value['records'][3]['status'], 'failed')
        self.assertNotIn('metrics', value['records'][3])
        # Even an erroneously optimistic outer wrapper cannot override raw failure.
        self.fixture.driver.update(complete=True, status='passed')
        self.record(3).update(status='passed', correct=True)
        self.record(3).pop('error')
        value = self.reject()
        self.assertEqual(value['records'][3]['status'], 'invalid_evidence')
        self.assertNotIn('metrics', value['records'][3])
        self.assertIsNone(sample['postHistorySpace'])
        self.assertFalse(sample['lifecycle']['cleanup']['complete'])

    def test_missing_sdk_results_or_nonhistory_pages_invalidate_complete_raw_record(self):
        sdk = self.sample(1)['sdkOperations']
        row = next(row for row in sdk if row['operation'] == 'workspace.unmount')
        del row['result']
        self.reject()
        self.fixture.reset()
        self.sample(1)['sdkOperations'].insert(0, captured_history_pages()[0])
        self.reject()

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


class LayerfsCapturedRawContractTests(unittest.TestCase):
    def clean_sample(self, operations=None):
        return {'ok': True, 'remainingMountsKnown': True, 'remainingMounts': [],
                'remainingContainersKnown': True, 'remainingContainers': [],
                'lifecycle': {'normalUnmountOnly': True, 'uncertain': False, 'cleanup': {'complete': True}},
                'sdkOperations': copy.deepcopy(operations if operations is not None else [CAPTURED_LAYERFS_CLOSE])}

    def histories(self, sdk=None, baseline=0, total=100):
        return audit.layerfs_history_sequences(captured_sdk_history() if sdk is None else sdk,
                                               list(reversed(CAPTURED_HISTORY_NEWEST_FIRST)), baseline, total)

    def test_captured_client_close_is_undefined_not_invented_null(self):
        sample = self.clean_sample()
        self.assertEqual(audit.layerfs_sdk_operations(sample), [{'operation': 'client.close', 'mutation': False}])
        self.assertNotIn('result', sample['sdkOperations'][0])
        for value in (None, {}, {'kind': 'Closed'}, False, 'undefined'):
            with self.subTest(value=value):
                malformed = self.clean_sample()
                malformed['sdkOperations'][0]['result'] = value
                with self.assertRaises(ValueError):
                    audit.layerfs_sdk_operations(malformed)

    def test_void_close_requires_exact_envelope_and_known_zero_normal_cleanup(self):
        for row in ({'operation': 'client.close'}, {'operation': 'client.close', 'mutation': True},
                    {'operation': 'client.close', 'mutation': 0},
                    {'operation': 'client.close', 'mutation': False, 'error': None},
                    {'operation': 'client.close', 'mutation': False, 'void': True}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                audit.layerfs_sdk_operations(self.clean_sample([row]))
        for key, value in (('ok', False), ('remainingMountsKnown', False), ('remainingMounts', ['/workspaces/1']),
                           ('remainingContainersKnown', False), ('remainingContainers', None)):
            sample = self.clean_sample(); sample[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.layerfs_sdk_operations(sample)
        for field, value in (('uncertain', True), ('normalUnmountOnly', False)):
            sample = self.clean_sample(); sample['lifecycle'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.layerfs_sdk_operations(sample)
        sample = self.clean_sample(); sample['lifecycle']['cleanup']['complete'] = False
        with self.assertRaises(ValueError):
            audit.layerfs_sdk_operations(sample)

    def test_every_nonvoid_operation_requires_result_and_frozen_mutation_marker(self):
        mutations = ('LayerFS.init', 'sandbox.create', 'branch.fork', 'workspace.mount',
                     'workspace.commit', 'workspace.unmount', 'sandbox.close')
        readers = ('branch.list_commits', 'sandbox.list_workspaces', 'project.list_sandboxes')
        for operation in (*mutations, *readers):
            for variant in ('missing_result', 'wrong_mutation', 'bool_as_integer', 'missing_mutation', 'null_result', 'extra_marker'):
                row = {'operation': operation, 'mutation': operation in mutations, 'result': {}}
                if variant == 'missing_result':
                    del row['result']
                elif variant == 'wrong_mutation':
                    row['mutation'] = not row['mutation']
                elif variant == 'bool_as_integer':
                    row['mutation'] = int(row['mutation'])
                elif variant == 'missing_mutation':
                    del row['mutation']
                elif variant == 'null_result':
                    row['result'] = None
                else:
                    row['void'] = True
                with self.subTest(operation=operation, variant=variant), self.assertRaises(ValueError):
                    audit.layerfs_sdk_operations(self.clean_sample([row]))
        with self.assertRaises(ValueError):
            audit.layerfs_sdk_operations(self.clean_sample([{'operation': 'unknown.close', 'mutation': False}]))

    def test_captured_empty_baseline_then_46_46_8_pages_form_two_histories(self):
        pages = captured_history_pages()
        self.assertEqual([len(row['result']['items']) for row in pages], [0, 46, 46, 8])
        self.assertEqual([row['result']['nextPagePos'] for row in pages], [None, 46, 92, None])
        self.assertEqual(self.histories(), [[], CAPTURED_HISTORY_NEWEST_FIRST])
        # One physical final page is also legitimate; no captured page size is a gate.
        sdk = captured_sdk_history()
        sdk[101:] = [{'operation': 'branch.list_commits', 'mutation': False,
                      'result': {'items': [{'id': value} for value in CAPTURED_HISTORY_NEWEST_FIRST],
                                 'hasMore': False, 'nextPagePos': None}}]
        self.assertEqual(self.histories(sdk), [[], CAPTURED_HISTORY_NEWEST_FIRST])

    def test_pagination_cursor_types_progress_terminal_marker_and_page_shape(self):
        for cursor in (None, 0, 45, 47, -1, True, 46.0, '46', 102):
            sdk = captured_sdk_history(); sdk[101]['result']['nextPagePos'] = cursor
            with self.subTest(cursor=cursor), self.assertRaises(ValueError):
                self.histories(sdk)
        for change in ('missing_cursor', 'terminal_cursor', 'nonbool_more', 'no_progress', 'items_not_array', 'unknown_field'):
            sdk = captured_sdk_history()
            if change == 'missing_cursor':
                del sdk[101]['result']['nextPagePos']
            elif change == 'terminal_cursor':
                sdk[-1]['result']['nextPagePos'] = 100
            elif change == 'nonbool_more':
                sdk[101]['result']['hasMore'] = 1
            elif change == 'no_progress':
                sdk[102]['result']['items'] = []
            elif change == 'items_not_array':
                sdk[101]['result']['items'] = {}
            else:
                sdk[101]['result']['offset'] = 0
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.histories(sdk)

    def test_duplicate_unknown_reordered_or_missing_history_ids_are_rejected(self):
        for change in ('within_page', 'across_pages', 'unknown_id', 'wrong_order', 'missing_id', 'malformed_id'):
            sdk = captured_sdk_history()
            if change == 'within_page':
                sdk[101]['result']['items'][1] = copy.deepcopy(sdk[101]['result']['items'][0])
            elif change == 'across_pages':
                sdk[102]['result']['items'][0] = copy.deepcopy(sdk[101]['result']['items'][0])
            elif change == 'unknown_id':
                sdk[-1]['result']['items'][-1]['id'] = '12' + 'f' * 64
            elif change == 'wrong_order':
                items = sdk[101]['result']['items']; items[0], items[1] = items[1], items[0]
            elif change == 'missing_id':
                sdk[-1]['result']['items'].pop()
            else:
                sdk[-1]['result']['items'][-1]['id'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.histories(sdk)

    def test_unterminated_extra_interleaved_or_wrongly_ordered_logical_sequences(self):
        for change in ('unterminated', 'drop_last_page', 'extra_sequence', 'interleaved', 'late_baseline', 'early_final'):
            sdk = captured_sdk_history()
            if change == 'unterminated':
                sdk[-1]['result'].update(hasMore=True, nextPagePos=100)
            elif change == 'drop_last_page':
                sdk.pop()
            elif change == 'extra_sequence':
                sdk.append(captured_history_pages()[0])
            elif change == 'interleaved':
                sdk.insert(102, {'operation': 'sandbox.list_workspaces', 'mutation': False, 'result': {}})
            elif change == 'late_baseline':
                sdk[0], sdk[1] = sdk[1], sdk[0]
            else:
                commit = sdk.pop(100); sdk.append(commit)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.histories(sdk)

    def test_baseline_is_preserved_exactly_and_total_remains_at_most101(self):
        sdk = captured_sdk_history(); baseline_id = '12' + 'f' * 64
        sdk[0]['result']['items'] = [{'id': baseline_id}]
        sdk[-1]['result']['items'].append({'id': baseline_id})
        self.assertEqual(self.histories(sdk, baseline=1, total=101), [[baseline_id], [*CAPTURED_HISTORY_NEWEST_FIRST, baseline_id]])
        sdk[-1]['result']['items'][-1]['id'] = '12' + 'e' * 64
        with self.assertRaises(ValueError):
            self.histories(sdk, baseline=1, total=101)
        with self.assertRaises(ValueError):
            self.histories(sdk, baseline=2, total=102)


if __name__ == '__main__':
    unittest.main()
