#!/usr/bin/env python3
"""Verify checked-in complete artifact plus public GitHub exact-head success.
Uses public unauthenticated metadata; no token/permission scope changes.
"""
import argparse
import json
from pathlib import Path
import urllib.request
from verify_stress_artifact import verify


def validate(root, provenance, source_sha, run):
    proof=verify(root)
    assert not proof['diagnostic'] and len(proof['records'])==6
    assert {r['backend'] for r in proof['records']}=={'native','projection','writable'}
    assert source_sha==provenance['productSha'] and source_sha in proof['sourcePins'].values()
    assert run['id']==provenance['runId'] and run['head_sha']==provenance['benchmarkSha']
    assert run['status']=='completed' and run['conclusion']=='success'
    assert run['path']=='.github/workflows/stress-canary.yml'
    return dict(accepted=True,runId=run['id'],headSha=run['head_sha'],sourceSha=source_sha,
                url=provenance['runUrl'],artifactProof=proof)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--provenance',type=Path,required=True);p.add_argument('--source-sha',required=True);a=p.parse_args()
    provenance=json.loads(a.provenance.read_text())
    run_id=provenance['runId'];assert type(run_id) is int and run_id>0
    url=f'https://api.github.com/repos/M4n5ter/sprig-benchmarks/actions/runs/{run_id}'
    request=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'sprig-stress-gate'})
    with urllib.request.urlopen(request,timeout=30) as response:run=json.load(response)
    print(json.dumps(validate(a.root,provenance,a.source_sha,run),indent=2))
