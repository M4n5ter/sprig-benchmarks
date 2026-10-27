#!/usr/bin/env python3
"""Fail-closed, offline audit of the fixed 24-sample mounted Sprig verified-read-reuse A/B.

No product, build, mount, repair, rerun or external operation is performed. Original
raw JSON and archived command bytes are authoritative; JS-rounded embedded tree
nanoseconds are deliberately not compared. All 24 gates precede every ratio.
"""
import argparse
import json
import math
from pathlib import Path
import re
import statistics
import sys

from stress_cargo_ab_summary import (
    HEX64, PACKAGES, digest, finite, read_regular, require, strict_json as _strict_json,
    validate_sample as validate_sprig_sample, verify_archives,
)
from stress_cargo_latest_summary import (
    ERRORS as COMMON_ERRORS, PROTOCOL_SHA, canonical_path, exact_int, normalize_tree,
    validate_admission, verify_common_evidence,
)

ERRORS = COMMON_ERRORS + (RecursionError,)
SCHEMA = 'sprig-stress-cargo-verified-read-reuse-v1'
SUMMARY_SCHEMA = 'sprig-stress-cargo-verified-read-reuse-summary-v1'
PLAN_SCHEMA = 'sprig-cargo-verified-read-reuse-plan-v1'
MANIFEST_FILE = 'stress-cargo-verified-read-reuse-products.json'
PLAN_FILE = 'stress-cargo-verified-read-reuse-plan.json'
PINS = {'sprig-baseline': '4eb0f4d7afdb19bf22d9667dc520ede8b162c737',
        'sprig-verified-read-reuse': 'f61ce655d9270e206d97e20bc104644c821e4e5d'}
PRODUCTS = tuple(PINS)
EXPERIMENT = {'schema': 'sprig-cargo-verified-read-reuse-experiment-v1', 'profile': 'ordinary',
              'roundsPerMode': 6, 'incrementalModes': [0, 1],
              'order': 'six-alternating-reverse-mode1', 'pressure': None}
PERMUTATIONS = ((0, 1), (1, 0), (0, 1), (1, 0), (0, 1), (1, 0))
IDENTITY = ('image', 'protocolSha256', 'fixtureManifestSha256', 'imageBytes',
            'resourceProtocol', 'abcManifestSha256', 'abcProducts', 'abcPlanSha256',
            'sharedJobBudget', 'abcExperiment')
EDGES = (('A-to-B', PRODUCTS[0], PRODUCTS[1]),)
SCHEDULE_KEYS = {'product', 'incremental', 'round', 'position', 'order'}
CLEANUP = ['strict runtime restoration completed',
           'normal outer unmount and detached loop verified',
           'detached synthetic image disposed after durable reports/log archive']
MIB = 1024**2
IMAGE_BYTES = 4 * 1024**3
MIXED_KEYS = {'abProducts', 'abManifestSha256', 'experimentSpec', 'directManifest',
              'directManifestSha256', 'productionSha', 'comparatorSha', 'latestDirect',
              'normalPressure', 'normalPressureScriptSha256', 'normalPressureRawSha256',
              'pressureProfile', 'lifecycleTrace', 'writableDiagnostics', 'diagnostic',
              'diagnostics', 'trace', 'traceProfile', 'instrumentation',
              'SPRIG_LIFECYCLE_TRACE', 'SPRIG_WRITABLE_DIAGNOSTICS',
              'fault', 'faults', 'faultInjection', 'layerfs', 'layerfsManifest', 'layerfsProducts'}


def strict_json(body):
    value = _strict_json(body)
    def check(item):
        if isinstance(item, float):
            require(math.isfinite(item), 'nonfinite JSON number')
        elif isinstance(item, dict):
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
    check(value)
    return value


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else ordered[middle - 1] + (ordered[middle] - ordered[middle - 1]) / 2


def sample_order(incremental, round_):
    require(type(incremental) is int and incremental in (0, 1), 'invalid schedule mode')
    require(type(round_) is int and 0 <= round_ < 6, 'invalid schedule round')
    indices = PERMUTATIONS[round_ if incremental == 0 else 5 - round_]
    return [PRODUCTS[index] for index in indices]


def schedule(incremental=None):
    modes = (0, 1) if incremental is None else (incremental,)
    return [{'product': product, 'incremental': mode, 'round': round_, 'position': position, 'order': order}
            for mode in modes for round_ in range(6)
            for order in [sample_order(mode, round_)] for position, product in enumerate(order)]


