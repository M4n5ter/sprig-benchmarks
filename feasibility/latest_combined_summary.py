#!/usr/bin/env python3
"""Fail-closed, read-only audit of the fixed current-main Native smoke4 series.

No products, subprocesses, mounts or workload files are created by this reader.
Raw JSON (including exact integers) and complete archived streams are authoritative.
The embedded JavaScript sample is deliberately not used as measurement evidence.
"""
from __future__ import annotations

import argparse
import base64
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys

SCHEMA = 'sprig-latest-combined-native-smoke-v1'
SUMMARY_SCHEMA = 'sprig-latest-combined-native-summary-v1'
IDENTITY_SCHEMA = 'sprig-latest-combined-native-identity-v1'
FIXTURE_SCHEMA = 'sprig-latest-combined-fixtures-v1'
PINS = {'sprig-native': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
        'layerfs': 'ad78914e36b258b360daf13aec164b5655814689'}
CASES = ('identical', 'history-distributed')
ORDER = tuple((product + '-' + case, product, case) for case in CASES for product in PINS)
IMAGE_BYTES, ARTIFACT_BYTES = 2 * 1024**3, 1024**3
REPORT_RESERVE, MANIFEST_RESERVE = 256 * 1024**2, 2 * 1024**2
RAW_LIMIT, DRIVER_LIMIT, STREAM_LIMIT = 16 * 1024**2, 64 * 1024**2, 2 * 1024**2
HEX = re.compile(r'[a-f0-9]{64}\Z')
SAFE = re.compile(r'[A-Za-z0-9_.-]+\Z')
ERRORS = (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError,
          OverflowError, UnicodeError, StopIteration)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, label, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum and (maximum is None or value <= maximum),
            'invalid integer ' + label)
    return value


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'invalid finite nonnegative timing/number ' + label)
    return value


def digest(value):
    return hashlib.sha256(value).hexdigest()


def hash_value(value, label):
    require(isinstance(value, str) and HEX.fullmatch(value), 'invalid SHA256 ' + label)
    return value


