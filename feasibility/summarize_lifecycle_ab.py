#!/usr/bin/env python3
"""Strict completeness and within-run paired ratios; no unpaired causal inference."""
import json
import math
from pathlib import Path
import statistics
import sys
from lifecycle_ab import validate, PINS

p = Path(sys.argv[1])
d = json.loads(p.read_text())
assert d['mode'] in ('smoke', 'full')
canonical_cases = (['identical', 'unique', 'mixed', 'insert', 'history-distributed', 'history-hotset', 'history-recurring']
                   if d['mode'] == 'full' else ['identical', 'history-distributed'])
assert d['cases'] == canonical_cases and d['pairs'] == (5 if d['mode'] == 'full' else 1)
assert len(d['backends']) == 1 and d['backends'][0] in ('native', 'projection', 'writable')
assert d['pins'] == PINS
CASES, BACKENDS, PAIRS = d['cases'], d['backends'], d['pairs']
EXPECTED = len(CASES) * len(BACKENDS) * PAIRS * 2
READBACKS = sum(c.startswith('history-') for c in CASES) * len(BACKENDS) * PAIRS * 200
assert d['expectedHistoricalReadbacks'] == READBACKS
assert sum(r['sample']['fullHistoricalSnapshotReadbacks'] for r in d['records']) == READBACKS
assert d['complete'] and d['expectedRecords'] == EXPECTED and len(d['records']) == EXPECTED
expected = {(b, c, i, r) for b in BACKENDS for c in CASES for i in range(PAIRS)
            for r in ['baseline', 'candidate']}
records = {(r['backend'], r['case'], r['pair'], r['revision']): r for r in d['records']}
assert set(records) == expected and len(records) == len(d['records'])
assert len(d['pairCleanup']) == EXPECTED // 2 and all(x['complete'] for x in d['pairCleanup'])
assert {(x['backend'], x['case'], x['pair']) for x in d['pairCleanup']} == {(b, c, i) for b in BACKENDS for c in CASES for i in range(PAIRS)}
assert all(len(x['images']) == 2 and all(image['removed'] for image in x['images']) for x in d['pairCleanup'])
for r in records.values():
    assert r['correct'] and r['sample']['ok']
    validate(r['sample'], r['revision'], r['backend'], r['case'])
    v = r['filesystemUsedDeltaBytes']
    assert type(v) in (int, float) and math.isfinite(v) and v >= 0
    for field, point in [('filesystemUsedDeltaBytes', 'activeSpace'), ('postHistoryFilesystemUsedDeltaBytes', 'postHistorySpace')]:
        value = r[field]
        assert type(value) in (int, float) and math.isfinite(value) and value >= 0
        assert value == r['sample'][point]['filesystemUsedBytes'] - r['filesystem']['empty']['filesystemUsedBytes']
    assert r['sample']['fullHistoricalSnapshotReadbacks'] == (100 if r['case'].startswith('history-') else 0)


def metrics(r):
    s = r['sample']
    return {'preparationMs': 1000 * (s['init_seconds'] + s['total_import_fork_read_seconds']),
            'warmMs': 1000 * s['warm_total_seconds'],
            'writeAndCheckpointMs': 1000 * (s['write_seconds'] + s['checkpoint_seconds']),
            'checkpointMs': 1000 * s['checkpoint_seconds'],
            'filesystemUsedDeltaBytes': r['filesystemUsedDeltaBytes'],
            'postHistoryFilesystemUsedDeltaBytes': r['postHistoryFilesystemUsedDeltaBytes'],
            'restoreMs': 1000 * s['restore_seconds'],
            'restoreReadMs': 1000 * s['restore_read_seconds'],
            'restoreCleanupMs': 1000 * s['restore_cleanup_seconds'],
            'restoreTotalMs': 1000 * (s['restore_seconds'] + s['restore_read_seconds'] + s['restore_cleanup_seconds'])}

rows = []
for backend in BACKENDS:
    for case in CASES:
        for metric in metrics(records[backend, case, 0, 'baseline']):
            pairs = []
            for i in range(PAIRS):
                a = metrics(records[backend, case, i, 'baseline'])[metric]
                b = metrics(records[backend, case, i, 'candidate'])[metric]
                assert a >= 0 and b >= 0
                pairs.append({'pair': i, 'baseline': a, 'candidate': b,
                              'candidateOverBaseline': b / a if a > 0 else None, 'candidateMinusBaseline': b - a})
            ratios = [x['candidateOverBaseline'] for x in pairs if x['candidateOverBaseline'] is not None]
            rows.append({'backend': backend, 'case': case, 'metric': metric, 'pairs': pairs,
                         'baselineMedian': statistics.median(x['baseline'] for x in pairs),
                         'candidateMedian': statistics.median(x['candidate'] for x in pairs),
                         'medianPairedRatio': statistics.median(ratios) if ratios else None,
                         'minPairedRatio': min(ratios) if ratios else None, 'maxPairedRatio': max(ratios) if ratios else None})
p.with_name('lifecycle-ab-summary.json').write_text(json.dumps({'complete': True,
    'expectedRecords': EXPECTED, 'historicalReadbacks': READBACKS, 'ratioDirection': 'candidate/baseline',
    'rows': rows}, indent=2) + '\n')
print(f'Complete: {EXPECTED} records, {READBACKS} historical readbacks; paired summary written.')
