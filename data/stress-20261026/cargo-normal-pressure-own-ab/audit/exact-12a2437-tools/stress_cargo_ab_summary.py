#!/usr/bin/env python3
"""Audit all repeated Cargo A/B records before emitting descriptive paired statistics.

Reads standalone Python JSON and copied/original archives, never JavaScript's rounded
embedded tree oracle. No build, mount, retry, pruning, or failure filtering occurs.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys

from stress_stats import latency_summary
from stress_cargo_pressure import SPEC as PRESSURE_SPEC, pressure_identity, validate_report as validate_pressure_report

SCHEMA = 'sprig-stress-cargo-own-ab-v2'
PINS = {'sprig-baseline': '4ef4a90d7ccf5f305416c5374bfc81038f5ca46e',
        'sprig-candidate': 'b300693e01c652c1a9631c61b7a439892d8f75cd'}
EXPERIMENT = {'schema': 'sprig-cargo-experiment-v1', 'profile': 'ordinary',
              'roundsPerMode': 4, 'incrementalModes': [0, 1],
              'order': 'alternating-pairs-mode-offset', 'pressure': None}
IDENTITY = ('image', 'protocolSha256', 'fixtureManifestSha256', 'imageBytes',
            'resourceProtocol', 'abManifestSha256', 'abProducts',
            'sharedJobBudget', 'experimentSpec')
PHASES = 'preflight init import fork fixture_verify cargo_setup toolchain_verify clean_build target_probe clean_artifacts clean_execute noop_build noop_artifacts noop_execute edit edit_build edit_artifacts edit_execute pre_checkpoint_oracle checkpoint_cli checkpoint_readiness checkpoint restore restore_verify restored_artifacts restored_execute restored_rebuild restored_rebuild_artifacts restored_rebuild_execute retained_input_verify space cleanup'.split()
PACKAGES = [f'node{i:03}' for i in range(16)] + ['stress-app']
HEX64 = re.compile(r'[a-f0-9]{64}')
LOG_NAME = re.compile(r'[A-Za-z0-9_.-]+\.(?:stdout|stderr|log|jsonl)')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value, name, positive=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        valid = False
    require(valid, 'invalid ' + name)
    return value


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


def read_regular(path):
    require(path.is_file() and not path.is_symlink(), 'missing/nonregular evidence: ' + str(path))
    return path.read_bytes()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def validate_identity(report):
    require(report.get('schema') == SCHEMA, 'requires repeated own-AB v2 schema')
    spec=report.get('experimentSpec')
    wanted=EXPERIMENT if isinstance(spec,dict) and spec.get('profile')=='ordinary' else {**EXPERIMENT,'profile':PRESSURE_SPEC['profile'],'pressure':pressure_identity()}
    require(spec==wanted,'requires exact reviewed repeated experiment')
    require(type(report.get('rounds')) is int and report['rounds'] == 4, 'requires four rounds')
    require(type(report.get('expectedRecords')) is int and report['expectedRecords'] == 8, 'requires eight expected records per mode')
    require(report.get('imageBytes') == 4 * 1024**3 and type(report['imageBytes']) is int, 'requires symmetric 4GiB')
    require(report.get('resourceProtocol') == 'sprig-cargo-resource-4g-v1', 'resource protocol mismatch')
    require(isinstance(report.get('image'), str) and re.fullmatch(r'sha256:[a-f0-9]{64}', report['image']), 'invalid image identity')
    for name in ('protocolSha256', 'fixtureManifestSha256', 'abManifestSha256'):
        require(isinstance(report.get(name), str) and HEX64.fullmatch(report[name]), 'invalid ' + name)
    products = report.get('abProducts')
    require(isinstance(products, list) and len(products) == 2, 'requires exactly two products')
    require([p.get('label') for p in products] == list(PINS), 'fixed ordered product labels required')
    for product in products:
        require(set(product) == {'label', 'sha', 'binary', 'binarySha256', 'sourcePath'}, 'unexpected product fields')
        require(product['sha'] == PINS[product['label']], 'fixed source pin mismatch')
        require(isinstance(product['binarySha256'], str) and HEX64.fullmatch(product['binarySha256']), 'invalid binary hash')
        for name in ('binary', 'sourcePath'):
            value = product[name]
            require(isinstance(value, str) and Path(value).is_absolute() and os.path.normpath(value) == value, 'invalid product path')
    for name in ('binary', 'sourcePath', 'binarySha256'):
        require(products[0][name] != products[1][name], 'distinct product ' + name + ' required')
    budget = report.get('sharedJobBudget', {})
    start = finite(budget.get('startedEpochSeconds'), 'budget start')
    deadline = finite(budget.get('deadlineEpochSeconds'), 'budget deadline')
    require(0 < deadline-start <= 2400, 'shared deadline exceeds 40-minute admission bound')
    require(budget.get('minimumSampleSeconds') == 180 and budget.get('cleanupReserveSeconds') == 300, 'operation/cleanup reserves changed')


def verify_archives(sample, archive_root, incremental, product, round_):
    declarations = sample.get('completeLogArchive')
    require(isinstance(declarations, list) and declarations, 'complete log archive missing')
    contents = {}
    names = set()
    for row in declarations:
        require(isinstance(row, dict), 'invalid archive declaration')
        archived = row.get('archived')
        require(isinstance(archived, str), 'invalid archive path')
        path = Path(archived)
        suffix = (f'inc{incremental}', f'{product}-{round_}.jsonl.logs', path.name)
        require(path.is_absolute() and path.parts[-3:] == suffix and LOG_NAME.fullmatch(path.name), 'archive outside exact sample identity')
        require(path.name not in names, 'duplicate archive name')
        names.add(path.name)
        require(type(row.get('bytes')) is int and row['bytes'] >= 0 and isinstance(row.get('sha256'), str) and HEX64.fullmatch(row['sha256']), 'invalid archive size/hash')
        local = archive_root.joinpath(*suffix)
        require(not local.parent.is_symlink() and not local.parent.parent.is_symlink(), 'symlink archive directory')
        body = read_regular(local)
        require(len(body) == row['bytes'] and digest(body) == row['sha256'], 'archive bytes/hash mismatch: ' + str(local))
        source = row.get('source')
        require(isinstance(source, str) and source not in contents, 'missing/duplicate archive source')
        contents[source] = body
    return contents


def validate_sample(sample, report, product, incremental, round_, archive_root):
    require(isinstance(sample, dict), 'raw sample is not an object')
    for flag in ('ok', 'fullRestoredTreeVerified', 'originalMainViewUnchanged', 'sourceUnchanged', 'allAcknowledgedIdsPresent'):
        require(sample.get(flag) is True, 'sample correctness failed: ' + flag)
    require(sample.get('testOnly') is False, 'mock/unspecified sample refused')
    require(type(sample.get('incremental')) is int and sample['incremental'] == incremental, 'sample mode mismatch')
    require(sample.get('production_sha') == product['sha'] and sample.get('binarySha256') == product['binarySha256'], 'sample binary/source identity mismatch')
    require(sample.get('image') == report['image'] and sample.get('protocolSha256') == report['protocolSha256'], 'sample shared identity mismatch')
    require(sample.get('backend') == 'writable' and sample.get('compressionPolicy') == 'auto (default init)', 'sample backend/compression mismatch')
    require(sample.get('remainingMounts') == [] and sample.get('remainingContainers') == [], 'remaining resource inventory not empty')
    lifecycle = sample.get('lifecycle', {})
    require(lifecycle.get('cleanup', {}).get('complete') is True, 'normal cleanup not complete')
    active = lifecycle.get('activeAtSpace', {})
    require(active.get('retainedGenerationCount') == 4 and len(active.get('foregroundFuseProcesses', [])) == 3 and len(active.get('views', [])) == 3, 'retained generation/view accounting mismatch')
    seconds = [v for v in active['views'] if v.get('name') == 'second']
    require(len(seconds) == 1, 'missing exact restored view')
    compiler = active.get('compilerContainer', {})
    require(compiler.get('count') == 1 and compiler.get('image') == report['image'] and compiler.get('inspection', {}).get('state', {}).get('Running') is True and compiler.get('generation') == seconds[0].get('generation') and compiler.get('tree') == seconds[0].get('path'), 'live exact-generation compiler mismatch')
    sessions = sample.get('compilerSessions', [])
    require(len(sessions) == 4 and all(s.get('removed') is True and s.get('uncertain') is False and s.get('naturalExitAndPidGoneVerified') is True for s in sessions), 'compiler sessions not naturally closed')
    observations = sample.get('cargoBuildObservations', [])
    for phase in ('clean_build', 'noop_build', 'edit_build', 'restored_rebuild'):
        rows = [r for r in observations if r.get('phase') == phase]
        require(len(rows) == 1 and rows[0].get('returncode') == 0, 'missing/failed Cargo build: ' + phase)
        fresh = phase in ('noop_build', 'restored_rebuild')
        expected = 'freshPackages' if fresh else 'compilingPackages'
        opposite = 'compilingPackages' if fresh else 'freshPackages'
        require(sorted(rows[0].get(expected, [])) == sorted(PACKAGES) and rows[0].get(opposite) == [], 'all17 Compiling/Fresh gate failed: ' + phase)
    for phase in ('clean_artifacts', 'noop_artifacts', 'edit_artifacts', 'restored_artifacts', 'restored_rebuild_artifacts'):
        rows = [r for r in sample.get('artifactChecks', []) if r.get('phase') == phase]
        require(len(rows) == 1, 'missing/duplicate artifact check')
        row = rows[0]
        require(all(row.get(k) is True for k in ('ok', 'hardlinkProbe', 'exactMtime')) and row.get('generatedFiles') and row.get('buildValue') == (1 if phase in ('clean_artifacts', 'noop_artifacts') else 2), 'artifact correctness mismatch')
    for name in PHASES:
        finite(sample.get('phase_seconds', {}).get(name), 'phase ' + name)
    phases = sample['phase_seconds']
    require(abs(phases['checkpoint']-phases['checkpoint_cli']-phases['checkpoint_readiness']) < 1e-6, 'checkpoint boundary mismatch')
    for name in ('checkpointCompilerQuiescePlusProduct', 'restoreToCompilerReady'):
        finite(sample.get('convenience_seconds', {}).get(name), 'convenience ' + name)
    finite(sample.get('full_task_seconds'), 'full task')
    finite(sample.get('activeSpace', {}).get('filesystemUsedBytes'), 'whole Used')
    contents = verify_archives(sample, archive_root, incremental, product['label'], round_)
    expected = sample.get('checkpointTreeOracle')
    require(isinstance(expected, dict) and expected.get('schema') == 'cargo-full-tree-v1' and isinstance(expected.get('entries'), list) and isinstance(expected.get('hardlink_groups'), list), 'full-tree oracle missing')
    require(expected['entries'] and all(type(e.get('mtime_ns')) is int for e in expected['entries']), 'exact integer nanosecond evidence missing')
    for purpose in ('pre_checkpoint_oracle', 'restore_verify'):
        rows = [c for c in sample.get('commands', []) if c.get('purpose') == purpose]
        require(len(rows) == 1 and rows[0].get('returncode') == 0, 'missing/failed oracle command')
        row = rows[0]
        require(isinstance(row.get('stdout'), str) and contents.get(row.get('stdoutPath')) == row['stdout'].encode(), 'oracle raw stdout not archived exactly')
        require(strict_json(row['stdout']) == expected, 'exact-ns full restored tree mismatch')
    validate_pressure_evidence(sample,report,contents)
    return len(contents)


def validate_pressure_evidence(sample,report,contents):
    spec=report['experimentSpec']
    if spec['profile']=='ordinary':
        require('normalPressure' not in sample and 'normal_pressure' not in sample['phase_seconds'],'ordinary sample contains pressure')
        return
    pressure=validate_pressure_report(sample.get('normalPressure'))
    require(sample.get('normalPressureScriptSha256')==spec['pressure']['scriptSha256'],'pressure helper identity mismatch')
    finite(sample['phase_seconds'].get('normal_pressure'),'normal pressure phase')
    commands=[row for row in sample.get('commands',[]) if row.get('purpose')=='normal_pressure']
    require(len(commands)==1 and commands[0].get('returncode')==0,'missing successful pressure command')
    command=commands[0];raw=command.get('stdout')
    require(isinstance(raw,str) and contents.get(command.get('stdoutPath'))==raw.encode(),'raw pressure stdout not archived exactly')
    require(command.get('stdinSha256')==spec['pressure']['scriptSha256'],'pressure executed helper differs')
    require(strict_json(raw)==pressure and digest(raw.encode())==sample.get('normalPressureRawSha256'),'raw pressure timing evidence differs')
    observations=[entry for entry in sample['checkpointTreeOracle']['entries'] if entry.get('path')=='pressure-rename2/observations.json']
    require(len(observations)==1 and observations[0].get('sha256')==sample['normalPressureRawSha256'],'pressure observations not retained in full restored oracle')
    # Every file and witness participates in the same exact-byte/mtime/hardlink oracle.
    entries={entry['path']:entry for entry in sample['checkpointTreeOracle']['entries']}
    for worker in range(2):
        base=f'pressure-rename2/worker-{worker}'
        require(sum(name.startswith(base+'/unrelated/') for name in entries)==1024,'pressure unrelated-file witness count mismatch')
        witness=entries.get(base+'/active/witness',{})
        require(witness.get('mode')==0o640 and witness.get('mtime_ns')==int(PRESSURE_SPEC['witnessMtimeNs']),'pressure exact-metadata witness mismatch')
        require([base+'/active/witness',base+'/active/witness-link'] in sample['checkpointTreeOracle']['hardlink_groups'],'pressure hardlink group mismatch')
        require(entries.get(base+'/active/symlink',{}).get('target')=='witness','pressure symlink witness mismatch')


def pressure_operation_summaries(sample):
    pressure=sample.get('normalPressure')
    if pressure is None:return None
    result={}
    for name in ('rename','write','read','metadata'):
        values=[value/1e9 for row in pressure['workers'] for value in row['samplesNanoseconds'][name]]
        result[name]={**latency_summary(values),'valuesSeconds':values,'minimum':min(values),
                      'tailCaveat':'Dependent concurrent operations in ONE sample; descriptive nearest-rank p95/p99, not independent trials or whole-task tails.'}
    return result


def distribution(values):
    result = latency_summary(values)
    result.update(minimum=min(values), values=list(values), p95=None, p99=None,
                  tailCaveat='Four runner-local repeats per variant; insufficient for p95/p99 or significance claims.')
    return result


def paired_metrics(records):
    metrics = {}
    keys = set(records[0]['metrics'])
    require(all(set(row['metrics']) == keys for row in records), 'metric set differs across samples')
    indexed = {(r['round'], r['product']): r for r in records}
    for name in sorted(keys):
        baseline = [indexed[i, 'sprig-baseline']['metrics'][name] for i in range(4)]
        candidate = [indexed[i, 'sprig-candidate']['metrics'][name] for i in range(4)]
        ratios = [c/b if b > 0 else None for b, c in zip(baseline, candidate)]
        pairs = [{'round': i, 'firstProduct': records[2*i]['product'], 'baseline': b, 'candidate': c,
                  'candidateOverBaseline': ratio, 'percentChange': (ratio-1)*100 if ratio is not None else None}
                 for i, (b, c, ratio) in enumerate(zip(baseline, candidate, ratios))]
        valid = all(r is not None and r > 0 for r in ratios)
        metrics[name] = {'baseline': distribution(baseline), 'candidate': distribution(candidate), 'pairs': pairs,
                         'medianPairedRatio': statistics.median(ratios) if all(r is not None for r in ratios) else None,
                         'geometricMeanPairedRatio': math.exp(statistics.mean(math.log(r) for r in ratios)) if valid else None,
                         'undefinedRatioReason': None if valid else 'Nonpositive baseline/candidate prevents a complete geometric ratio; no pair dropped.',
                         'orderStrata': {first: [p for p in pairs if p['firstProduct'] == first] for first in PINS}}
    return metrics


def summarize(paths, archive_root):
    result = {'schema': 'sprig-stress-cargo-own-ab-summary-v1', 'complete': False, 'status': 'incomplete',
              'expectedSamples': 16, 'records': [], 'reports': [], 'errors': [], 'comparisons': None,
              'notes': ['All16 correctness and archive gates must pass before any paired statistic is emitted; no sample is dropped.',
                        'Standalone sampler JSON and archived oracle stdout retain exact integer nanoseconds; embedded JS oracle is not authoritative.',
                        'Four runner-local pairs per mode are descriptive small-N repeats, not independent multi-host trials or statistical significance.',
                        'No per-sample p95/p99 inference; phase/composite timers overlap and cannot be summed or subtracted from whole wall.',
                        'Modes and experiment profiles remain separate; historical one-pair runs are never pooled.',
                        'Pressure-operation p95/p99, when present, describe dependent operations within one sample; four-repeat distributions are NOT end-to-end latency tails.',
                        'Cargo phases exclude the separate normal_pressure stage; stressed whole-task wall/space are not directly comparable with unstressed runs.']}
    loaded = []
    for expected_mode, path in enumerate(paths):
        info = {'path': str(path), 'incremental': expected_mode}
        result['reports'].append(info)
        try:
            body = read_regular(path); report = strict_json(body)
            require(isinstance(report, dict), 'report is not an object')
            loaded.append((path, report, digest(body)))
            info.update(sha256=digest(body), status=report.get('status'), complete=report.get('complete'), error=report.get('error'))
            validate_identity(report)
            require(type(report.get('incremental')) is int and report['incremental'] == expected_mode, 'input mode/order mismatch')
            require(report.get('complete') is True and report.get('status') == 'passed', 'report incomplete/failed')
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            result['errors'].append(str(path) + ': ' + str(error))
    require(len(paths) == 2, 'exactly inc0 and inc1 input paths required')
    if len(loaded) == 2:
        first, second = loaded[0][1], loaded[1][1]
        for key in IDENTITY:
            if first.get(key) != second.get(key): result['errors'].append('cross-mode identity mismatch: ' + key)
        gate = second.get('previousGate')
        if not isinstance(gate, dict) or gate.get('sha256') != loaded[0][2]:
            result['errors'].append('inc1 prerequisite hash does not bind exact inc0 report')
    for path, report, _ in loaded:
        mode = report.get('incremental')
        rows = report.get('records')
        if not isinstance(rows, list):
            result['errors'].append(str(path) + ': records not a list'); continue
        if len(rows) != 8: result['errors'].append(str(path) + ': expected eight records, found ' + str(len(rows)))
        for index, row in enumerate(rows):
            audit = {'reportPath': str(path), 'index': index, 'incremental': mode}
            result['records'].append(audit)
            try:
                require(isinstance(row, dict), 'record is not an object')
                for key in ('product', 'round', 'correct', 'status', 'error', 'originalError', 'cleanupErrors', 'rawReportPath', 'rawReportSha256', 'sampleReturncode'):
                    if key in row: audit[key] = row[key]
                round_ = index//2
                require(type(mode) is int and mode in (0, 1), 'invalid mode')
                order = list(PINS)[::(-1 if (round_+mode) % 2 else 1)]
                require(index < 8 and type(row.get('round')) is int and row['round'] == round_ and row.get('product') == order[index % 2] and type(row.get('incremental')) is int and row['incremental'] == mode, 'record identity/order mismatch')
                require(row.get('correct') is True and row.get('status') == 'passed' and type(row.get('sampleReturncode')) is int and row['sampleReturncode'] == 0 and not row.get('cleanupErrors'), 'record failed or cleanup blocked')
                name = f"stress-cargo-{row['product']}-inc{mode}-{round_}.json"
                require(row.get('rawReportPath') == 'results/'+name, 'raw path differs from fixed sample name')
                raw = read_regular(path.parent/name)
                require(isinstance(row.get('rawReportSha256'), str) and digest(raw) == row['rawReportSha256'], 'standalone raw report hash mismatch')
                sample = strict_json(raw)
                product = next(p for p in report['abProducts'] if p['label'] == row['product'])
                audit['archivedFilesVerified'] = validate_sample(sample, report, product, mode, round_, archive_root)
                embedded = row.get('sample', {})
                for key in ('ok', 'incremental', 'production_sha', 'binarySha256', 'image', 'protocolSha256', 'phase_seconds', 'convenience_seconds', 'full_task_seconds'):
                    require(embedded.get(key) == sample.get(key), 'embedded/raw safe field differs: ' + key)
                metrics = {'wholeSamplerSeconds': finite(row.get('wholeSampleSubprocessWallSeconds'), 'whole sampler wall', True),
                           'runtimeSetupSeconds': finite(row.get('runtimeSetupSeconds'), 'runtime setup'),
                           'fullTaskSeconds': sample['full_task_seconds'], 'wholeFilesystemUsedBytes': sample['activeSpace']['filesystemUsedBytes']}
                for group, prefix in (('phase_seconds', 'phase.'), ('convenience_seconds', 'convenience.')):
                    for key, value in sample[group].items(): metrics[prefix+key] = finite(value, prefix+key)
                operations=pressure_operation_summaries(sample)
                if operations is not None:
                    audit['normalPressureOperations']=operations
                    for operation,stats in operations.items():
                        for statistic in ('median','maximum','p95','p99'):
                            metrics[f'pressure.{operation}.{statistic}Seconds']=stats[statistic]
                audit['metrics'] = metrics
            except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration) as error:
                audit['validationError'] = str(error)
                result['errors'].append(f'{path} record{index}: {error}')
    if not result['errors']:
        try:
            result['comparisons'] = {f'inc{mode}': paired_metrics([r for r in result['records'] if r['incremental'] == mode]) for mode in (0, 1)}
            result.update(complete=True, status='passed', experimentSpec=loaded[0][1]['experimentSpec'], identity={key: loaded[0][1][key] for key in IDENTITY})
        except (ValueError, KeyError, TypeError, IndexError) as error:
            result['errors'].append('statistics blocked: ' + str(error)); result['comparisons'] = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('incremental0', type=Path); parser.add_argument('incremental1', type=Path)
    parser.add_argument('--archive-root', required=True, type=Path, help='Original stress-cargo-records or relocated artifact records directory')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = summarize([args.incremental0, args.incremental1], args.archive_root)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'complete': report['complete'], 'status': report['status'], 'records': len(report['records']), 'errors': report['errors']}))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