def absolute(value, label):
    require(isinstance(value, str) and value.startswith('/') and '\0' not in value
            and os.path.normpath(value) == value and not value.startswith('//'),
            'noncanonical absolute path ' + label)
    return Path(value)


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def checked(path, directory=False):
    path = Path(path).absolute()
    require(path.resolve(strict=True) == path, 'symlink or noncanonical evidence path: ' + str(path))
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            'evidence must be independent regular file/directory: ' + str(path))
    return info


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def read_evidence(path, limit=RAW_LIMIT, retain=True):
    """Bounded streaming hash, no following links, and before/after identity checks."""
    path = Path(path).absolute()
    before = checked(path)
    require(before.st_size <= limit, 'evidence exceeds acceptance cap: ' + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    parts, size, hashed = [], 0, hashlib.sha256()
    with os.fdopen(fd, 'rb') as stream:
        require(stamp(os.fstat(stream.fileno())) == stamp(before), 'evidence replaced on open')
        while size < before.st_size:
            block = stream.read(min(1024**2, before.st_size - size))
            require(block, 'evidence shortened during read')
            hashed.update(block)
            size += len(block)
            if retain:
                parts.append(block)
        require(not stream.read(1) and stamp(os.fstat(stream.fileno())) == stamp(before),
                'evidence mutated during read')
    require(stamp(checked(path)) == stamp(before), 'evidence changed after read')
    return b''.join(parts) if retain else None, hashed.hexdigest(), size


def read_json(path, limit=RAW_LIMIT):
    body, sha, size = read_evidence(path, limit)
    return strict_json(body), sha, size


def framed(value):
    body = value.encode()
    return struct.pack('<Q', len(body)) + body


def splitmix(seed, count):
    out, mask = bytearray(), 2**64 - 1
    while len(out) < count:
        seed = (seed + 0x9e3779b97f4a7c15) & mask
        value = ((seed ^ (seed >> 30)) * 0xbf58476d1ce4e5b9) & mask
        value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & mask
        out.extend(struct.pack('<Q', value ^ (value >> 31)))
    return bytes(out[:count])


def frozen_content(family, profile, ordinal, role, count):
    seed = hashlib.sha256(b''.join(framed(s) for s in
        ('dedup-input-v1', family, profile, 'layerfs-v0.1.3-seed-1'))
        + struct.pack('<Q', ordinal) + framed(role)).digest()
    return splitmix(int.from_bytes(seed[:8], 'little'), count)


@lru_cache(maxsize=2)
def frozen_fixture(case):
    """Reconstruct only small in-memory recipe bytes; never materialize a workload."""
    require(case in CASES, 'unknown frozen case')
    if case == 'identical':
        sha = digest(frozen_content('dedup_cross_file', 'base', 0, 'bytes', 1048576))
        return ([{'path': f'files/f{i:04}.dat', 'bytes': 1048576, 'sha256': sha} for i in range(100)], [])
    genesis, names = {}, []
    for i in range(200):
        name = (f'wide/s000-f{i:03}.dat' if i < 64 else f'regular/s000/f{i:03}.dat' if i < 199
                else 'spine/' + '/'.join(f'd{j:03}' for j in range(1, 129)) + '/s000.dat')
        names.append(name)
        seed = hashlib.sha256(framed('workspace-shards-v1') + framed('layerfs-v0.1.3-seed-1')
                              + struct.pack('<QQ', 0, i)).digest()
        genesis[name] = splitmix(int.from_bytes(seed[:8], 'little'), 1024 if i < 128 else 8192 if i < 192 else 49152)
    oracle = [{'path': name, 'bytes': len(body), 'sha256': digest(body)} for name, body in sorted(genesis.items())]
    prefix = framed('layerfs-v0.1.3-seed-1') + framed('dedup-history-distributed')
    rank = [i for _, i in sorted((hashlib.sha256(prefix + struct.pack('<Q', i)).digest(), i) for i in range(200))]
    steps = []
    for index, i in enumerate(rank[:100]):
        name, original = names[i], genesis[names[i]]
        data = frozen_content('dedup_branch_history', 'distributed', index, 'replacement', 64)
        offset = len(original) // 2 - 32
        steps.append({'step': index + 1, 'path': name, 'offset': offset,
                      'data': base64.b64encode(data).decode(),
                      'sha256': digest(original[:offset] + data + original[offset + 64:])})
    return oracle, steps


def exact_json(left, right):
    """Avoid Python's True == 1 when enforcing integer evidence contracts."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(exact_json(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact_json(a, b) for a, b in zip(left, right))
    return left == right


def validate_identity(value):
    require(isinstance(value, dict) and set(value) == {'schema', 'sprig', 'layerfs'}
            and value['schema'] == IDENTITY_SCHEMA, 'identity schema/fields differ')
    common = {'sha', 'ref', 'binary', 'binarySha256', 'sourcePath'}
    for name, product in (('sprig', 'sprig-native'), ('layerfs', 'layerfs')):
        item = value[name]
        extra = {'sdkPath', 'sdkSha256', 'nativeAddonPath', 'nativeAddonSha256'} if name == 'layerfs' else set()
        require(isinstance(item, dict) and set(item) == common | extra, 'product identity fields differ')
        require(item['sha'] == PINS[product] and item['ref'] == 'main', 'fixed current-main pin differs')
        source = absolute(item['sourcePath'], 'source checkout')
        suffix = 'target/release/sprig' if name == 'sprig' else 'core/target/release/layerfs-daemon'
        require(absolute(item['binary'], 'binary') == source / suffix, 'wrong built executable path')
        hash_value(item['binarySha256'], 'binary')
        if name == 'layerfs':
            for key, suffix in (('sdkPath', 'api/agent/sdk/src/index.js'), ('nativeAddonPath', 'api/binding/layerfs.node')):
                require(absolute(item[key], key) == source / suffix, 'wrong fixed SDK/addon path')
            hash_value(item['sdkSha256'], 'sdk'); hash_value(item['nativeAddonSha256'], 'addon')
    require(value['sprig']['sourcePath'] != value['layerfs']['sourcePath']
            and value['sprig']['binarySha256'] != value['layerfs']['binarySha256'], 'products not independently identified')


def validate_inputs(report, results):
    require(report.get('schema') == SCHEMA and report.get('backend') == 'native'
            and report.get('mode') == 'smoke', 'requires separate Native smoke schema/mode')
    require(integer(report.get('rounds'), 'rounds') == 1 and integer(report.get('expectedRecords'), 'expected records') == 4,
            'requires exactly one fixed pair per case / four records')
    require(report.get('productionSha') == PINS['sprig-native'] and report.get('comparatorSha') == PINS['layerfs'], 'driver pins differ')
    require(integer(report.get('imageBytes'), 'imageBytes') == IMAGE_BYTES, 'only symmetric 2GiB images allowed')
    require(isinstance(report.get('image'), str) and re.fullmatch(r'sha256:[a-f0-9]{64}', report['image']), 'immutable image ID missing')
    identity, sha, _ = read_json(results / 'latest-combined-identity.json')
    validate_identity(identity)
    require(sha == report.get('identitySha256') and exact_json(identity, report.get('identity')), 'identity bytes/embedded manifest binding differs')
    manifest, sha, _ = read_json(results / 'latest-combined-fixtures.json')
    require(sha == report.get('fixtureManifestSha256') and exact_json(manifest, report.get('fixtureManifest')), 'fixture manifest bytes binding differs')
    require(isinstance(manifest, dict) and set(manifest) == {'schema', 'cases'}
            and manifest['schema'] == FIXTURE_SCHEMA and isinstance(manifest['cases'], list)
            and len(manifest['cases']) == 2, 'fixture manifest schema/count differs')
    fixtures = {}
    for case, entry in zip(CASES, manifest['cases']):
        keys = {'case', 'sourcePath', 'oraclePath', 'oracleSha256'} | ({'stepsPath', 'stepsSha256', 'finalPath', 'finalSha256'} if case == 'history-distributed' else set())
        require(isinstance(entry, dict) and set(entry) == keys and entry['case'] == case, 'fixture manifest fields/order differ')
        absolute(entry['sourcePath'], 'fixture source'); absolute(entry['oraclePath'], 'oracle path')
        oracle, oracle_sha, _ = read_json(results / ('latest-combined-' + case + '-oracle.json'))
        require(oracle_sha == hash_value(entry['oracleSha256'], 'oracle'), 'copied oracle actual bytes differ')
        steps = []
        if case == 'history-distributed':
            absolute(entry['stepsPath'], 'steps path')
            steps, step_sha, _ = read_json(results / 'latest-combined-history-distributed-steps.json')
            require(step_sha == hash_value(entry['stepsSha256'], 'steps'), 'copied recipe actual bytes differ')
        expected_oracle, expected_steps = frozen_fixture(case)
        require(exact_json(oracle, expected_oracle) and exact_json(steps, expected_steps), 'frozen seed-1 listed-byte/history recipe differs')
        if case == 'history-distributed':
            absolute(entry['finalPath'], 'final oracle path')
            require(entry['finalPath'] == entry['stepsPath'].removesuffix('-steps.json') + '-final.json', 'frozen steps/final sibling derivation differs')
            final, final_sha, _ = read_json(results / 'latest-combined-history-distributed-final.json')
            expected_final = {row['path']: dict(row) for row in expected_oracle}
            for step in expected_steps:
                expected_final[step['path']]['sha256'] = step['sha256']
            require(final_sha == hash_value(entry['finalSha256'], 'final oracle')
                    and exact_json(final, list(expected_final.values())), 'frozen copied final oracle bytes/hash differ')
        fixtures[case] = (entry, oracle, steps)
    require(manifest['cases'][0]['sourcePath'] != manifest['cases'][1]['sourcePath'], 'fixture sources must be distinct')
    budget = report.get('sharedJobBudget', {})
    start = number(budget.get('startedEpochSeconds'), 'job start')
    end = number(budget.get('deadlineEpochSeconds'), 'job deadline')
    require(0 < end - start <= 2400 and integer(budget.get('minimumSampleSeconds'), 'sample reserve') == 180
            and integer(budget.get('cleanupReserveSeconds'), 'cleanup reserve') == 300, '40min shared deadline/reserves differ')
    require(exact_json(report.get('limits'), {'artifactBytes': ARTIFACT_BYTES, 'pendingReportReserveBytes': REPORT_RESERVE,
                                            'collectionManifestReserveBytes': MANIFEST_RESERVE}), 'artifact allowance policy differs')
    return identity, fixtures


def validate_budget(record, budget):
    previous = None
    for key in ('budgetAdmission', 'postRuntimeBudgetAdmission'):
        row = record.get(key, {})
        require(row.get('admitted') is True and row.get('startedEpochSeconds') == budget['startedEpochSeconds']
                and row.get('deadlineEpochSeconds') == budget['deadlineEpochSeconds'], 'missing/shared pre-runtime budget admission')
        work = number(row.get('workReserveSeconds'), key + ' work')
        cleanup = number(row.get('cleanupReserveSeconds'), key + ' cleanup')
        remaining = number(row.get('remainingSeconds'), key + ' remaining')
        require(work >= 180 and cleanup >= 300 and number(row.get('requiredSeconds'), key + ' required') == work + cleanup
                and remaining >= work + cleanup and remaining <= budget['deadlineEpochSeconds'] - budget['startedEpochSeconds'], 'invalid admission reserves/remaining budget')
        require(previous is None or remaining <= previous, 'budget increased after runtime setup')
        previous = remaining
    before = integer(record.get('preSampleArtifactInventory', {}).get('bytes'), 'pre-sample artifact bytes')
    allowance = integer(record.get('archiveAllowanceBytes'), 'archive allowance', 1, ARTIFACT_BYTES)
    require(allowance == ARTIFACT_BYTES - before - REPORT_RESERVE - MANIFEST_RESERVE, 'archive allowance not from complete inventory/reserves')
    final = integer(record.get('finalArtifactInventory', {}).get('bytes'), 'final artifact bytes')
    require(final + MANIFEST_RESERVE <= ARTIFACT_BYTES, 'artifact cap exceeded')
    host = record.get('hostAdmission', {})
    required = IMAGE_BYTES + ARTIFACT_BYTES + 512 * 1024**2
    require(integer(host.get('requiredBytes'), 'host reserve') == required
            and integer(host.get('availableBytes'), 'host free bytes') >= required, 'host admission insufficient')


def validate_space(value, label, device=False):
    require(isinstance(value, dict), 'missing ' + label)
    used = integer(value.get('filesystemUsedBytes'), label + ' Used', 0, IMAGE_BYTES)
    raw = value.get('usageRaw')
    require(isinstance(raw, str), 'missing whole-filesystem usage output')
    matches = re.findall(r'^\s*Used:\s*(\d+)\s*$', raw, re.M)
    require(len(matches) == 1 and int(matches[0]) == used, 'Used differs from complete usage output')
    require(isinstance(value.get('groupsRaw'), str) and value['groupsRaw'], 'missing data/metadata/system group evidence')
    if device:
        sizes = re.findall(r'^\s*Device size:\s*(\d+)\s*$', raw, re.M)
        require(integer(value.get('deviceBytes'), label + ' device') == IMAGE_BYTES and len(sizes) == 1
                and int(sizes[0]) == IMAGE_BYTES, 'outer measured filesystem not exactly 2GiB')
    return used


def verify_archives(sample, record, archive_root):
    root = absolute(sample.get('root'), 'sample root')
    ledger = absolute(sample.get('recordsFile'), 'records file')
    require(ledger.name == record['id'] + '.jsonl' and ledger.parent.name == 'latest-combined-records', 'records parent/id binding differs')
    require(sample.get('recordsIncludedInActiveSpace') is False, 'external ledger accounting differs')
    original_dir = Path(str(ledger) + '.logs')
    actual_dir = Path(archive_root) / original_dir.name
    checked(actual_dir, directory=True)
    rows = sample.get('completeLogArchive')
    require(isinstance(rows, list) and rows, 'complete log archive absent')
    require(not sample.get('partialLogArchive'), 'partial archive cannot be accepted')
    names, sources, contents, total = set(), set(), {}, 0
    previous_source = None
    for index, row in enumerate(rows):
        require(isinstance(row, dict) and set(row) == {'source', 'archived', 'bytes', 'sha256'}, 'invalid archive entry fields')
        source = absolute(row['source'], 'log source')
        archived = absolute(row['archived'], 'original archive')
        require(archived.parent == original_dir and archived.name not in names and str(source) not in sources,
                'archive source/destination duplicate or wrong parent')
        require(previous_source is None or str(source) > previous_source, 'archive source order differs')
        previous_source = str(source)
        if record['product'] == 'sprig-native':
            require(archived.name == f'{index:06}-' + source.name, 'Native archive filename/index differs')
            allowed = (source == ledger or source.parent == root / 'logs' and
                       (re.fullmatch(r'command-[0-9]{6}-(?:stdout|stderr)\.log', source.name) or source.name == 'lifecycle.jsonl'))
            require(allowed, 'Native source outside exact owned log/ledger scope')
        else:
            require(source.parent == root / 'logs' and archived.name == source.name
                    and re.fullmatch(r'(?:[0-9]{5}-[A-Za-z0-9_.-]+\.(?:stdout|stderr)|lifecycle\.jsonl)', source.name),
                    'LayerFS source outside exact owned log scope/name')
        size = integer(row['bytes'], 'archive bytes', 0, 64 * 1024**2)
        _, sha, actual_size = read_evidence(actual_dir / archived.name, 64 * 1024**2, retain=False)
        require(sha == hash_value(row['sha256'], 'archive') and size == actual_size, 'archive actual size/hash mismatch')
        names.add(archived.name); sources.add(str(source)); total += size
        contents[str(source)] = (actual_dir / archived.name, row)
    require({p.name for p in actual_dir.iterdir()} == names, 'archive set has extra/missing files')
    require(str(root / 'logs' / 'lifecycle.jsonl') in sources, 'complete lifecycle stream missing')
    if record['product'] == 'sprig-native':
        require(str(ledger) in sources, 'complete Native checkpoint ledger missing')
        require(contents[str(ledger)][1]['bytes'] <= 8 * 1024**2
                and total - contents[str(ledger)][1]['bytes'] <= 64 * 1024**2, 'Native source/ledger acceptance cap exceeded')
    admission, copy = sample.get('archiveAdmission', {}), sample.get('archiveCopy', {})
    require(admission.get('admitted') is True and integer(admission.get('allowanceBytes'), 'sample allowance') == record['archiveAllowanceBytes']
            and integer(admission.get('plannedBytes'), 'archive planned bytes') == total <= record['archiveAllowanceBytes'], 'full archive plan/admission differs')
    require(copy.get('complete') is True and copy.get('sourceFilesRetained') is True
            and integer(copy.get('completedFiles'), 'completed archive files') == len(rows), 'full archive copy unconfirmed')
    if record['product'] == 'sprig-native':
        require(integer(admission.get('plannedFiles'), 'planned files') == len(rows)
                and integer(copy.get('copiedBytes'), 'copied bytes') == total and copy.get('destination') == str(original_dir)
                and sample.get('sourceFilesRetained') is True, 'Native full plan/copy bytes differ')
    else:
        planned = admission.get('plannedFiles')
        require(isinstance(planned, list) and len(planned) == len(rows), 'LayerFS planned archive list incomplete')
        for planned_row, row in zip(planned, rows):
            require(all(exact_json(planned_row.get(k), row[k]) for k in ('source', 'archived', 'bytes')), 'LayerFS plan/copy entry differs')
        require(integer(sample.get('sourceLogBytes'), 'source log bytes') == total <= 64 * 1024**2
                and integer(sample.get('externalLedgerBytes'), 'ledger bytes') <= 8 * 1024**2, 'LayerFS source/ledger acceptance cap differs')
    return contents


class Commands:
    def __init__(self, sample, record, contents):
        self.rows = sample.get('commands')
        require(isinstance(self.rows, list) and self.rows, 'complete raw command rows missing')
        self.outputs = {}
        all_paths = set()
        root = Path(sample['root'])
        for index, row in enumerate(self.rows, 1):
            require(isinstance(row, dict) and integer(row.get('sequence'), 'command sequence') == index
                    and integer(row.get('returncode'), 'command returncode') == 0, 'failed/duplicate/noncontiguous command')
            if record['product'] == 'sprig-native':
                require(row.get('outcomeKnown') is True and row.get('withinAcceptanceLimits') is True, 'unknown Native command outcome')
            else:
                require(row.get('signal') is None and isinstance(row.get('purpose'), str), 'LayerFS command signal/purpose invalid')
            for stream in ('stdout', 'stderr'):
                source = str(absolute(row.get(stream + 'Path'), 'command stream'))
                require(source in contents and source not in all_paths and Path(source).parent == root / 'logs', 'command stream not uniquely bound to complete archive')
                expected = (f'command-{index:06}-{stream}.log' if record['product'] == 'sprig-native' else
                            f'{index:05}-' + re.sub(r'[^A-Za-z0-9_.-]', '_', row['purpose']) + '.' + stream)
                require(Path(source).name == expected, 'command stream filename differs from sequence/purpose')
                path, archive = contents[source]
                require(integer(row.get(stream + 'Bytes'), 'command bytes', 0, STREAM_LIMIT) == archive['bytes']
                        and hash_value(row.get(stream + 'Sha256'), 'command stream') == archive['sha256'], 'command/archive hash/bytes binding differs')
                body, _, _ = read_evidence(path, STREAM_LIMIT)
                self.outputs[(index, stream)] = body.decode('utf-8', errors='strict')
                all_paths.add(source)
        archived_commands = {p for p in contents if Path(p).parent == root / 'logs' and Path(p).name != 'lifecycle.jsonl'}
        require(all_paths == archived_commands, 'archive contains unreported command streams')

    def stdout(self, row):
        return self.outputs[(row['sequence'], 'stdout')]

    def one(self, predicate, label):
        found = [row for row in self.rows if predicate(row)]
        require(len(found) == 1, 'missing/duplicate command evidence: ' + label)
        return found[0]

    def checks(self, row, oracle):
        require(self.stdout(row) == ''.join(item['path'] + ': OK\n' for item in oracle), 'complete listed-file readback output differs')
        require(self.outputs[(row['sequence'], 'stderr')] == '', 'unexpected checksum stderr')


def checksum(oracle):
    return '(' + ';'.join("printf '%s  %s\\n' '" + row['sha256'] + "' '" + row['path'] + "'" for row in oracle) + ') | sha256sum -c -'


def changed(step):
    return "printf '%s  %s\\n' '" + step['sha256'] + "' '" + step['path'] + "' | sha256sum -c -"


def writer(step):
    return ("set -e; printf '%s' '" + step['data'] + "' | base64 -d | dd of='" + step['path']
            + "' bs=65536 iflag=fullblock oflag=seek_bytes seek=" + str(step['offset'])
            + " conv=notrunc,fsync status=none; touch -d @1700000000 '" + step['path'] + "'")


def close_sum(total, values, label):
    require(math.isclose(number(total, label), sum(number(v, label + ' component') for v in values),
                         rel_tol=1e-9, abs_tol=1e-9), 'timing sum mismatch: ' + label)


def boundary(sample, product, count):
    lifecycle = sample.get('lifecycle', {})
    active = lifecycle.get('activeAtSpace', {})
    post = lifecycle.get('activeAfterHistory', {}) if product == 'sprig-native' else sample.get('postHistoryBoundary', {})
    names = {'main', 'work', 'second'} if product == 'sprig-native' else {'import-main', 'work', 'second'}
    found = []
    for stage, expected_count in ((active, 0), (post, count)):
        views = stage.get('views')
        require(isinstance(views, list) and len(views) == 3 and {v.get('name') for v in views} == names
                and len({v.get('path') for v in views}) == 3, 'three distinct original live views missing')
        require(stage.get('historicalReadbacksStarted') is (expected_count > 0)
                and integer(stage.get('historicalReadbacksCompleted'), 'boundary readback count') == expected_count
                and stage.get('fileTreesRetained') is True and stage.get('allRuntimeLogsAndJournalsInsideMeasuredStore') is True,
                'active/post-history boundary scope differs')
        if product == 'sprig-native':
            require(integer(stage.get('controlProcessesRunning'), 'Native daemons') == 0
                    and stage.get('foregroundFuseProcesses') == []
                    and exact_json(stage.get('retainedGenerations'), {'projection': [], 'writable': []}), 'unexpected Native FUSE generation/process')
            for view in views:
                require(isinstance(view.get('generation'), str) and SAFE.fullmatch(view['generation'])
                        and view['path'] == str(Path(sample['root']) / 'library/native' / view['generation'] / 'tree')
                        and view.get('backend', {}).get('kind') == 'native', 'Native view binding differs')
                hash_value(view.get('base_revision'), 'view revision')
        else:
            require(integer(stage.get('controlProcessesRunning'), 'LayerFS control process') == 1, 'missing live LayerFS control process')
            workspaces = stage.get('workspaces')
            require(isinstance(workspaces, list) and len(workspaces) == 3 and all(any(
                w.get('path') == v['path'] and w.get('activity') == 'Idle' for w in workspaces) for v in views), 'live LayerFS workspace inventory differs')
            require(isinstance(stage.get('sandboxes'), list) and len(stage['sandboxes']) == 1
                    and stage['sandboxes'][0].get('workspaces') == 3
                    and all(v.get('sandbox') == stage['sandboxes'][0].get('sandbox') for v in views), 'live sandbox identity differs')
        found.append({view['name']: view for view in views})
    require(post.get('historicalReadbacksComplete') is True and exact_json(found[0], found[1]), 'original live views moved across readbacks')
    if product == 'sprig-native':
        generations = post.get('generationDirectories')
        require(isinstance(generations, list) and len(generations) == 3 + count
                and all(isinstance(g, str) and SAFE.fullmatch(g) for g in generations)
                and generations == sorted(set(generations))
                and integer(post.get('retainedGenerationCount'), 'retained Native generations') == 3 + count
                and {v['generation'] for v in found[1].values()}.issubset(generations), 'Native retained 3/103 generation directories differ')
    return found[0], post


def native_evidence(sample, commands, oracle, steps, views, post):
    prefix = [sample['binary'], '--store', str(Path(sample['root']) / 'library'), '--json']
    def cli(action, *args):
        row = commands.one(lambda r: r.get('argv') == prefix + [action, *args], 'Native ' + action + ' ' + ' '.join(args))
        value = strict_json(commands.stdout(row))
        require(isinstance(value, dict) and integer(value.get('schema_version'), 'CLI schema') == 1
                and 'result' in value and 'error' not in value, 'invalid successful CLI result')
        return row, value['result']
    def shell(path, command, label):
        return commands.one(lambda r: r.get('argv') == ['bash', '-c', command] and r.get('cwd') == path, label)
    initial = hash_value(sample.get('initialHead'), 'initial Native revision')
    require(views['main']['base_revision'] == views['second']['base_revision'] == initial, 'original branch revision moved')
    cli('init')
    _, imported = cli('import', sample['source'], 'main')
    require(imported.get('base_revision') == initial and imported.get('path') == views['main']['path'], 'import does not bind original main')
    for name in ('work', 'second'):
        _, fork = cli('fork', 'main', name)
        require(fork.get('base_revision') == initial and fork.get('path') == views[name]['path'], 'fork source/path differs')
    for name in ('main', 'second', 'work'):
        reads = [r for r in commands.rows if r.get('argv') == ['bash', '-c', checksum(oracle)] and r.get('cwd') == views[name]['path']]
        require(len(reads) == (2 if name == 'second' else 1), 'original/warm Native full read count differs: ' + name)
        for read in reads:
            commands.checks(read, oracle)
    commands.checks(shell(sample['source'], checksum(oracle), 'unchanged source read'), oracle)
    rows, restores = sample.get('checkpoint_steps'), sample.get('historical_restore_steps')
    require(isinstance(rows, list) and isinstance(restores, list) and len(rows) == len(restores) == len(steps)
            and integer(sample.get('history_distinct_revisions'), 'distinct Native revisions') == len(steps), 'Native history/restore row count differs')
    current = {item['path']: dict(item) for item in oracle}
    previous, ids, generations, last_seq = initial, [], [], 0
    for step, row, restore in zip(steps, rows, restores):
        n = step['step']; revision = hash_value(row.get('revision'), 'checkpoint revision')
        require(integer(row.get('step'), 'checkpoint step') == n and revision not in [initial, *ids]
                and row.get('base') == previous and row.get('changedFileReadback') is True, 'Native checkpoint chain/readback differs')
        write = shell(views['work']['path'], writer(step), 'frozen history writer')
        ack, checkpoint = cli('checkpoint', 'work', '--expected-head', previous, '--message', 'Frozen history step ' + str(n))
        require(exact_json(checkpoint, row.get('checkpoint')) and checkpoint.get('committed') is True
                and checkpoint.get('branch') == 'work' and checkpoint.get('previous_head') == previous
                and checkpoint.get('revision') == revision, 'Native acknowledged checkpoint output differs')
        read = shell(views['work']['path'], changed(step), 'changed file read')
        commands.checks(read, [step])
        require(last_seq < write['sequence'] < ack['sequence'] < read['sequence'], 'Native write/checkpoint/read order differs')
        last_seq = read['sequence']
        require(row.get('generation_before') == row.get('generation_after') == views['work']['generation']
                and row.get('workspace_path_after') == views['work']['path'], 'Native checkpoint changed original generation')
        close_sum(row.get('checkpoint_seconds'), [row.get('checkpoint_cli_seconds'), row.get('checkpoint_ready_seconds')], 'checkpoint phases')
        require(number(row.get('checkpoint_ready_seconds'), 'Native ready seconds') == 0, 'Native readiness scope changed')
        number(row.get('write_seconds'), 'history write seconds')
        restore_command, restored = cli('restore', revision, 'history-%03d' % n)
        generation = restore.get('generation')
        require(integer(restore.get('step'), 'restore step') == n and restore.get('revision') == revision
                and isinstance(generation, str) and SAFE.fullmatch(generation) and generation not in generations
                and generation not in {v['generation'] for v in views.values()} and generation in post['generationDirectories']
                and restore.get('cleanup_operation') == 'none; native tree retained', 'Native historical restore/generation retention differs')
        path = str(Path(sample['root']) / 'library/native' / generation / 'tree')
        require(restored.get('path') == path and restored.get('base_revision') == revision, 'Native restore command returned wrong historical snapshot')
        current[step['path']]['sha256'] = step['sha256']
        historical_read = shell(path, checksum(list(current.values())), 'historical full listed read')
        commands.checks(historical_read, list(current.values()))
        require(restore_command['sequence'] < historical_read['sequence'], 'historical read before restore')
        require(number(restore.get('restore_cleanup_seconds'), 'Native restore cleanup') == 0, 'Native retained tree cleanup is not zero')
        number(restore.get('restore_seconds'), 'Native restore'); number(restore.get('restore_read_seconds'), 'Native historical read')
        ids.append(revision); generations.append(generation); previous = revision
    logs = [r for r in commands.rows if r.get('argv') == prefix + ['log', 'work']]
    require(len(logs) == (2 if steps else 1), 'Native exact baseline/final history count differs')
    for log, chain in ((logs[-1], list(reversed(ids)) + [initial]), *([(logs[0], [initial])] if steps else [])):
        response = strict_json(commands.stdout(log))
        require(response.get('schema_version') == 1 and 'error' not in response, 'invalid Native log result')
        history = response.get('result')
        require(isinstance(history, list) and [r.get('revision') for r in history] == chain
                and all(row.get('parents') == chain[i + 1:i + 2] for i, row in enumerate(history)), 'exact acknowledged history/parents missing')
    if steps:
        commands.checks(shell(views['work']['path'], checksum(list(current.values())), 'final work read'), list(current.values()))
    require(views['work']['base_revision'] == previous, 'active work view not at final acknowledged Native revision')
    _, listing = cli('list')
    require(listing.get('branches', {}).get('main') == listing.get('branches', {}).get('second') == initial, 'original branch names moved')
    for key, row_key in (('write_seconds', 'write_seconds'), ('checkpoint_seconds', 'checkpoint_seconds')):
        close_sum(sample.get(key), [r.get(row_key) for r in rows], key)
    for key in ('restore_seconds', 'restore_read_seconds', 'restore_cleanup_seconds'):
        close_sum(sample.get(key), [r.get(key) for r in restores], key)


def layerfs_evidence(sample, commands, oracle, steps, views):
    def by_purpose(purpose, command=None, path=None):
        row = commands.one(lambda r: r.get('purpose') == purpose, purpose)
        if command is not None:
            require(row.get('command') == command and row.get('workspace', {}).get('path') == path, 'LayerFS frozen command/workspace differs: ' + purpose)
        return row
    for purpose, name in (('first_full_read', 'work'), ('warm_full_read', 'second'), ('main_unchanged', 'import-main'), ('second_unchanged', 'second')):
        commands.checks(by_purpose(purpose, checksum(oracle), views[name]['path']), oracle)
    source = by_purpose('source_unchanged')
    require(source.get('argv') == ['bash', '-c', checksum(oracle)] and source.get('cwd') == sample['source'], 'LayerFS original source read binding differs')
    commands.checks(source, oracle)
    sdk = sample.get('sdkOperations')
    require(isinstance(sdk, list) and sdk and all(isinstance(row, dict) and 'operation' in row and 'result' in row for row in sdk), 'complete LayerFS SDK operations missing')
    commits = [r['result'] for r in sdk if r['operation'] == 'workspace.commit']
    history = sample.get('historyCheck')
    rows = history.get('samples') if isinstance(history, dict) else []
    restores = sample.get('historicalRestoreSamples')
    require(isinstance(rows, list) and isinstance(restores, list) and len(rows) == len(restores) == len(commits) == len(steps), 'LayerFS acknowledged/restore history count differs')
    current, ids, paths = {item['path']: dict(item) for item in oracle}, [], []
    last_write = 0
    for step, row, restore, commit in zip(steps, rows, restores, commits):
        n = step['step']; revision = row.get('commitId')
        require(isinstance(revision, str) and re.fullmatch(r'12[a-f0-9]{64}', revision) and revision not in ids
                and integer(row.get('step'), 'LayerFS checkpoint step') == n and exact_json(row.get('commit'), commit)
                and commit.get('kind') == 'Committed' and commit.get('head') == commit.get('commit', {}).get('id') == revision,
                'distinct acknowledged LayerFS checkpoint differs')
        write = by_purpose('history_write_' + str(n), writer(step), views['work']['path'])
        read = by_purpose('history_changed_read_' + str(n), changed(step), views['work']['path'])
        commands.checks(read, [step])
        require(last_write < write['sequence'] < read['sequence'], 'LayerFS write/read order differs'); last_write = read['sequence']
        current[step['path']]['sha256'] = step['sha256']
        historical = by_purpose('historical_full_read_' + str(n))
        path = historical.get('workspace', {}).get('path')
        require(isinstance(path, str) and re.fullmatch(r'/workspaces/[1-9][0-9]*', path) and path not in paths
                and path not in {v['path'] for v in views.values()} and historical.get('command') == checksum(list(current.values())), 'historical LayerFS full read workspace/recipe differs')
        commands.checks(historical, list(current.values()))
        require(integer(restore.get('step'), 'LayerFS restore step') == n and restore.get('commitId') == revision
                and restore.get('verified') is True, 'LayerFS historical snapshot verification incomplete')
        for key in ('writeMs', 'commitMs'):
            number(row.get(key), key)
        for key in ('restoreMs', 'readMs', 'cleanupMs'):
            number(restore.get(key), key)
        ids.append(revision); paths.append(path)
    if steps:
        for key in ('completed', 'allAcknowledgedIdsPresent', 'finalFullByteVerification', 'changedFileReadbackAfterEveryCommit'):
            require(history.get(key) is True, 'LayerFS history coverage flag missing: ' + key)
        require(integer(history.get('expectedSamples'), 'expected history') == integer(history.get('acknowledgedCommits'), 'acknowledged commits') == 100
                and integer(history.get('historyRecords'), 'history records') == integer(history.get('baselineHistoryRecords'), 'history baseline') + 100,
                'LayerFS history retention counts differ')
        pages = [r['result'] for r in sdk if r['operation'] == 'branch.list_commits']
        require(len(pages) == 2 and all(isinstance(p, dict) and p.get('hasMore') is False and isinstance(p.get('items'), list) for p in pages), 'complete fixed LayerFS history pages absent')
        require(len(pages[0]['items']) == history['baselineHistoryRecords'] and len(pages[1]['items']) == history['historyRecords']
                and set(ids).issubset({r.get('id') for r in pages[1]['items']}), 'acknowledged IDs absent from public LayerFS history')
        commands.checks(by_purpose('history_final_full_read', checksum(list(current.values())), views['work']['path']), list(current.values()))
        close_sum(history.get('totalWriteMs'), [r['writeMs'] for r in rows], 'LayerFS total writes')
        close_sum(history.get('totalCommitMs'), [r['commitMs'] for r in rows], 'LayerFS total checkpoints')
    else:
        require(history is None, 'unexpected nonhistory checkpoints')
    for total, key in (('historicalRestoreMs', 'restoreMs'), ('historicalRestoreReadMs', 'readMs'), ('historicalRestoreCleanupMs', 'cleanupMs')):
        close_sum(sample.get(total), [r[key] for r in restores], total)
    require(len([r for r in sdk if r['operation'] == 'workspace.unmount']) == len(steps) + 3, 'normal historical/original workspace cleanup incomplete')
    require(len([r for r in sdk if r['operation'] == 'sandbox.close']) == len([r for r in sdk if r['operation'] == 'client.close']) == 1, 'normal sandbox/client close incomplete')
    expected_unmounts = set(paths) | {v['path'] for v in views.values()}
    lifecycle = sample['lifecycle']
    for key in ('attemptedUnmounts', 'confirmedUnmounts'):
        require(isinstance(lifecycle.get(key), list) and len(lifecycle[key]) == len(expected_unmounts)
                and set(lifecycle[key]) == expected_unmounts, 'LayerFS unique normal unmount bindings differ')


def metrics(sample, product):
    if product == 'sprig-native':
        mapping = {'initMs': 'init_seconds', 'importMs': 'import_seconds', 'firstForkMs': 'first_fork_seconds',
                   'firstReadMs': 'first_read_seconds', 'importForkReadMs': 'total_import_fork_read_seconds',
                   'warmForkMs': 'warm_fork_seconds', 'warmReadMs': 'warm_read_seconds', 'warmForkReadMs': 'warm_total_seconds',
                   'historyWriteMs': 'write_seconds', 'checkpointMs': 'checkpoint_seconds', 'restoreMs': 'restore_seconds',
                   'historicalReadMs': 'restore_read_seconds', 'historicalCleanupMs': 'restore_cleanup_seconds'}
        values = {name: number(sample.get(key), key) * 1000 for name, key in mapping.items()}
        require('metadata_branch_seconds' in sample and sample['metadata_branch_seconds'] is None
                and sample.get('metadata_branch_available') is True and sample.get('metadata_branch_probe') == 'omitted'
                and sample.get('metadata_branch_unavailable_reason') is None, 'Native omitted metadata probe marker differs')
    else:
        mapping = {'initMs': 'initMs', 'importMs': 'importMs', 'firstForkMs': 'forkToWorkspaceMs',
                   'firstReadMs': 'firstFullReadVerifyMs', 'importForkReadMs': 'totalImportForkReadMs',
                   'warmForkMs': 'warmForkToWorkspaceMs', 'warmReadMs': 'warmFirstFullReadMs', 'warmForkReadMs': 'warmForkReadMs',
                   'restoreMs': 'historicalRestoreMs', 'historicalReadMs': 'historicalRestoreReadMs', 'historicalCleanupMs': 'historicalRestoreCleanupMs'}
        values = {name: number(sample.get(key), key) for name, key in mapping.items()}
        history = sample.get('historyCheck')
        values.update(historyWriteMs=number(history['totalWriteMs'], 'history writes') if history else 0,
                      checkpointMs=number(history['totalCommitMs'], 'history checkpoints') if history else 0)
        close_sum(sample.get('initInclusiveImportForkReadMs'), [values['initMs'], values['importForkReadMs']], 'LayerFS init-inclusive preparation')
    close_sum(values['importForkReadMs'], [values[k] for k in ('importMs', 'firstForkMs', 'firstReadMs')], 'import/fork/read')
    close_sum(values['warmForkReadMs'], [values[k] for k in ('warmForkMs', 'warmReadMs')], 'warm fork/read')
    values['initInclusiveImportForkReadMs'] = values['initMs'] + values['importForkReadMs']
    values['activeUsedBytes'] = validate_space(sample.get('activeSpace'), 'original activeSpace')
    values['postHistoryUsedBytes'] = validate_space(sample.get('postHistorySpace'), 'postHistorySpace')
    return values


def validate_timing_fields(value, root=True):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith(('_seconds', 'Seconds', 'Ms')) or key == 'seconds':
                if root and key == 'metadata_branch_seconds':
                    continue  # The explicit Native omitted marker is checked by metrics().
                number(item, key)
            else:
                validate_timing_fields(item, root=False)
    elif isinstance(value, list):
        for item in value:
            validate_timing_fields(item, root=False)


def validate_sample(sample, record, driver, identity, fixture, archive_root):
    product, case = record['product'], record['case']
    entry, oracle, steps = fixture
    require(isinstance(sample, dict) and sample.get('ok') is True and sample.get('testOnly') is False
            and sample.get('prototype_only') is False and sample.get('product') == product and sample.get('case') == case
            and sample.get('production_sha') == PINS[product], 'raw sample identity/real-success gate differs')
    require(sample.get('schema') == ('sprig-latest-combined-native-sample-v1' if product == 'sprig-native' else 'sprig-latest-combined-layerfs-sample-v1')
            and sample.get('backend') == ('native' if product == 'sprig-native' else 'fuse'), 'raw sampler schema/backend differs')
    require(sample.get('workload_only_verification') is True and sample.get('complete_metadata_verification') is False
            and sample.get('initializationIncludedInImport') is False, 'listed-byte-only/timing scope marker differs')
    validate_timing_fields(sample)
    for key in ('error', 'cleanupErrors', 'logArchiveError', 'reportWriteError', 'rawReportAcceptanceExceeded', 'uncertain', 'cleanupAdmissionBlocked'):
        require(not sample.get(key), 'raw failure/uncertainty retained: ' + key)
    require(sample.get('source') == entry['sourcePath'], 'sample captured wrong source fixture')
    require(integer(sample.get('oracleFiles' if product == 'sprig-native' else 'files'), 'listed file count') == len(oracle)
            and integer(sample.get('logicalBytes'), 'listed logical bytes') == sum(r['bytes'] for r in oracle)
            and integer(sample.get('fullHistoricalSnapshotReadbacks'), 'full historical readbacks') == len(steps), 'listed-file/history coverage differs')
    for key in ('sourceUnchanged', 'originalMainViewUnchanged', 'originalSecondViewUnchanged', 'allAcknowledgedIdsPresent'):
        require(sample.get(key) is True, 'missing original/acknowledgment check: ' + key)
    fs = record.get('filesystem', {})
    mount = absolute(fs.get('mount'), 'outer measured mount')
    directory = absolute(fs.get('directory'), 'outer retained image directory')
    require(mount == directory / 'mount' and fs.get('image') == str(directory / 'new.img')
            and fs.get('runtimeState') == str(directory / 'runtime-state.json') and sample.get('root') == str(mount / 'store'), 'sample/outer filesystem root binding differs')
    require(directory.name.startswith('latest-combined-' + record['id'] + '-')
            and Path(sample.get('recordsFile', '')).parent == directory.parent / 'latest-combined-records', 'outer temporary/record ownership derivation differs')
    validate_space(fs.get('empty'), 'empty 2GiB image', device=True)
    validate_budget(record, driver['sharedJobBudget'])
    require(record.get('verifiedProductInputs') == identity['sprig' if product == 'sprig-native' else 'layerfs'], 'verified built-product identity differs')
    lifecycle = sample.get('lifecycle', {})
    cleanup = lifecycle.get('cleanup', {})
    require(lifecycle.get('normalUnmountOnly') is True and lifecycle.get('uncertain') is not True
            and cleanup.get('complete') is True and cleanup.get('blocked') is not True, 'normal sampler cleanup not confirmed')
    for key in ('Mounts', 'Servers' if product == 'sprig-native' else 'Containers'):
        require(sample.get('remaining' + key + 'Known') is True and sample.get('remaining' + key) == [], 'known zero remaining ' + key + ' missing')
    outer = record.get('cleanup', {})
    require(outer.get('complete') is True and outer.get('blocked') is None and outer.get('normalOnly') is True
            and outer.get('originalImageRetained') is True and outer.get('unmounted') is True, 'outer cleanup/retained image unconfirmed')
    for key in ('cleanupErrors', 'error', 'artifactError'):
        require(not record.get(key), 'driver record failure: ' + key)
    if product == 'sprig-native':
        require(integer(record.get('sampleReturncode'), 'Native sampler returncode') == 0 and sample.get('status') == 'passed', 'Native transport/status failure')
        require(sample.get('binary') == identity['sprig']['binary'] and sample.get('binarySha256') == identity['sprig']['binarySha256']
                and sample.get('binaryHashVerified') is True and sample.get('binarySourcePinVerifiedBySampler') is False, 'Native built binary binding differs')
        integer(sample.get('binaryBytes'), 'binary bytes', 1)
        require(integer(sample.get('historyExpectedSteps'), 'expected Native steps') == len(steps), 'Native expected history differs')
        require(exact_json(sample.get('temporaryDirectory'), {'path': str(mount / 'store/tmp'), 'environment': 'TMPDIR',
                'insideMeasuredRoot': True, 'setBeforeProductCLI': True}), 'Native measured TMPDIR scope differs')
        require(cleanup.get('harnessProcessesKilled') is False and integer(cleanup.get('processesKilled'), 'killed processes') == 0
                and cleanup.get('forceOrLazyUnmountUsed') is False, 'forbidden Native cleanup semantics')
    else:
        require(sample.get('image') == driver['image'] and sample.get('sdkPath') == identity['layerfs']['sdkPath']
                and sample.get('daemonPath') == identity['layerfs']['binary'] and sample.get('oracleSha256') == entry['oracleSha256']
                and sample.get('stepsSha256') == entry.get('stepsSha256'), 'LayerFS image/SDK/fixture identity differs')
        runtime = record.get('runtime', {})
        require(runtime.get('image') == driver['image'] and absolute(runtime.get('dockerRoot'), 'Docker root').is_relative_to(mount)
                and absolute(runtime.get('containerdRoot'), 'containerd root').is_relative_to(mount)
                and record.get('runtimeLeave', {}).get('restored') is True, 'LayerFS runtime placement/restoration unconfirmed')
        validate_space(record.get('runtimeReadySpace'), 'runtime-ready image', device=True)
        require(lifecycle.get('committedHistoryRetained') is True and lifecycle.get('volumeRetained') is True, 'LayerFS retained history/volume missing')
    values = metrics(sample, product)
    views, post = boundary(sample, product, len(steps))
    contents = verify_archives(sample, record, archive_root)
    commands = Commands(sample, record, contents)
    if product == 'sprig-native':
        native_evidence(sample, commands, oracle, steps, views, post)
    else:
        layerfs_evidence(sample, commands, oracle, steps, views)
    # Bind each primary Used sample to its actual complete command output, in order.
    target = sample['root'] if product == 'sprig-native' else str(mount)
    usage = [r for r in commands.rows if r.get('argv') == ['btrfs', 'filesystem', 'usage', '-b', target]]
    groups = [r for r in commands.rows if r.get('argv') == ['btrfs', 'filesystem', 'df', '-b', target]]
    require(len(usage) == len(groups) == 2, 'original/post-history space command boundaries differ')
    for index, key in enumerate(('activeSpace', 'postHistorySpace')):
        require(commands.stdout(usage[index]) == sample[key]['usageRaw'] and commands.stdout(groups[index]) == sample[key]['groupsRaw'], 'space evidence not bound to full command output')
    scopes = ({'nativeExecuteIncludingPostHistorySeconds': number(sample.get('wholeTaskSeconds'), 'Native execute scope'),
               'nativeWholeSampleIncludingSetupCleanupSeconds': number(sample.get('wholeSampleIncludingSetupCleanupSeconds'), 'Native whole sample scope')}
              if product == 'sprig-native' else {'layerfsFullAdapterIncludingSetupCleanupSeconds': number(sample.get('fullTaskSeconds'), 'LayerFS full adapter scope')})
    return {'metrics': values, 'unmatchedScopes': scopes, 'historicalReadbacks': len(steps),
            'archivedFilesVerified': len(contents), 'rawReportAuthoritative': True,
            'runtimeOverhead': {'emptyUsedBytes': fs['empty']['filesystemUsedBytes'],
                                'runtimeReadyUsedBytes': record.get('runtimeReadySpace', {}).get('filesystemUsedBytes'),
                                'separateFromProductMetrics': True}}


def summarize(input_path, archive_root):
    result = {'schema': SUMMARY_SCHEMA, 'complete': False, 'status': 'failed', 'expectedRecords': 4,
              'verifiedRecords': 0, 'expectedHistoricalReadbacks': 200, 'verifiedHistoricalReadbacks': 0,
              'errors': [], 'records': [], 'ratios': None,
              'scope': 'One Sprig Native/LayerFS pair per fixed case; smoke correctness/coverage only.',
              'limitations': ['Fixed listed-file bytes and 100 historical states per product only; NOT exact metadata or hardlink parity.',
                             'One pair per case is descriptive only: not balanced, not a performance estimate, no p99/statistics/promotion.',
                             'Native execute and LayerFS full-adapter scopes are unmatched and have no whole-task ratio.',
                             'Native whole-sample scope includes harness setup/logging/cleanup; it is not product-only.',
                             'Original active Used and post-history Used remain distinct; runtime overhead is separate.',
                             'No equal durability claim; do not pool with historical combined or Cargo series.']}
    report, identity, fixtures = None, None, None
    path = Path(input_path).absolute()
    try:
        report, _, _ = read_json(path, DRIVER_LIMIT)
        require(isinstance(report, dict), 'comparison must be a JSON object')
        require(path.name == 'latest-combined-comparison.json', 'fixed comparison filename required')
        archive = Path(archive_root).absolute()
        checked(archive, directory=True)
        allowed_names = {record_id + suffix for record_id, _, _ in ORDER for suffix in ('.jsonl', '.jsonl.logs')}
        allowed_names |= {'driver.jsonl', 'driver.jsonl.logs'}
        require({item.name for item in archive.iterdir()} <= allowed_names, 'unexpected entry in complete records archive root')
        identity, fixtures = validate_inputs(report, path.parent)
        require(isinstance(report.get('records'), list) and len(report['records']) == 4, 'exact four-record list missing')
        require(report.get('complete') is True and report.get('status') == 'passed', 'driver incomplete/failed (remaining records retained)')
    except ERRORS as error:
        result['errors'].append(str(error))
    source_rows = report.get('records', []) if isinstance(report, dict) and isinstance(report.get('records'), list) else []
    for position, (record_id, product, case) in enumerate(ORDER):
        record = source_rows[position] if position < len(source_rows) else None
        row = {'id': record_id, 'position': position, 'product': product, 'case': case,
               'status': record.get('status', 'malformed') if isinstance(record, dict) else 'missing',
               'verified': False, 'errors': []}
        result['records'].append(row)
        try:
            require(isinstance(record, dict), 'predeclared record missing/malformed')
            require(record.get('id') == record_id and record.get('product') == product and record.get('case') == case
                    and integer(record.get('position'), 'record position') == position, 'predeclared record identity/order differs')
            require(record.get('status') == 'passed' and record.get('correct') is True, 'sample ' + str(record.get('status')) + ': ' + str(record.get('error', 'not successfully completed')))
            require(identity is not None and fixtures is not None, 'driver identity/fixture validation unavailable')
            relative = 'results/latest-combined-' + record_id + '.json'
            require(record.get('rawReportPath') == relative, 'raw report path differs from fixed record ID')
            sample, sha, _ = read_json(path.parent / Path(relative).name)
            require(sha == hash_value(record.get('rawReportSha256'), 'raw report'), 'authoritative raw report bytes/hash mismatch')
            row.update(validate_sample(sample, record, report, identity, fixtures[case], Path(archive_root).absolute()))
            row['verified'] = True
            result['verifiedRecords'] += 1
            result['verifiedHistoricalReadbacks'] += row['historicalReadbacks']
        except ERRORS as error:
            row['errors'].append(str(error))
            if row['status'] == 'passed':
                row['status'] = 'invalid_evidence'
    result['complete'] = not result['errors'] and result['verifiedRecords'] == 4 and result['verifiedHistoricalReadbacks'] == 200
    if result['complete']:
        result['status'] = 'passed'
        result['ratios'] = {}
        for offset, case in enumerate(CASES):
            native, layer = result['records'][offset * 2:offset * 2 + 2]
            ratios = {}
            for key in native['metrics']:
                ratio = layer['metrics'][key] / native['metrics'][key] if native['metrics'][key] > 0 else None
                ratios[key] = ratio if ratio is None or math.isfinite(ratio) else None
            result['ratios'][case] = {'definition': 'LayerFS / Sprig Native; one descriptive pair, no statistical inference',
                                    'values': ratios, 'zeroDenominator': 'null; never infinity or fabricated equality',
                                    'nonfiniteQuotient': 'null; operands remain separately reported'}
    return result


def admit_output(input_path, archive_root, output, body):
    require(len(body) <= RAW_LIMIT, 'summary exceeds16MiB acceptance cap; no partial output written')
    archive = Path(archive_root).absolute()
    if archive.name == 'latest-combined-records':
        # Reuse only the collector's exact-name read-only inventory. Never inspect
        # measured roots, source trees, Docker or retained images for admission.
        from latest_combined_collect import inventory
        results = Path(input_path).absolute().parent
        require(output.parent == results and output.name == 'latest-combined-summary.json', 'CI summary must use exact named results output')
        state = inventory(results, archive.parent)
        require(state.get('completeNamedInventory') is True
                and integer(state.get('bytes'), 'actual named external evidence') + len(body) + MANIFEST_RESERVE <= ARTIFACT_BYTES,
                'summary plus actual complete evidence/manifest exceeds1GiB; no write begun')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--archive-root', required=True, help='directory containing the four ID.jsonl.logs directories')
    parser.add_argument('--output', required=True, help='NEW output file; existing files are never replaced')
    args = parser.parse_args(argv)
    result = summarize(args.input, args.archive_root)
    output = Path(args.output).absolute()
    try:
        checked(output.parent, directory=True)
        body = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        admit_output(args.input, args.archive_root, output, body)
        with output.open('xb') as stream:
            stream.write(body)
    except ERRORS as error:
        print(json.dumps({'complete': False, 'error': str(error)}))
        return 1
    print(json.dumps({'complete': result['complete'], 'status': result['status'],
                      'verifiedRecords': result['verifiedRecords'], 'verifiedHistoricalReadbacks': result['verifiedHistoricalReadbacks'],
                      'output': str(output)}))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
