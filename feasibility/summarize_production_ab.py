#!/usr/bin/env python3
"""Strict completeness and within-run paired ratios; no unpaired causal inference."""
import json
import math
from pathlib import Path
import statistics
import sys
from production_ab import CASES, BACKENDS, PAIRS, validate

p = Path(sys.argv[1])
d = json.loads(p.read_text())
assert d['complete'] and len(d['records']) == 80
expected = {(b, c, i, r) for b in BACKENDS for c in CASES for i in range(PAIRS)
            for r in ['baseline', 'candidate']}
records = {(r['backend'], r['case'], r['pair'], r['revision']): r for r in d['records']}
assert set(records) == expected and len(records) == len(d['records'])
assert len(d['pairCleanup']) == 40 and all(x['complete'] for x in d['pairCleanup'])
assert {(x['backend'], x['case'], x['pair']) for x in d['pairCleanup']} == {(b, c, i) for b in BACKENDS for c in CASES for i in range(PAIRS)}
assert all(len(x['images']) == 2 and all(image['removed'] for image in x['images']) for x in d['pairCleanup'])
for r in records.values():
    assert r['correct'] and r['sample']['ok']
    validate(r['sample'], r['revision'], r['backend'])
    v = r['filesystemUsedDeltaBytes']
    assert type(v) in (int, float) and math.isfinite(v) and v >= 0
    assert r['sample']['fullHistoricalSnapshotReadbacks'] == 100
    assert r['sample']['history_distinct_revisions'] == 100


def metrics(r):
    s = r['sample']
    return {'preparationMs': 1000 * (s['init_seconds'] + s['total_import_fork_read_seconds']),
            'warmMs': 1000 * s['warm_total_seconds'],
            'writeAndCheckpointMs': 1000 * (s['write_seconds'] + s['checkpoint_seconds']),
            'checkpointMs': 1000 * s['checkpoint_seconds'],
            'filesystemUsedDeltaBytes': r['filesystemUsedDeltaBytes']}

rows = []
for backend in BACKENDS:
    for case in CASES:
        for metric in metrics(records[backend, case, 0, 'baseline']):
            pairs = []
            for i in range(PAIRS):
                a = metrics(records[backend, case, i, 'baseline'])[metric]
                b = metrics(records[backend, case, i, 'candidate'])[metric]
                assert a > 0 and b >= 0
                pairs.append({'pair': i, 'baseline': a, 'candidate': b,
                              'candidateOverBaseline': b / a, 'candidateMinusBaseline': b - a})
            ratios = [x['candidateOverBaseline'] for x in pairs]
            rows.append({'backend': backend, 'case': case, 'metric': metric, 'pairs': pairs,
                         'baselineMedian': statistics.median(x['baseline'] for x in pairs),
                         'candidateMedian': statistics.median(x['candidate'] for x in pairs),
                         'medianPairedRatio': statistics.median(ratios),
                         'minPairedRatio': min(ratios), 'maxPairedRatio': max(ratios)})
p.with_name('production-ab-summary.json').write_text(json.dumps({'complete': True,
    'expectedRecords': 80, 'historicalReadbacks': 8000, 'ratioDirection': 'candidate/baseline',
    'rows': rows}, indent=2) + '\n')
print('Complete: 80 records, 8000 historical readbacks; paired summary written.')
