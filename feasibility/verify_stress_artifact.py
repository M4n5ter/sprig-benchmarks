#!/usr/bin/env python3
"""Read-only verification of downloaded complete stress artifacts and log hashes."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    roots=list(root.rglob('stress-results/stress-comparison.json'))
    if len(roots)!=1: raise ValueError('expected exactly one stress-comparison artifact')
    results=roots[0].parent;r=json.loads(roots[0].read_text())
    assert r['complete'] and r['status']=='passed'
    assert len(r['records'])==len(r['products'])*len(r['backends'])*r['rounds']
    fixture=json.loads((results/'fixture.json').read_text())
    operations=len(fixture['edits'])+int(r['noopCheckpoint'])
    pins={p['label']:p['sha'] for p in r['products']}
    out=[]
    for row in r['records']:
        s=row['sample']
        assert row['correct'] and s['ok'] and s['lifecycle']['cleanup']['complete']
        assert s['remainingMounts']==[] and s['production_sha']==pins[row['product']]
        assert s['fullHistoricalSnapshotReadbacks']==operations
        assert len(s['fullTreeChecks'])==7+2*operations
        assert all(x['verified'] for x in s['fullTreeChecks'])
        if row['productType']=='sprig':
            if not r['diagnostic']: assert s['lifecycleTraceEvidence']['validRecords']==0
            logs=[(x['archived'],x['bytes'],x['sha256']) for x in s['completeLogArchive']]
        else:
            assert s['remainingContainers']==[] and s['remainingContainersKnown'] and s['remainingMountsKnown']
            logs=[(x['path'],x['bytes'],x['sha256']) for x in s['preservedLogs']]
        for name,size,digest in logs:
            relative=Path(name.split('/stress-results/',1)[1])
            assert not relative.is_absolute() and '..' not in relative.parts
            path=results/relative;assert not path.is_symlink()
            data=path.read_bytes()
            assert len(data)==size and hashlib.sha256(data).hexdigest()==digest
        out.append(dict(product=row['product'],backend=row['backend'],round=row['round'],
                        fullTreeChecks=len(s['fullTreeChecks']),historicalReadbacks=operations,
                        cleanup=True,archivedFilesVerified=len(logs)))
    return dict(verified=True,comparisonProtocol=r['comparisonProtocol'],diagnostic=r['diagnostic'],
                records=out,totalFullTreeChecks=sum(x['fullTreeChecks'] for x in out),
                totalHistoricalReadbacks=sum(x['historicalReadbacks'] for x in out),
                sourcePins=pins)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    text=json.dumps(verify(a.root),indent=2)+'\n'
    if a.output:a.output.write_text(text)
    print(text,end='')