def same_json(left, right):
    # Python equality equates false with 0 and true with 1; identities must not.
    try:
        return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return False


def same_evidence(left, right):
    # JS emits an integral timer 2.0 as 2; safe numeric fields may differ only
    # in that representation, never by bool coercion or rounded tree integers.
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(same_evidence(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same_evidence(a, b) for a, b in zip(left, right))
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    return left == right


def ordinary_only(value, name):
    require(isinstance(value, dict), name + ' is not an object')
    require(not MIXED_KEYS.intersection(value), 'mixed own-AB/direct/pressure/trace identity in ' + name)
    require(not any(any(word in key.lower() for word in ('pressure', 'trace', 'diagnostic', 'instrumentation', 'fault', 'layerfs'))
                    for key in value), 'pressure/trace/diagnostic/fault/LayerFS field in ' + name)
    require('profile' not in value or value['profile'] == 'ordinary', 'nonordinary profile in ' + name)
    require(not any('pressure' in str(key).lower() or 'trace' in str(key).lower()
                    or 'diagnostic' in str(key).lower() or 'fault' in str(key).lower()
                    or 'layerfs' in str(key).lower() for key in value.get('phase_seconds', {})),
            'pressure/trace/diagnostic/fault/LayerFS phase in ' + name)
    for command in value.get('commands', []):
        purpose = command.get('purpose', '') if isinstance(command, dict) else ''
        require(not any(word in str(purpose).lower() for word in ('pressure', 'trace', 'diagnostic', 'fault', 'layerfs')),
                'pressure/trace/diagnostic/fault/LayerFS command in ' + name)


def validate_products(products):
    require(isinstance(products, list) and len(products) == 2, 'exactly two immutable products required')
    require(all(isinstance(item, dict) for item in products), 'non-object product')
    require([item.get('label') for item in products] == list(PRODUCTS), 'fixed ordered A/B labels required')
    for item in products:
        require(set(item) == {'label', 'sha', 'binary', 'binarySha256', 'sourcePath'}, 'unexpected product fields')
        require(item['sha'] == PINS[item['label']], 'fixed source pin mismatch')
        require(isinstance(item['binarySha256'], str) and HEX64.fullmatch(item['binarySha256']), 'invalid binary hash')
        for key in ('binary', 'sourcePath'):
            canonical_path(item[key], key)
    for key in ('binary', 'sourcePath', 'binarySha256'):
        require(len({item[key] for item in products}) == 2, 'two distinct product ' + key + ' required')
    return products


def validate_plan(plan, products):
    require(isinstance(plan, dict) and set(plan) == {'schema', 'abcExperiment', 'abcProducts', 'records'},
            'global plan requires exact four fields')
    require(plan['schema'] == PLAN_SCHEMA and same_json(plan['abcExperiment'], EXPERIMENT), 'global plan experiment mismatch')
    require(same_json(plan['abcProducts'], products), 'global plan product identity mismatch')
    require(same_json(plan['records'], schedule()), 'global plan must predeclare exact 24-position schedule')
    return plan


def validate_identity(report, path):
    ordinary_only(report, 'mode report')
    require(report.get('schema') == SCHEMA, 'requires fixed verified-read-reuse A/B schema')
    require(type(report.get('rounds')) is int and report['rounds'] == 6, 'requires exactly six rounds per mode')
    require(type(report.get('expectedRecords')) is int and report['expectedRecords'] == 12, 'requires twelve expected records per mode')
    require(same_json(report.get('abcExperiment'), EXPERIMENT), 'requires exact ordinary verified-read-reuse A/B experiment')
    require(report.get('protocolSha256') == PROTOCOL_SHA, 'frozen DAG16 protocol differs')
    require(type(report.get('imageBytes')) is int and report['imageBytes'] == IMAGE_BYTES
            and report.get('resourceProtocol') == 'sprig-cargo-resource-4g-v1', 'requires symmetric 4GiB resource protocol')
    require(isinstance(report.get('image'), str) and re.fullmatch(r'sha256:[a-f0-9]{64}', report['image']), 'invalid shared image identity')
    for key in ('fixtureManifestSha256', 'abcManifestSha256', 'abcPlanSha256'):
        require(isinstance(report.get(key), str) and HEX64.fullmatch(report[key]), 'invalid ' + key)
    products = validate_products(report.get('abcProducts'))
    raw = read_regular(path.parent / MANIFEST_FILE)
    require(digest(raw) == report['abcManifestSha256'] and same_json(strict_json(raw), products), 'product manifest raw bytes/hash mismatch')
    raw_plan = read_regular(path.parent / PLAN_FILE)
    require(digest(raw_plan) == report['abcPlanSha256'], 'global plan raw bytes/hash mismatch')
    validate_plan(strict_json(raw_plan), products)
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
    capacity = strict_json(read_regular(path.parent / 'stress-cargo-capacity.json'))
    require(isinstance(capacity, dict) and capacity.get('schema') == 'sprig-stress-cargo-capacity-v1', 'capacity pilot schema differs')
    require(all(capacity.get(key) == report[key] for key in ('image', 'protocolSha256', 'fixtureManifestSha256')),
            'capacity pilot shared identity differs')
    require(capacity.get('toolchain') == {'rustc': '1.90.0', 'cargo': '1.90.0'}, 'capacity pilot toolchain differs')
    pilots = capacity.get('pilots')
    require(isinstance(pilots, list) and len(pilots) == 2
            and all(isinstance(p, dict) and type(p.get('incremental')) is int for p in pilots)
            and sorted(p['incremental'] for p in pilots) == [0, 1], 'requires symmetric two-mode external capacity pilot')
    for pilot in pilots:
        require(exact_int(pilot.get('targetAllocatedBytes'), 'pilot target allocation', 1) <= 2**53 - 1, 'unsafe pilot target allocation')
    mode = report.get('incremental')
    require(type(mode) is int and mode in (0, 1), 'invalid report incremental mode')
    require(same_json(report.get('capacityPilot'), next(p for p in pilots if p['incremental'] == mode)),
            'selected capacity pilot differs from original evidence')
    return fixture


def validate_resources(row, report, fixture):
    validate_admission(row, report)
    before, after = row['budgetAdmission'], row['postRuntimeBudgetAdmission']
    maximum = report['sharedJobBudget']['deadlineEpochSeconds'] - report['sharedJobBudget']['startedEpochSeconds']
    require(after['remainingSeconds'] <= before['remainingSeconds'] <= maximum, 'budget reset or post-runtime time reversal')
    value = row.get('capacityAdmission')
    require(isinstance(value, dict) and value.get('admitted') is True, 'capacity admission missing')
    for key in ('availableBytes', 'requiredBytes', 'deviceBytes', 'targetAllocatedBytes', 'fixtureLogicalBytes', 'pressureReserveBytes'):
        require(exact_int(value.get(key), 'capacity ' + key, 0) <= 2**53 - 1, 'unsafe capacity integer')
    logical = sum(entry['size'] for entry in fixture['initial']['entries'] if entry['type'] == 'file')
    require(value['deviceBytes'] == IMAGE_BYTES and value['pressureReserveBytes'] == 0, 'capacity 4GiB/ordinary resource bound differs')
    require(value['targetAllocatedBytes'] == report['capacityPilot']['targetAllocatedBytes']
            and value['fixtureLogicalBytes'] == logical, 'capacity pilot/fixture allocation differs')
    wanted = max(512 * MIB, 4 * value['targetAllocatedBytes'] + 8 * logical + 256 * MIB)
    require(value['requiredBytes'] == wanted and value['availableBytes'] >= wanted, 'capacity reserve arithmetic/admission differs')
    ready = row.get('runtimeReadySpace')
    require(isinstance(ready, dict) and ready.get('availableBytes') == value['availableBytes']
            and ready.get('deviceBytes') == IMAGE_BYTES, 'runtime-ready capacity evidence differs')
    recovery = row.get('recoveryMetadata')
    require(isinstance(recovery, dict) and all(recovery.get(key) is True for key in ('runtimeAttempted', 'runtimeReady', 'sampleStarted'))
            and recovery.get('cleanupAdmissionBlocked') is None, 'known-clean runtime/sample admission unconfirmed')
    require(row.get('cleanup') == CLEANUP and 'isolatedImageRetained' in row and row['isolatedImageRetained'] is None,
            'strict runtime restoration/outer unmount/disposal unconfirmed')


def validate_record(row, expected, report, path, archive_root, fixture):
    ordinary_only(row, 'record')
    require(all(key in row for key in SCHEDULE_KEYS)
            and same_json({key: row[key] for key in SCHEDULE_KEYS}, expected), 'record identity/order/position mismatch')
    require(row.get('status') in ('not-run', 'failed', 'passed'), 'invalid predeclared record status')
    require(row.get('correct') is True and row['status'] == 'passed'
            and type(row.get('sampleReturncode')) is int and row['sampleReturncode'] == 0
            and not any(row.get(key) for key in ('error', 'originalError', 'cleanupErrors', 'runtimeSetupFailure', 'failureStderr')),
            'record not-run, failed or cleanup blocked')
    require(fixture is not None, 'report identity/fixture not validated')
    validate_resources(row, report, fixture)
    product = next(item for item in report['abcProducts'] if item['label'] == expected['product'])
    for key in ('verifiedProductInputs', 'verifiedProductInputsAfter'):
        require(same_json(row.get(key), product), key + ' differs from frozen product manifest')
    mode, round_, label = expected['incremental'], expected['round'], expected['product']
    name = f'stress-cargo-{label}-inc{mode}-{round_}.json'
    require(row.get('rawReportPath') == 'results/' + name, 'raw path differs from fixed sample name')
    raw = read_regular(path.parent / name)
    require(isinstance(row.get('rawReportSha256'), str) and HEX64.fullmatch(row['rawReportSha256'])
            and digest(raw) == row['rawReportSha256'], 'standalone raw report hash mismatch')
    sample = strict_json(raw)
    ordinary_only(sample, 'raw sample')
    # This context selects only the ordinary pressure validator; it never changes
    # the A/B header, pins, rounds, schedule, raw evidence or prerequisite gate.
    validation_report = {**report, 'experimentSpec': {'profile': 'ordinary'}}
    count = validate_sprig_sample(sample, validation_report, product, mode, round_, archive_root)
    contents = verify_archives(sample, archive_root, mode, label, round_)
    verify_common_evidence(sample, report, fixture, contents, layerfs=False)
    checkpoint = sample.get('checkpoint', {})
    require(checkpoint.get('committed') is True and checkpoint.get('revision') == sample.get('restoredRevision')
            and isinstance(sample.get('restoredRevision'), str) and HEX64.fullmatch(sample['restoredRevision']),
            'Sprig acknowledged checkpoint/restore identity differs')
    embedded = row.get('sample')
    require(isinstance(embedded, dict), 'embedded sample missing')
    ordinary_only(embedded, 'embedded sample')
    for key in ('ok', 'incremental', 'production_sha', 'binarySha256', 'image', 'protocolSha256',
                'phase_seconds', 'convenience_seconds', 'full_task_seconds', 'fullRestoredTreeVerified',
                'originalMainViewUnchanged', 'sourceUnchanged', 'allAcknowledgedIdsPresent'):
        require(same_evidence(embedded.get(key), sample.get(key)), 'embedded/raw safe field differs: ' + key)
    metrics = {'wholeSamplerSeconds': finite(row.get('wholeSampleSubprocessWallSeconds'), 'whole sampler wall', True),
               'runtimeSetupSeconds': finite(row.get('runtimeSetupSeconds'), 'runtime setup'),
               'fullTaskSeconds': sample['full_task_seconds'],
               'wholeFilesystemUsedBytes': sample['activeSpace']['filesystemUsedBytes']}
    for group, prefix in (('phase_seconds', 'phase.'), ('convenience_seconds', 'convenience.')):
        values = sample.get(group)
        require(isinstance(values, dict), 'invalid metric group')
        for key, value in values.items():
            metrics[prefix + key] = finite(value, prefix + key)
    return {'archivedFilesVerified': count, 'metrics': metrics, 'validated': True}


def distribution(values):
    return {'n': len(values), 'values': list(values), 'median': median(values),
            'minimum': min(values), 'maximum': max(values), 'p95': None, 'p99': None,
            'caveat': 'Six runner-local blocks, not task tails, independent hosts or significance evidence.'}


def compare_mode(records):
    require(len(records) == 12, 'exactly twelve validated samples required for statistics')
    indexed = {(row['round'], row['product']): row for row in records}
    require(len(indexed) == 12, 'duplicate sample identity in statistics')
    keys = set(records[0]['metrics'])
    require(all(set(row['metrics']) == keys for row in records), 'ordinary matched metric set differs across samples')
    edges, negatives = {}, {}
    for edge, reference, candidate in EDGES:
        metrics, edge_negatives = {}, []
        for name in sorted(keys):
            baseline = [indexed[round_, reference]['metrics'][name] for round_ in range(6)]
            contender = [indexed[round_, candidate]['metrics'][name] for round_ in range(6)]
            ratios = [c / b if b > 0 else None for b, c in zip(baseline, contender)]
            require(all(ratio is None or (math.isfinite(ratio) and math.isfinite((ratio - 1) * 100)) for ratio in ratios),
                    'ratio/percent overflow')
            pairs = []
            for round_, (b, c, ratio) in enumerate(zip(baseline, contender, ratios)):
                first, second = indexed[round_, reference], indexed[round_, candidate]
                pairs.append({'round': round_, 'order': first['order'], 'referenceProduct': reference,
                              'candidateProduct': candidate, 'referencePosition': first['position'],
                              'candidatePosition': second['position'],
                              'firstProduct': reference if first['position'] < second['position'] else candidate,
                              'reference': b, 'candidate': c, 'candidateOverReference': ratio,
                              'percentChange': (ratio - 1) * 100 if ratio is not None else None})
            valid = all(ratio is not None and ratio > 0 and math.isfinite(ratio) for ratio in ratios)
            # Zero denominators never silently reduce the six-pair denominator.
            metrics[name] = {'reference': distribution(baseline), 'candidate': distribution(contender), 'pairs': pairs,
                             'medianPairedRatio': median(ratios) if all(r is not None for r in ratios) else None,
                             'geometricMeanPairedRatio': math.exp(statistics.mean(math.log(r) for r in ratios)) if valid else None,
                             'undefinedRatioReason': None if valid else 'Nonpositive denominator/ratio prevents a complete geometric ratio; all six pairs retained.',
                             'orderStrata': {label: [pair for pair in pairs if pair['firstProduct'] == label]
                                             for label in (reference, candidate)},
                             'positionStrata': {label: {str(position): distribution([
                                 indexed[round_, label]['metrics'][name] for round_ in range(6)
                                 if indexed[round_, label]['position'] == position]) for position in range(2)}
                                 for label in (reference, candidate)}}
            edge_negatives.extend({'metric': name, **pair} for pair in pairs
                                  if pair['candidate'] > pair['reference'])
        edges[edge] = {'referenceProduct': reference, 'candidateProduct': candidate, 'metrics': metrics}
        negatives[edge] = edge_negatives
    return edges, negatives


def summarize(paths, archive_root):
    paths, archive_root = [Path(path) for path in paths], Path(archive_root)
    result = {'schema': SUMMARY_SCHEMA, 'complete': False, 'status': 'incomplete', 'expectedSamples': 24,
              'records': [], 'missingRecords': [], 'notRunRecords': [], 'reports': [], 'errors': [],
              'comparisons': None, 'slowerOrLargerPairs': None,
              'notes': ['All 24 ordinary samples and identity/correctness/archive/known-clean gates must pass before ANY ratio; every failure, missing slot and outlier is retained.',
                        'Two fixed baseline/verified-read-reuse Sprig revisions only; no clean-sync/read-TTL, directory-count/narrow, LayerFS, older own-AB, pressure, diagnostic, fault or unmounted core-only results are relabeled or pooled.',
                        'Standalone raw JSON and archived command outputs retain exact integer nanoseconds; embedded JS trees are not authoritative.',
                        'Six same-block paired ratios for the single A-to-B edge per mode on ONE host, not independent hosts or significance evidence.',
                        'No task p95/p99 or significance inference. Order strata have three pairs, each of two position strata has three observations per variant.',
                        'Runtime setup is separate from matched sampler-launch-through-exit wall. Phase/composite timers overlap: do not sum or subtract them as exclusive costs.',
                        'Whole filesystem Used includes runtime/compiler image, target/cache, retained views/history/logs; no baseline subtraction.',
                        'External capacity pilots are admission setup, not measured product samples. No rerun, filtering, promotion or deadline extension.']}
    if len(paths) != 2:
        result['errors'].append('exactly inc0 and inc1 input paths required')
    loaded = {}
    for mode, path in enumerate(paths):
        info = {'path': str(path), 'expectedIncremental': mode}
        result['reports'].append(info)
        try:
            body = read_regular(path)
            report = strict_json(body)
            require(isinstance(report, dict), 'mode report is not an object')
            loaded[mode] = (path, report, digest(body), None)
            info.update({key: value for key, value in report.items() if key != 'records'})
            info['sha256'] = digest(body)
            require(mode in (0, 1) and path.name == f'stress-cargo-verified-read-reuse-{mode}.json', 'input report name/order differs')
            require(type(report.get('incremental')) is int and report['incremental'] == mode, 'mode identity differs')
            fixture = validate_identity(report, path)
            loaded[mode] = (path, report, digest(body), fixture)
            require(report.get('complete') is True and report.get('status') == 'passed'
                    and not any(report.get(key) for key in ('error', 'originalError', 'cleanupErrors')), 'report incomplete/failed')
            if mode == 0:
                require(report.get('previousGate') is None, 'inc0 cannot have a prerequisite gate')
        except ERRORS as error:
            info['validationError'] = str(error)
            result['errors'].append(str(path) + ': ' + str(error))
    if 0 in loaded and 1 in loaded:
        first, second = loaded[0][1], loaded[1][1]
        for key in IDENTITY:
            try:
                require(same_json(first.get(key), second.get(key)), 'cross-mode identity mismatch: ' + key)
            except ERRORS as error:
                result['errors'].append(str(error))
        try:
            previous = second.get('previousGate')
            require(isinstance(previous, dict) and set(previous) == {'path', 'sha256'}
                    and previous['sha256'] == loaded[0][2], 'inc1 prerequisite hash does not bind exact inc0 report')
            canonical_path(previous['path'], 'previous gate path')
            require(Path(previous['path']).name == 'stress-cargo-verified-read-reuse-0.json', 'inc1 prerequisite path differs')
        except ERRORS as error:
            result['errors'].append(str(error))
    for mode in (0, 1):
        expected_rows = schedule(mode)
        rows = []
        if mode in loaded:
            path, report, _, fixture = loaded[mode]
            rows = report.get('records')
            if not isinstance(rows, list):
                result['errors'].append(str(path) + ': records is not a list')
                rows = []
            if len(rows) != 12:
                result['errors'].append(str(path) + ': expected twelve predeclared records, found ' + str(len(rows)))
            stopped = False
            for index, row in enumerate(rows):
                audit = {'reportPath': str(path), 'index': index, 'expectedIncremental': mode}
                result['records'].append(audit)
                try:
                    require(isinstance(row, dict), 'record is not an object')
                    # Preserve all driver fields/errors, not a success-only subset.
                    audit.update({key: value for key, value in row.items() if key != 'sample'})
                    embedded = row.get('sample')
                    if isinstance(embedded, dict):
                        audit['sampleErrorEvidence'] = {key: value for key, value in embedded.items()
                                                       if 'error' in key.lower() or 'uncertain' in key.lower()}
                    if row.get('status') == 'not-run':
                        result['notRunRecords'].append({**{key: row.get(key) for key in SCHEDULE_KEYS}, 'index': index, 'status': 'not-run'})
                    require(index < 12, 'unexpected extra record')
                    require(not (stopped and row.get('status') == 'passed'), 'execution continued after first failed/not-run position')
                    if row.get('status') != 'passed':
                        stopped = True
                    audit.update(validate_record(row, expected_rows[index], report, path, archive_root, fixture))
                except ERRORS as error:
                    if not isinstance(row, dict):
                        audit['unparsedRecord'] = row
                    audit['validationError'] = str(error)
                    result['errors'].append(f'{path} record{index}: {error}')
        for index, expected in enumerate(expected_rows):
            present = any(isinstance(row, dict) and all(key in row for key in SCHEDULE_KEYS)
                          and same_json({key: row[key] for key in SCHEDULE_KEYS}, expected) for row in rows)
            if not present:
                result['missingRecords'].append({**expected, 'index': index, 'attempted': False, 'status': 'not_recorded'})
        if mode not in loaded:
            result['errors'].append(f'inc{mode}: mode report missing or unreadable; twelve positions unrecorded')
    if not result['errors'] and len(result['records']) == 24 and not result['missingRecords']:
        try:
            keys = set(result['records'][0]['metrics'])
            require(all(set(row['metrics']) == keys for row in result['records']), 'cross-mode ordinary metric set differs')
            compared, negatives = {}, {}
            for mode in (0, 1):
                compared[f'inc{mode}'], negatives[f'inc{mode}'] = compare_mode([
                    row for row in result['records'] if row['incremental'] == mode])
            result.update(complete=True, status='passed', comparisons=compared, slowerOrLargerPairs=negatives,
                          identity={key: loaded[0][1][key] for key in IDENTITY})
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
    report = summarize([args.inc0, args.inc1], args.archive_root)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'complete': report['complete'], 'status': report['status'],
                      'records': len(report['records']), 'missingRecords': len(report['missingRecords']), 'errors': report['errors']}))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
