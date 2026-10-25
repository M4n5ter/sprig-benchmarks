#!/usr/bin/env python3
"""Emit a bounded staged plan. This does not launch any benchmark/job."""
import json
from stress_fixture import file_sizes

MiB = 1024**2

def matrix():
    rows = []
    def add(name, stage=1, **params):
        p = dict(files=256, size=4096, depth=0, width=32, links=0, steps=0, pattern='random')
        p.update(params)
        # Deliberately no reflink/dedup credit: native retained restore trees,
        # plus writable checkpoint generations, plus three initial views.
        logical = sum(file_sizes(p['files'],p['size'],p.get('size_profile','uniform')))
        operations = p['steps'] if p['steps'] else 2  # no-op + one changed checkpoint
        generations = 3 + 2*operations
        rows.append(dict(name=name, stage=stage, fixture=p,
                         logicalBytes=logical,
                         conservativeRetainedLogicalBytes=logical*generations,
                         pilotPairs=1, maximumConfirmedPairs=3,
                         sampleTimeoutSeconds=600, imageGiB=2,
                         capacityReviewRequired=logical*generations > 1024*MiB,
                         priorityPilot=name in ('files-10000','depth-128','history-random-300')))
    for n in (1000, 10000, 50000):
        add(f'files-{n}', stage=1 if n < 50000 else 2, files=n, width=1)
    for n in (64, 256):
        add(f'bytes-{n}MiB', stage=1 if n == 64 else 2, files=n, size=MiB)
    for n in (32, 128):
        add(f'depth-{n}', depth=n, width=1)
    for n in (128, 1024):
        add(f'width-{n}', files=1024, width=n)
    for n in (100, 300, 1000):
        for pattern in ('random','hot','repeated'):
            add(f'history-{pattern}-{n}', stage=1 if n == 100 else 2, steps=n, pattern=pattern)
    add('history-bytes-8MiB-100', stage=2, files=256, size=32768, steps=100)
    add('hardlinks-256', links=256, steps=100, pattern='hot')
    add('cache-history-repeated-300', stage=2, files=200, size=4096, size_profile='cache-1-8-48k', steps=300, pattern='cache-repeated-hot')
    return rows

if __name__ == '__main__':
    print(json.dumps(dict(schema='sprig-stress-plan-v1', launchAuthorized=False,
        maxConcurrentJobs=1, jobTimeoutMinutes=45,
        baselineBenchmark='231d66e2d89c16964dc32ea7279c00abd3bb956a',
        baselineProduct='071036f83691b89bd9e35bb162d34e305e1874b7',
        cases=matrix()), indent=2))
