#!/usr/bin/env python3
"""Fixed ordinary two-worker rename/read/write load; no faults or cleanup bypass."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time

SPEC = {'profile':'normal-rename2-v1','workers':2,'iterationsPerWorker':128,
        'unrelatedFilesPerWorker':1024,'movingFilesPerWorker':8,'payloadBytes':64,
        'witnessMtimeNs':'1700000000123456789'}
SCHEMA = 'sprig-cargo-normal-pressure-v1'


def pressure_identity():
    return dict(schema=SCHEMA,scriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                spec=SPEC,availableReserveBytes=128*1024**2)


def payload(worker, index):
    return hashlib.sha256(f'normal-pressure:{worker}:{index}'.encode()).digest()*2


def verify_worker(directory, worker):
    hot=directory/'active'
    assert not (directory/'moved').exists()
    for index in range(SPEC['unrelatedFilesPerWorker']):
        p=directory/'unrelated'/f'{index:04d}'
        assert p.read_bytes()==payload(worker,index) and p.stat().st_nlink==1
    for index in range(SPEC['movingFilesPerWorker']):
        p=hot/f'file-{index}'
        assert p.read_bytes()==payload(worker,10000+index) and p.stat().st_nlink==1
    a=(hot/'witness').stat();b=(hot/'witness-link').stat()
    assert (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino) and a.st_nlink==b.st_nlink==2
    assert stat.S_IMODE(a.st_mode)==0o640 and a.st_mtime_ns==int(SPEC['witnessMtimeNs'])
    assert (hot/'witness').read_bytes()==payload(worker,20000)
    assert (hot/'symlink').is_symlink() and os.readlink(hot/'symlink')=='witness'
    assert (hot/'mutable').read_bytes()==payload(worker,SPEC['iterationsPerWorker']-1)


def validate_report(report):
    if not isinstance(report,dict) or report.get('schema')!=SCHEMA or report.get('spec')!=SPEC or report.get('profile')!=SPEC['profile']:
        raise ValueError('normal pressure identity mismatch')
    if report.get('ok') is not True or report.get('allWitnessesVerified') is not True:
        raise ValueError('normal pressure witness failure')
    rows=report.get('workers')
    if not isinstance(rows,list) or len(rows)!=2 or any(not isinstance(r,dict) or type(r.get('worker')) is not int for r in rows) or [r.get('worker') for r in rows]!=[0,1]:
        raise ValueError('normal pressure worker identity mismatch')
    for row in rows:
        if type(row.get('completedIterations')) is not int or row['completedIterations']!=128:
            raise ValueError('normal pressure incomplete iteration count')
        for key in ('startedNs','finishedNs'):
            if type(row.get(key)) is not int or not 0<=row[key]<2**53:
                raise ValueError('normal pressure interval is not an exact safe integer')
        if row['finishedNs']<=row['startedNs']:
            raise ValueError('normal pressure empty interval')
        samples=row.get('samplesNanoseconds')
        if not isinstance(samples,dict) or set(samples)!=set(('rename','write','read','metadata')):
            raise ValueError('normal pressure timing classes mismatch')
        for name,values in samples.items():
            if not isinstance(values,list) or len(values)!=(256 if name=='rename' else 128):
                raise ValueError('normal pressure operation count mismatch')
            if any(type(v) is not int or not 0<=v<2**53 for v in values):
                raise ValueError('normal pressure timing is not an exact safe integer')
    overlap=min(r['finishedNs'] for r in rows)-max(r['startedNs'] for r in rows)
    if type(report.get('workerLifetimeOverlapNs')) is not int or report['workerLifetimeOverlapNs']!=overlap or overlap<=0:
        raise ValueError('normal pressure lifetime overlap unverified')
    return report


def run(root):
    root=Path(root)
    pressure=root/'pressure-rename2';pressure.mkdir()
    directories=[]
    for worker in range(SPEC['workers']):
        directory=pressure/f'worker-{worker}';directory.mkdir();directories.append(directory)
        unrelated=directory/'unrelated';unrelated.mkdir()
        for index in range(SPEC['unrelatedFilesPerWorker']):
            (unrelated/f'{index:04d}').write_bytes(payload(worker,index))
        hot=directory/'active';hot.mkdir()
        for index in range(SPEC['movingFilesPerWorker']):
            (hot/f'file-{index}').write_bytes(payload(worker,10000+index))
        (hot/'witness').write_bytes(payload(worker,20000));os.chmod(hot/'witness',0o640)
        os.utime(hot/'witness',ns=(int(SPEC['witnessMtimeNs']),int(SPEC['witnessMtimeNs'])))
        os.link(hot/'witness',hot/'witness-link');os.symlink('witness',hot/'symlink')
        (hot/'mutable').write_bytes(payload(worker,0))
    origin=time.perf_counter_ns();barrier=threading.Barrier(SPEC['workers'])
    def work(worker):
        directory=directories[worker];active=directory/'active';moved=directory/'moved'
        samples={name:[] for name in ('rename','write','read','metadata')}
        def timed(name, operation):
            start=time.perf_counter_ns();result=operation();samples[name].append(time.perf_counter_ns()-start);return result
        barrier.wait();started=time.perf_counter_ns()-origin
        for iteration in range(SPEC['iterationsPerWorker']):
            timed('rename',lambda:os.rename(active,moved))
            data=payload(worker,iteration)
            timed('write',lambda:(moved/'mutable').write_bytes(data))
            assert timed('read',lambda:(moved/'mutable').read_bytes())==data
            def metadata():
                a=(moved/'witness').stat();b=(moved/'witness-link').stat()
                assert (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino) and a.st_nlink==b.st_nlink==2
                assert stat.S_IMODE(a.st_mode)==0o640 and a.st_mtime_ns==int(SPEC['witnessMtimeNs'])
                assert os.readlink(moved/'symlink')=='witness'
            timed('metadata',metadata)
            timed('rename',lambda:os.rename(moved,active))
        finished=time.perf_counter_ns()-origin
        verify_worker(directory,worker)
        return dict(worker=worker,startedNs=started,finishedNs=finished,
                    completedIterations=SPEC['iterationsPerWorker'],samplesNanoseconds=samples)
    # Always join normal workers; no kill, cancellation, detached child or retry.
    with ThreadPoolExecutor(max_workers=SPEC['workers']) as pool:
        rows=list(pool.map(work,range(SPEC['workers'])))
    overlap=min(r['finishedNs'] for r in rows)-max(r['startedNs'] for r in rows)
    assert overlap>0, 'worker lifetime overlap was not observed'
    report=dict(schema=SCHEMA,profile=SPEC['profile'],spec=SPEC,ok=True,workers=rows,
                workerLifetimeOverlapNs=overlap,allWitnessesVerified=True,
                timingBoundary='per-operation wall; concurrent dependent operations; setup/final validation excluded from individual timings but charged to pressure phase and whole sampler',
                concurrencyCaveat='worker lifetime overlap, not proof that every syscall overlaps')
    validate_report(report)
    # Retain raw observations inside the full checkpoint oracle and space charge.
    with (pressure/'observations.json').open('x') as stream:
        json.dump(report,stream,sort_keys=True);stream.write('\n')
    return report


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: stress_cargo_pressure.py ROOT')
    print(json.dumps(run(sys.argv[1]),sort_keys=True))
