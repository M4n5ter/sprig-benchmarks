#!/usr/bin/env python3
"""Fail-closed offline audit of the fixed eight-sample latest-main Cargo comparison.

This reader neither executes products nor repairs evidence. Standalone raw JSON and
the complete archived command outputs, not JavaScript-rounded embedded trees, are
authoritative. LayerFS's decimal-string nanoseconds are converted only for exact
integer comparison; original evidence is never rewritten.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import statistics
import sys

from stress_cargo_ab_summary import (
    HEX64, PACKAGES, PHASES, digest, finite, read_regular, require, strict_json,
    validate_sample as validate_sprig_sample, verify_archives,
)

SCHEMA = 'sprig-stress-cargo-latest-direct-v1'
SUMMARY_SCHEMA = 'sprig-stress-cargo-latest-direct-summary-v1'
MANIFEST_SCHEMA = 'sprig-cargo-latest-direct-identity-v1'
MANIFEST_FILE = 'stress-cargo-latest-direct-identity.json'
PINS = {'sprig-writable': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
        'layerfs': 'ad78914e36b258b360daf13aec164b5655814689'}
PRODUCTS = tuple(PINS)
PROTOCOL_SHA = '08822e9e6e7cd411561559a689bd91c404b587c95ec452fa62e4018e166b748e'
IDENTITY = ('image', 'productionSha', 'comparatorSha', 'protocolSha256',
            'fixtureManifestSha256', 'imageBytes', 'resourceProtocol',
            'sharedJobBudget', 'directManifest', 'directManifestSha256')
BUILD_PHASES = ('clean_build', 'noop_build', 'edit_build', 'restored_rebuild')
ARTIFACT_PHASES = ('clean_artifacts', 'noop_artifacts', 'edit_artifacts',
                   'restored_artifacts', 'restored_rebuild_artifacts')
PROGRAM_OUTPUTS = {'clean_execute': '269\n', 'noop_execute': '269\n',
                   'edit_execute': '3400\n', 'restored_execute': '3400\n',
                   'restored_rebuild_execute': '3400\n'}
ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError,
          StopIteration, OverflowError, UnicodeError)


def canonical_path(value, name):
    require(isinstance(value, str) and value and '\0' not in value
            and Path(value).is_absolute() and os.path.normpath(value) == value,
            'invalid canonical absolute ' + name)


def exact_int(value, name, minimum=None):
    require(type(value) is int and (minimum is None or value >= minimum), 'invalid integer ' + name)
    return value


def validate_manifest(value):
    require(isinstance(value, dict) and set(value) == {'schema', 'sprig', 'layerfs'}
            and value['schema'] == MANIFEST_SCHEMA, 'invalid latest direct manifest schema')
    base = {'sha', 'ref', 'binary', 'binarySha256', 'sourcePath'}
    for name, product in (('sprig', 'sprig-writable'), ('layerfs', 'layerfs')):
        item = value[name]
        extra = {'sdkPath', 'sdkSha256', 'nativeAddonPath', 'nativeAddonSha256'} if name == 'layerfs' else set()
        require(isinstance(item, dict) and set(item) == base | extra, 'unexpected product manifest fields')
        require(item['sha'] == PINS[product] and item['ref'] == 'main', 'fixed current-main source mismatch')
        for key in ('binary', 'sourcePath') + (('sdkPath', 'nativeAddonPath') if name == 'layerfs' else ()):
            canonical_path(item[key], key)
        for key in ('binarySha256',) + (('sdkSha256', 'nativeAddonSha256') if name == 'layerfs' else ()):
            require(isinstance(item[key], str) and HEX64.fullmatch(item[key]), 'invalid ' + key)
        binary_suffix = 'target/release/sprig' if name == 'sprig' else 'core/target/release/layerfs-daemon'
        require(item['binary'] == str(Path(item['sourcePath']) / binary_suffix), 'binary outside fixed source build path')
        if name == 'layerfs':
            require(item['sdkPath'] == str(Path(item['sourcePath']) / 'api/agent/sdk/src/index.js')
                    and item['nativeAddonPath'] == str(Path(item['sourcePath']) / 'api/binding/layerfs.node'),
                    'LayerFS SDK/addon outside fixed source paths')
    for key in ('binary', 'sourcePath', 'binarySha256'):
        require(value['sprig'][key] != value['layerfs'][key], 'distinct product ' + key + ' required')
    return value


def validate_identity(report, path):
    require(report.get('schema') == SCHEMA, 'requires fixed latest direct schema')
    require(type(report.get('rounds')) is int and report['rounds'] == 2, 'requires exactly two rounds per mode')
    require(type(report.get('expectedRecords')) is int and report['expectedRecords'] == 4,
            'requires four expected records per mode')
    require(report.get('productionSha') == PINS['sprig-writable']
            and report.get('comparatorSha') == PINS['layerfs'], 'fixed latest-main pins mismatch')
    require(report.get('protocolSha256') == PROTOCOL_SHA, 'frozen DAG16 protocol differs')
    require(type(report.get('imageBytes')) is int and report['imageBytes'] == 4 * 1024**3
            and report.get('resourceProtocol') == 'sprig-cargo-resource-4g-v1', 'requires symmetric 4GiB resource protocol')
    require(isinstance(report.get('image'), str) and re.fullmatch(r'sha256:[a-f0-9]{64}', report['image']),
            'invalid shared image identity')
    for key in ('fixtureManifestSha256', 'directManifestSha256'):
        require(isinstance(report.get(key), str) and HEX64.fullmatch(report[key]), 'invalid ' + key)
    require(not any(key in report for key in ('abProducts', 'abManifestSha256', 'experimentSpec')),
            'own-AB or pressure identity in direct ordinary report')
    manifest = validate_manifest(report.get('directManifest'))
    raw = read_regular(path.parent / MANIFEST_FILE)
    require(digest(raw) == report['directManifestSha256'] and strict_json(raw) == manifest,
            'direct manifest raw bytes/hash mismatch')
    fixture_bytes = read_regular(path.parent / 'stress-cargo-manifest.json')
    require(digest(fixture_bytes) == report['fixtureManifestSha256'], 'fixture manifest raw hash mismatch')
    fixture = strict_json(fixture_bytes)
    require(isinstance(fixture, dict) and fixture.get('schema') == 'sprig-stress-cargo-v2'
            and fixture.get('protocolSha256') == PROTOCOL_SHA and fixture.get('packages') == PACKAGES
            and type(fixture.get('crates')) is int and fixture['crates'] == 16
            and type(fixture.get('totalPackages')) is int and fixture['totalPackages'] == 17
            and fixture.get('expectedStdoutBefore') == '269\n' and fixture.get('expectedStdoutAfter') == '3400\n',
            'frozen fixture manifest mismatch')
    tree = normalize_tree(fixture.get('initial'), strings=False)
    require(normalize_tree(strict_json(read_regular(path.parent / 'stress-cargo-oracle.json')), strings=False) == tree,
            'source oracle differs from bound fixture manifest')
    budget = report.get('sharedJobBudget')
    require(isinstance(budget, dict), 'missing shared job budget')
    start = finite(budget.get('startedEpochSeconds'), 'budget start')
    end = finite(budget.get('deadlineEpochSeconds'), 'budget deadline')
    require(0 < end - start <= 2400, 'shared admission deadline exceeds 40 minutes')
    require(type(budget.get('minimumSampleSeconds')) is int and budget['minimumSampleSeconds'] == 180
            and type(budget.get('cleanupReserveSeconds')) is int and budget['cleanupReserveSeconds'] == 300,
            '180s work / 300s cleanup reserves changed')
    return fixture


def normalize_tree(value, *, strings):
    require(isinstance(value, dict) and set(value) == {'schema', 'entries', 'hardlink_groups'}
            and value['schema'] == 'cargo-full-tree-v1', 'full-tree oracle shape mismatch')
    tree = copy.deepcopy(value)
    entries = tree['entries']
    require(isinstance(entries, list) and entries, 'empty or missing full-tree entries')
    seen = {}
    common = {'path', 'type', 'mode', 'mtime_ns'}
    for entry in entries:
        require(isinstance(entry, dict), 'non-object tree entry')
        name = entry.get('path')
        require(isinstance(name, str) and name and '\0' not in name and not name.startswith('/')
                and (name == '.' or all(part not in ('', '.', '..') for part in name.split('/'))),
                'unsafe tree path')
        require(name not in seen, 'duplicate tree path')
        kind = entry.get('type')
        require(kind in ('file', 'directory', 'symlink'), 'unsupported tree entry type')
        wanted = common | ({'size', 'sha256'} if kind == 'file' else {'target'} if kind == 'symlink' else set())
        require(set(entry) == wanted, 'incomplete or unexpected tree entry fields')
        exact_int(entry['mode'], 'tree mode', 0)
        require(entry['mode'] <= 0o777, 'tree mode outside ordinary permission mask')
        if strings:
            require(isinstance(entry['mtime_ns'], str) and re.fullmatch(r'-?(?:0|[1-9][0-9]*)', entry['mtime_ns']),
                    'LayerFS structured nanoseconds must be exact decimal strings')
            entry['mtime_ns'] = int(entry['mtime_ns'])
        else:
            exact_int(entry['mtime_ns'], 'exact raw integer nanoseconds')
        if kind == 'file':
            exact_int(entry['size'], 'file size', 0)
            require(isinstance(entry['sha256'], str) and HEX64.fullmatch(entry['sha256']), 'invalid file content hash')
        elif kind == 'symlink':
            require(isinstance(entry['target'], str) and '\0' not in entry['target'], 'invalid symlink target')
        seen[name] = entry
    require(seen.get('.', {}).get('type') == 'directory', 'full-tree root missing')
    require([e['path'] for e in entries] == sorted(seen, key=os.fsencode), 'tree entries not canonically ordered')
    for name in seen:
        if name != '.':
            parent = str(PurePosixPath(name).parent)
            require(seen.get(parent, {}).get('type') == 'directory', 'tree parent directory missing')
    groups = tree['hardlink_groups']
    require(isinstance(groups, list), 'hardlink groups missing')
    members = []
    for group in groups:
        require(isinstance(group, list) and group and all(isinstance(p, str) for p in group)
                and group == sorted(set(group), key=os.fsencode), 'invalid hardlink group')
        require(all(seen.get(p, {}).get('type') == 'file' for p in group), 'hardlink to non-file')
        baseline = {k: v for k, v in seen[group[0]].items() if k != 'path'}
        require(all({k: v for k, v in seen[p].items() if k != 'path'} == baseline for p in group),
                'hardlink members disagree in metadata/content')
        members.extend(group)
    require(groups == sorted(groups, key=lambda group: os.fsencode(group[0])), 'hardlink group order mismatch')
    files = sorted((name for name, item in seen.items() if item['type'] == 'file'), key=os.fsencode)
    require(sorted(members, key=os.fsencode) == files and len(members) == len(set(members)),
            'hardlink groups do not partition all files exactly')
    return tree


def command_evidence(sample, contents, purpose):
    rows = [row for row in sample.get('commands', []) if isinstance(row, dict) and row.get('purpose') == purpose]
    require(len(rows) == 1, 'missing/duplicate command: ' + purpose)
    row = rows[0]
    require(type(row.get('returncode')) is int and row['returncode'] == 0 and not row.get('signal')
            and not row.get('truncated') and row.get('exitCode', 0) == 0, 'failed/truncated command: ' + purpose)
    for field in ('stdout', 'stderr'):
        require(isinstance(row.get(field), str) and isinstance(row.get(field + 'Path'), str)
                and contents.get(row[field + 'Path']) == row[field].encode('utf-8'),
                'command output not archived exactly: ' + purpose + ' ' + field)
    return row


def verify_common_evidence(sample, report, fixture, contents, *, layerfs):
    require(sample.get('prototype_only') is False and sample.get('workload') == 'stress-cargo-dag16-v2'
            and sample.get('protocol') == 'sprig-stress-cargo-protocol-v2'
            and sample.get('packages') == PACKAGES, 'sample frozen workload identity mismatch')
    require(not sample.get('error') and not sample.get('cleanupErrors') and not sample.get('logArchiveError')
            and not sample.get('reportWriteError'), 'successful sample contains error evidence')
    require(not any(k in sample for k in ('normalPressure', 'normalPressureScriptSha256', 'normalPressureRawSha256'))
            and 'normal_pressure' not in sample.get('phase_seconds', {}), 'ordinary sample contains pressure')
    fixture_tree = normalize_tree(fixture['initial'], strings=False)
    require(normalize_tree(sample.get('fixtureOracle'), strings=layerfs) == fixture_tree, 'sample source oracle differs')
    checkpoint = normalize_tree(sample.get('checkpointTreeOracle'), strings=layerfs)
    for purpose, wanted in (('fixture_verify', fixture_tree), ('main_unchanged', fixture_tree),
                            ('source_unchanged', fixture_tree), ('pre_checkpoint_oracle', checkpoint),
                            ('restore_verify', checkpoint)):
        row = command_evidence(sample, contents, purpose)
        require(normalize_tree(strict_json(row['stdout']), strings=False) == wanted,
                'exact-ns complete tree mismatch: ' + purpose)
    names = [row.get('purpose') for row in sample['commands']]
    require(names.index('pre_checkpoint_oracle') < names.index('restore_verify')
            < min(names.index(p) for p in ('restored_artifacts', 'restored_execute', 'restored_rebuild')),
            'full restore oracle must precede execution/rebuild')
    for purpose, expected in PROGRAM_OUTPUTS.items():
        require(command_evidence(sample, contents, purpose)['stdout'] == expected, 'program output mismatch: ' + purpose)
    toolchain = command_evidence(sample, contents, 'toolchain_verify')['stdout']
    require(toolchain == sample.get('compilerVersionOutput') and re.search(r'^rustc 1\.90\.0 ', toolchain, re.M)
            and re.search(r'^cargo 1\.90\.0 ', toolchain, re.M), 'shared Rust/Cargo 1.90.0 output mismatch')
    observations = sample.get('cargoBuildObservations')
    require(isinstance(observations, list) and len(observations) == 4, 'requires exactly four Cargo build observations')
    for purpose in BUILD_PHASES:
        row = command_evidence(sample, contents, purpose)
        parsed = {'Fresh': [], 'Compiling': []}
        for line in row['stderr'].splitlines():
            if not re.match(r'^\s*(Fresh|Compiling)\s', line):
                continue
            match = re.match(r'^\s*(Fresh|Compiling)\s+([a-zA-Z0-9_-]+)\s+v0\.1\.0(?:\s|$)', line)
            require(match is not None, 'unexpected Cargo package/version line')
            parsed[match[1]].append(match[2])
        fresh = purpose in ('noop_build', 'restored_rebuild')
        require(sorted(parsed['Fresh' if fresh else 'Compiling']) == sorted(PACKAGES)
                and parsed['Compiling' if fresh else 'Fresh'] == [], 'all17 raw Cargo gate failed: ' + purpose)
        observed = [r for r in observations if r.get('phase') == purpose]
        require(len(observed) == 1 and observed[0].get('returncode') == 0
                and observed[0].get('freshPackages') == parsed['Fresh']
                and observed[0].get('compilingPackages') == parsed['Compiling'], 'Cargo structured/raw package mismatch')
        for field in ('stdoutPath', 'stderrPath'):
            require(observed[0].get(field) == row[field], 'Cargo observation output path mismatch')
    artifacts = sample.get('artifactChecks')
    require(isinstance(artifacts, list) and len(artifacts) == 5, 'requires five artifact checks')
    for purpose in ARTIFACT_PHASES:
        actual = strict_json(command_evidence(sample, contents, purpose)['stdout'])
        observed = [r for r in artifacts if r.get('phase') == purpose]
        require(isinstance(actual, dict) and len(observed) == 1
                and {k: v for k, v in observed[0].items() if k != 'phase'} == actual,
                'artifact structured/raw mismatch')
        require(all(actual.get(k) is True for k in ('ok', 'hardlinkProbe', 'exactMtime'))
                and type(actual.get('buildValue')) is int
                and actual['buildValue'] == (1 if purpose in ('clean_artifacts', 'noop_artifacts') else 2)
                and isinstance(actual.get('generatedFiles'), list) and actual['generatedFiles'], 'artifact witness mismatch')
    entries = {row['path']: row for row in checkpoint['entries']}
    prefix = 'target/restore-probe/'
    probe = entries.get(prefix + 'original', {})
    require(probe.get('type') == 'file' and probe.get('mode') == 0o640
            and probe.get('mtime_ns') == 1700000000123456789
            and probe.get('sha256') == digest(b'cargo checkpoint hardlink probe\n')
            and probe.get('size') == len(b'cargo checkpoint hardlink probe\n'), 'checkpoint probe content/metadata differs')
    require([prefix + 'hardlink', prefix + 'original'] in checkpoint['hardlink_groups']
            and entries.get(prefix + 'symlink', {}).get('type') == 'symlink'
            and entries[prefix + 'symlink'].get('target') == 'original', 'checkpoint hardlink/symlink witness differs')
    for key, value in sample['phase_seconds'].items():
        finite(value, 'phase.' + key)
    for key in PHASES:
        finite(sample['phase_seconds'].get(key), 'required phase.' + key)
    phases = sample['phase_seconds']
    require(abs(phases['checkpoint'] - phases['checkpoint_cli'] - phases['checkpoint_readiness']) < 1e-6,
            'checkpoint boundary mismatch')
    finite(sample.get('full_task_seconds'), 'full task')
    exact_int(sample.get('activeSpace', {}).get('filesystemUsedBytes'), 'whole filesystem Used', 0)
    return checkpoint


def validate_layerfs_sample(sample, report, product, incremental, round_, archive_root, fixture):
    require(isinstance(sample, dict), 'raw LayerFS sample is not an object')
    for flag in ('ok', 'fullRestoredTreeVerified', 'originalMainViewUnchanged', 'sourceUnchanged', 'allAcknowledgedIdsPresent',
                 'remainingMountsKnown', 'remainingContainersKnown'):
        require(sample.get(flag) is True, 'LayerFS correctness/inventory failed: ' + flag)
    # Real SDK samples omit testOnly; injection alone adds true. Do not invent a field.
    require('testOnly' not in sample or sample['testOnly'] is False, 'mock LayerFS sample refused')
    require(sample.get('production_sha') == product['sha'] and sample.get('product') == 'layerfs'
            and sample.get('backend') == 'fuse', 'LayerFS product/source mismatch')
    require(type(sample.get('incremental')) is int and sample['incremental'] == incremental
            and sample.get('image') == report['image'] and sample.get('protocolSha256') == PROTOCOL_SHA
            and sample.get('fixtureManifestSha256') == report['fixtureManifestSha256'], 'LayerFS shared identity mismatch')
    require(sample.get('remainingMounts') == [] and sample.get('remainingContainers') == [], 'LayerFS resources remain')
    lifecycle = sample.get('lifecycle', {})
    require(lifecycle.get('normalUnmountOnly') is True and lifecycle.get('cleanup', {}).get('complete') is True
            and lifecycle.get('committedHistoryRetained') is True and lifecycle.get('fileTreesRetainedAtSpace') is True,
            'LayerFS normal cleanup/history retention unconfirmed')
    checkpoint = sample.get('checkpoint', {})
    revision = sample.get('restoredRevision')
    require(checkpoint.get('kind') == 'Committed' and checkpoint.get('head') == revision
            and isinstance(revision, str) and re.fullmatch(r'12[a-f0-9]{64}', revision)
            and checkpoint.get('commit', {}).get('id') == revision
            and isinstance(sample.get('initialHead'), str) and re.fullmatch(r'32[a-f0-9]{64}', sample['initialHead']),
            'LayerFS acknowledged checkpoint/restore identity differs')
    active = lifecycle.get('activeAtSpace', {})
    views = active.get('views', [])
    require(len(views) == 3 and {v.get('name') for v in views} == {'import-main', 'work', 'second'}
            and len({v.get('path') for v in views}) == 3 and len({v.get('sandbox') for v in views}) == 1
            and all(v.get('image') == report['image'] and re.fullmatch(r'/workspaces/[1-9][0-9]*', v.get('path', '')) for v in views),
            'LayerFS exact three live views missing')
    workspaces = active.get('workspaces', [])
    require(len(workspaces) == 3 and {w.get('path') for w in workspaces} == {v['path'] for v in views}
            and all(w.get('activity') == 'Idle' for w in workspaces), 'LayerFS active workspace inventory differs')
    for name in ('work', 'second'):
        path = next(v['path'] for v in views if v['name'] == name)
        require(next(w for w in workspaces if w['path'] == path).get('base') == revision, 'LayerFS live checkpoint head differs')
    sandboxes = active.get('sandboxes', [])
    require(len(sandboxes) == 1 and sandboxes[0].get('sandbox') == views[0]['sandbox']
            and sandboxes[0].get('image') == report['image'] and sandboxes[0].get('workspaces') == 3
            and active.get('controlProcessesRunning') == 1, 'LayerFS live sandbox accounting differs')
    require(all(active.get(key) is True for key in ('fileTreesRetained', 'cargoRestoreReadbackComplete',
                                                  'allRuntimeLogsAndJournalsInsideMeasuredStore', 'verifiedAfterSpace')),
            'LayerFS space boundary unverified')
    compiler = sample.get('compilerContainerIdentity', {})
    require(isinstance(compiler.get('id'), str) and HEX64.fullmatch(compiler['id'])
            and compiler.get('image') == report['image'] and isinstance(compiler.get('project'), str) and compiler['project'],
            'LayerFS shared compiler identity missing')
    contents = verify_archives(sample, archive_root, incremental, 'layerfs', round_)
    expected = verify_common_evidence(sample, report, fixture, contents, layerfs=True)
    raw = sample.get('checkpointTreeOracleRaw')
    require(isinstance(raw, str) and digest(raw.encode()) == sample.get('checkpointTreeOracleSha256')
            and normalize_tree(strict_json(raw), strings=False) == expected
            and raw == command_evidence(sample, contents, 'pre_checkpoint_oracle')['stdout'],
            'LayerFS checkpoint raw oracle/hash mismatch')
    source_raw = sample.get('fixtureOracleRaw')
    require(isinstance(source_raw, str) and normalize_tree(strict_json(source_raw), strings=False)
            == normalize_tree(fixture['initial'], strings=False), 'LayerFS original fixture raw mismatch')
    for purpose, reference in (('fixture_verify', source_raw), ('main_unchanged', source_raw), ('restore_verify', raw)):
        rows = [r for r in sample.get('snapshotOracleComparisons', []) if r.get('purpose') == purpose]
        output = command_evidence(sample, contents, purpose)['stdout']
        require(len(rows) == 1 and rows[0].get('ok') is True
                and rows[0].get('snapshotSha256') == digest(output.encode())
                and rows[0].get('expectedSha256') == digest(reference.encode())
                and rows[0].get('entries') == len(strict_json(output)['entries']), 'LayerFS exact snapshot comparison binding differs')
    inspected = strict_json(command_evidence(sample, contents, 'compiler_container_inspect')['stdout'])
    require(isinstance(inspected, list) and len(inspected) == 1 and inspected[0].get('Id') == compiler['id']
            and inspected[0].get('Image') == report['image'] and inspected[0].get('State', {}).get('Running') is True
            and inspected[0].get('Config', {}).get('Labels', {}).get('layerfs.project') == compiler['project'],
            'LayerFS archived compiler inspection differs')
    return len(contents)


def validate_admission(row, report):
    budget = report['sharedJobBudget']
    for name in ('budgetAdmission', 'postRuntimeBudgetAdmission'):
        value = row.get(name)
        require(isinstance(value, dict) and value.get('admitted') is True, 'missing budget admission: ' + name)
        require(value.get('startedEpochSeconds') == budget['startedEpochSeconds']
                and value.get('deadlineEpochSeconds') == budget['deadlineEpochSeconds']
                and value.get('workReserveSeconds') == 180 and value.get('cleanupReserveSeconds') == 300
                and value.get('requiredSeconds') == 480, 'budget admission identity/reserve differs')
        require(finite(value.get('remainingSeconds'), 'remaining admission budget') >= 480, 'sample admitted without reserves')


def distribution(values):
    return {'n': len(values), 'values': values, 'median': statistics.median(values),
            'minimum': min(values), 'maximum': max(values), 'p95': None, 'p99': None,
            'caveat': 'Two runner-local paired samples per mode; no tails, significance or multi-host inference.'}


def compare_mode(records):
    indexed = {(r['round'], r['product']): r for r in records}
    for product in PRODUCTS:
        require(set(indexed[0, product]['metrics']) == set(indexed[1, product]['metrics']), 'within-product metric set differs')
    common = set.intersection(*(set(r['metrics']) for r in records))
    compared, unmatched, negatives = {}, {}, []
    for name in sorted(common):
        sprig = [indexed[i, 'sprig-writable']['metrics'][name] for i in range(2)]
        layerfs = [indexed[i, 'layerfs']['metrics'][name] for i in range(2)]
        ratios = [s / l if l > 0 else None for s, l in zip(sprig, layerfs)]
        pairs = [{'round': i, 'firstProduct': records[2 * i]['product'], 'sprig': s, 'layerfs': l,
                  'sprigOverLayerfs': ratio, 'percentChange': (ratio - 1) * 100 if ratio is not None else None}
                 for i, (s, l, ratio) in enumerate(zip(sprig, layerfs, ratios))]
        valid = all(value is not None and value > 0 for value in ratios)
        compared[name] = {'sprig': distribution(sprig), 'layerfs': distribution(layerfs), 'pairs': pairs,
                          'medianPairedRatio': statistics.median(ratios) if all(r is not None for r in ratios) else None,
                          'geometricMeanPairedRatio': math.exp(statistics.mean(math.log(r) for r in ratios)) if valid else None,
                          'undefinedRatioReason': None if valid else 'A zero denominator or nonpositive ratio prevents a complete geometric ratio; no pair removed.',
                          'orderStrata': {product: [p for p in pairs if p['firstProduct'] == product] for product in PRODUCTS}}
        negatives.extend({'metric': name, **pair} for pair in pairs if pair['sprigOverLayerfs'] is not None and pair['sprigOverLayerfs'] > 1)
    for product in PRODUCTS:
        unmatched[product] = {name: distribution([indexed[i, product]['metrics'][name] for i in range(2)])
                              for name in sorted(set(indexed[0, product]['metrics']) - common)}
    return compared, unmatched, negatives


def summarize(paths, archive_root):
    paths = [Path(path) for path in paths]
    archive_root = Path(archive_root)
    result = {'schema': SUMMARY_SCHEMA, 'complete': False, 'status': 'incomplete', 'expectedSamples': 8,
              'records': [], 'missingRecords': [], 'reports': [], 'errors': [], 'comparisons': None,
              'unmatchedMetrics': None, 'slowerOrLargerPairs': None,
              'notes': ['All eight samples and exact archive/identity gates must pass before any ratios are emitted; missing/failed attempts are retained.',
                        'Standalone raw JSON and archived command outputs are authoritative; JS embedded exact-ns trees are never used as evidence.',
                        'LayerFS structured decimal-string nanoseconds are compared as exact Python integers without rewriting original evidence.',
                        'Two pairs per mode, one per order stratum: descriptive small N only; no p95/p99 or significance claims.',
                        'Sprig latest main and LayerFS latest main, not LayerFS v1.1.0; source pins are immutable for this finite run.',
                        'Sprig sync/fsync and LayerFS Disposable WAL/OFF, MEMORY/OFF are unequal durability; generation Docker sessions versus persistent SDK costs remain charged.',
                        'Mode results are separate. All phases and Sprig-only composites overlap; do not add/subtract them from whole wall.',
                        'Whole filesystem Used includes runtime/compiler image, target/cache, retained views/history/logs; runtime setup is separately timed, not subtracted from space.']}
    if len(paths) != 2:
        result['errors'].append('exactly inc0 and inc1 input paths required')
    loaded = {}
    for mode, path in enumerate(paths):
        info = {'path': str(path), 'incremental': mode}
        result['reports'].append(info)
        try:
            body = read_regular(path)
            report = strict_json(body)
            require(isinstance(report, dict), 'mode report is not an object')
            loaded[mode] = (path, report, digest(body), None)
            info.update(sha256=digest(body), status=report.get('status'), complete=report.get('complete'), error=report.get('error'))
            require(mode in (0, 1) and path.name == f'stress-cargo-comparison-{mode}.json', 'input report name/order differs')
            fixture = validate_identity(report, path)
            loaded[mode] = (path, report, digest(body), fixture)
            require(type(report.get('incremental')) is int and report['incremental'] == mode, 'mode identity differs')
            require(report.get('complete') is True and report.get('status') == 'passed' and not report.get('error'), 'report incomplete/failed')
        except ERRORS as error:
            result['errors'].append(str(path) + ': ' + str(error))
    if 0 in loaded and 1 in loaded:
        first, second = loaded[0][1], loaded[1][1]
        for key in IDENTITY:
            if first.get(key) != second.get(key):
                result['errors'].append('cross-mode identity mismatch: ' + key)
        previous = second.get('previousGate')
        if not isinstance(previous, dict) or previous.get('sha256') != loaded[0][2]:
            result['errors'].append('inc1 prerequisite hash does not bind exact inc0 report')
    for mode in (0, 1):
        if mode not in loaded:
            rows = []
        else:
            path, report, _, fixture = loaded[mode]
            rows = report.get('records')
            if not isinstance(rows, list):
                result['errors'].append(str(path) + ': records is not a list')
                rows = []
            if len(rows) != 4:
                result['errors'].append(str(path) + ': expected four records, found ' + str(len(rows)))
            for index, row in enumerate(rows):
                audit = {'reportPath': str(path), 'index': index, 'incremental': mode}
                result['records'].append(audit)
                try:
                    require(isinstance(row, dict), 'record is not an object')
                    for key in ('product', 'round', 'correct', 'status', 'error', 'originalError', 'cleanupErrors',
                                'rawReportPath', 'rawReportSha256', 'sampleReturncode', 'recoveryMetadata', 'isolatedImageRetained'):
                        if key in row:
                            audit[key] = row[key]
                    round_ = index // 2
                    order = PRODUCTS[::-1] if (mode + round_) % 2 else PRODUCTS
                    require(index < 4 and type(row.get('round')) is int and row['round'] == round_
                            and row.get('product') == order[index % 2]
                            and type(row.get('incremental')) is int and row['incremental'] == mode, 'record identity/order mismatch')
                    require(row.get('correct') is True and row.get('status') == 'passed'
                            and type(row.get('sampleReturncode')) is int and row['sampleReturncode'] == 0
                            and not row.get('cleanupErrors') and not row.get('error'), 'record failed or cleanup blocked')
                    require(fixture is not None, 'report identity/fixture not validated')
                    validate_admission(row, report)
                    product = report['directManifest']['sprig' if row['product'] == 'sprig-writable' else 'layerfs']
                    require(row.get('verifiedProductInputs') == product, 'verified product inputs differ from frozen manifest')
                    name = f"stress-cargo-{row['product']}-inc{mode}-{round_}.json"
                    require(row.get('rawReportPath') == 'results/' + name, 'raw path differs from fixed sample name')
                    raw = read_regular(path.parent / name)
                    require(isinstance(row.get('rawReportSha256'), str) and digest(raw) == row['rawReportSha256'],
                            'standalone raw report hash mismatch')
                    sample = strict_json(raw)
                    if row['product'] == 'sprig-writable':
                        validation_report = {**report, 'experimentSpec': {'profile': 'ordinary'}}
                        count = validate_sprig_sample(sample, validation_report, {**product, 'label': 'sprig-writable'}, mode, round_, archive_root)
                        contents = verify_archives(sample, archive_root, mode, 'sprig-writable', round_)
                        verify_common_evidence(sample, report, fixture, contents, layerfs=False)
                        checkpoint = sample.get('checkpoint', {})
                        require(checkpoint.get('committed') is True and checkpoint.get('revision') == sample.get('restoredRevision')
                                and isinstance(sample.get('restoredRevision'), str) and HEX64.fullmatch(sample['restoredRevision']),
                                'Sprig acknowledged checkpoint/restore identity differs')
                    else:
                        count = validate_layerfs_sample(sample, report, product, mode, round_, archive_root, fixture)
                    audit['archivedFilesVerified'] = count
                    embedded = row.get('sample')
                    require(isinstance(embedded, dict), 'embedded sample missing')
                    keys = ('ok', 'incremental', 'production_sha', 'image', 'protocolSha256', 'phase_seconds', 'full_task_seconds',
                            'fullRestoredTreeVerified', 'originalMainViewUnchanged', 'sourceUnchanged', 'allAcknowledgedIdsPresent')
                    if row['product'] == 'sprig-writable':
                        keys += ('binarySha256', 'convenience_seconds')
                    for key in keys:
                        require(embedded.get(key) == sample.get(key), 'embedded/raw safe field differs: ' + key)
                    metrics = {'wholeSamplerSeconds': finite(row.get('wholeSampleSubprocessWallSeconds'), 'whole sampler wall', True),
                               'runtimeSetupSeconds': finite(row.get('runtimeSetupSeconds'), 'runtime setup'),
                               'fullTaskSeconds': sample['full_task_seconds'],
                               'wholeFilesystemUsedBytes': sample['activeSpace']['filesystemUsedBytes']}
                    for group, prefix in (('phase_seconds', 'phase.'), ('convenience_seconds', 'convenience.')):
                        values = sample.get(group, {})
                        require(isinstance(values, dict), 'invalid metric group')
                        for key, value in values.items():
                            metrics[prefix + key] = finite(value, prefix + key)
                    if row['product'] == 'layerfs':
                        require(not sample.get('convenience_seconds'), 'unmatched Sprig composites fabricated for LayerFS')
                    audit['metrics'] = metrics
                    audit['validated'] = True
                except ERRORS as error:
                    audit['validationError'] = str(error)
                    result['errors'].append(f'{path} record{index}: {error}')
        recorded = {(row.get('round'), row.get('product')) for row in rows
                    if isinstance(row, dict) and type(row.get('round')) is int and isinstance(row.get('product'), str)}
        for index in range(4):
            round_ = index // 2
            order = PRODUCTS[::-1] if (mode + round_) % 2 else PRODUCTS
            if (round_, order[index % 2]) not in recorded:
                result['missingRecords'].append({'incremental': mode, 'round': round_, 'product': order[index % 2],
                                                 'index': index, 'attempted': False, 'status': 'not_recorded'})
    if not result['errors'] and len(result['records']) == 8 and not result['missingRecords']:
        try:
            compared, unmatched, negatives = {}, {}, {}
            for mode in (0, 1):
                compared[f'inc{mode}'], unmatched[f'inc{mode}'], negatives[f'inc{mode}'] = compare_mode(
                    [r for r in result['records'] if r['incremental'] == mode])
            result.update(complete=True, status='passed', comparisons=compared, unmatchedMetrics=unmatched,
                          slowerOrLargerPairs=negatives, identity={key: loaded[0][1][key] for key in IDENTITY})
        except ERRORS as error:
            result['errors'].append('statistics blocked: ' + str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inc0', required=True, type=Path)
    parser.add_argument('--inc1', required=True, type=Path)
    parser.add_argument('--archive-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = summarize([args.inc0, args.inc1], args.archive_root)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'complete': result['complete'], 'status': result['status'],
                      'records': len(result['records']), 'missingRecords': len(result['missingRecords']), 'errors': result['errors']}))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
