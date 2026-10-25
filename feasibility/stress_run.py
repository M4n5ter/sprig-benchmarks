#!/usr/bin/env python3
"""Sequential bounded stress orchestration on approved GitHub ephemeral runners.
No local mount fallback, process killing, forced unmount, pruning, or blind retry.
Products config pins two exact binaries/source SHAs, or Sprig plus LayerFS.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from stress_fixture import generate
from stress_plan import matrix

GIB = 1024**3
MIB = 1024**2
SHA = re.compile(r'^[0-9a-f]{40}$')
RELEASE = '9f97a7ec95b662e9cb288704afa165feff132cfa'

class BudgetAbort(RuntimeError): pass


def command(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(json.dumps(dict(argv=[str(x) for x in args], returncode=result.returncode,
                                          stdout=result.stdout, stderr=result.stderr)))
    return result.stdout


def physical_space(mount):
    command(['btrfs','filesystem','sync',mount])
    usage = command(['btrfs','filesystem','usage','-b',mount])
    match = re.search(r'^\s*Used:\s*(\d+)\s*$', usage, re.M)
    if not match: raise RuntimeError('missing Btrfs Used')
    return dict(filesystemUsedBytes=int(match[1]), usageRaw=usage,
                groupsRaw=command(['btrfs','filesystem','df','-b',mount]),
                extentSetRaw=command(['btrfs','filesystem','du','-s','--raw',mount]))


def resolve_file(value):
    p = Path(value)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise ValueError('expected absolute regular input file: '+str(p))
    return p.resolve(strict=True)


def validate_products(products):
    if not isinstance(products,list) or not 1 <= len(products) <= 2:
        raise ValueError('one canary product or two paired products required')
    names=set()
    for p in products:
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,30}',p['label']) or p['label'] in names:
            raise ValueError('unsafe/duplicate product label')
        names.add(p['label'])
        if not SHA.fullmatch(p['sha']): raise ValueError('immutable40hex SHA required')
        if p['type']=='sprig':
            binary=resolve_file(p['binary'])
            if not os.access(binary,os.X_OK): raise ValueError('binary not executable')
            p['binarySha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
        elif p['type']=='layerfs':
            if p['sha'] != RELEASE: raise ValueError('comparator release changed')
            for key in ('daemonPath','layerfsSdkPath','imageArchive'): resolve_file(p[key])
            if not re.fullmatch(r'sha256:[0-9a-f]{64}',p['image']):
                raise ValueError('immutable runtime image ID required')
        else: raise ValueError('unknown product')
    diagnostics=[bool(p.get('diagnostic',False)) for p in products]
    if any(diagnostics) and (not all(diagnostics) or any(p['type']!='sprig' for p in products)):
        raise ValueError('diagnostic and primary samples cannot be mixed')
    return products


def capacity_guard(used, retained, image_bytes=2*GIB):
    if retained > GIB:
        raise BudgetAbort('capacity blocked: conservative retained logical exceeds1GiB ceiling')
    if used + retained + 256*MIB > image_bytes:
        raise BudgetAbort('capacity blocked: runtime-ready Used+retained+256MiB reserve exceeds2GiB')


def cell_parameters(cell):
    if cell == 'canary':
        return dict(files=16,size=4096,depth=4,width=4,links=4,steps=3,pattern='hot',symlink=True),True
    match = next((x for x in matrix() if x['name']==cell),None)
    if match is None: raise ValueError('unknown stress cell')
    if match['capacityReviewRequired']: raise BudgetAbort('cell requires capacity review, not launchable')
    p=dict(match['fixture'])
    noop=p['steps']==0
    if noop: p['steps']=1
    return p,noop


def ordered_products(products, round_no, pair_order):
    if pair_order not in ('forward','reverse'): raise ValueError('invalid pair order')
    return list(products) if (round_no+int(pair_order=='reverse'))%2==0 else list(reversed(products))


def cleanup_admission(record, *, sampler_started, runtime_attempted,
                      runtime_ready, runtime_state):
    """Read-only proof gate; unknown output/state never authorizes teardown."""
    if sampler_started:
        sample=record.get('sample')
        if not isinstance(sample,dict): return 'sampler report missing or malformed'
        error=sample.get('error',{})
        if not isinstance(error,dict): return 'sampler error field malformed'
        if error.get('uncertain'):
            return 'sampler reported uncertain mutation or exec outcome'
        lifecycle=sample.get('lifecycle')
        if not isinstance(lifecycle,dict) or not isinstance(lifecycle.get('cleanup'),dict):
            return 'sampler cleanup proof malformed'
        if lifecycle['cleanup'].get('complete') is not True:
            return 'sampler did not affirm normal cleanup completion'
        if sample.get('remainingMounts') != []:
            return 'sampler did not affirm zero remaining mounts'
        if record.get('productType')=='layerfs':
            if sample.get('remainingContainers') != [] or sample.get('remainingContainersKnown') is not True or sample.get('remainingMountsKnown') is not True:
                return 'comparator did not affirm known zero containers/mounts'
        elif sample.get('lifecycle',{}).get('daemons') != []:
            return 'Sprig did not affirm zero remaining daemons'
    if runtime_attempted and not runtime_ready:
        # No state file means relocation failed before configuration mutation;
        # otherwise require explicit completed rollback, never assume it.
        if runtime_state is not None and runtime_state.get('restored') is not True:
            return 'runtime setup rollback incomplete or unconfirmed'
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--products',type=Path,required=True)
    parser.add_argument('--cell',required=True)
    parser.add_argument('--backend',choices=['native','projection','writable','all'],required=True)
    parser.add_argument('--rounds',type=int,choices=[1,3],default=1)
    parser.add_argument('--pair-order',choices=['forward','reverse'],default='forward')
    parser.add_argument('--budget-seconds',type=int,default=1200)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true':
        parser.error('only root in authorized ephemeral GitHub Actions runner')
    temp=Path(os.environ.get('RUNNER_TEMP',''))
    if not temp.is_absolute() or not temp.is_dir(): parser.error('RUNNER_TEMP must exist and be absolute')
    if not 1 <= a.budget_seconds <= 1200: parser.error('measurement budget maximum1200seconds')
    if a.backend=='all' and a.cell!='canary': parser.error('all backends only for canary')
    products=validate_products(json.loads(a.products.read_text()))
    if len(products)==1 and a.cell!='canary': parser.error('pressure requires two paired products')
    diagnostic=any(p.get('diagnostic',False) for p in products)
    if diagnostic and a.cell!='canary': parser.error('instrumented diagnostics limited to canary')
    params,noop=cell_parameters(a.cell)
    backends=['native','projection','writable'] if a.backend=='all' else [a.backend]
    if not a.output.is_absolute() or not a.output.is_relative_to(temp) or a.output==temp:
        parser.error('output must be strictly belowRUNNER_TEMP for external ledgers')
    a.output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic(); deadline=started+a.budget_seconds
    report=dict(schema='sprig-stress-run-v1',complete=False,status='running',cell=a.cell,
                products=products,backends=backends,rounds=a.rounds,records=[],diagnostic=diagnostic,pairOrder=a.pair_order,
                comparisonProtocol=('diagnostic-canary' if diagnostic else 'within-sprig-ab' if len(products)==2 and all(p['type']=='sprig' for p in products) else 'sprig-layerfs-stress' if len(products)==2 else 'single-product-canary'),
                measurementBudgetSeconds=a.budget_seconds,wholeTaskScope='per-sampler task excludes fixture/runtime setup; phases overlap only as documented',
                durability='Sprig sync enabled; LayerFS Disposable WAL/OFF and MEMORY/OFF are unequal',
                cpuMemoryComparison='unavailable; no partial process RSS/CPU claim')
    def save():
        report['elapsedSeconds']=time.monotonic()-started
        (a.output/'stress-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        fixture_dir=Path(tempfile.mkdtemp(prefix='stress-source-',dir=temp))
        fixture=generate(fixture_dir/'tree',**params)
        fixture_path=fixture_dir/'fixture.json';fixture_path.write_text(json.dumps(fixture))
        oracle=fixture_dir/'listed.json';oracle.write_text(json.dumps([dict(path=e['path'],bytes=e['size'],sha256=e['sha256']) for e in fixture['initial']['entries'] if e['type']=='file']))
        (a.output/'fixture.json').write_text(json.dumps(fixture,indent=2)+'\n')
        logical=sum(e.get('size',0) for e in fixture['initial']['entries'])
        retained=logical*(3+2*(len(fixture['edits'])+int(noop)))
        capacity_guard(0,retained)
        report.update(logicalBytes=logical,conservativeRetainedLogicalBytes=retained,
                      noopCheckpoint=noop,fixtureSha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest())
        for round_no in range(a.rounds):
            for backend in backends:
                for product in ordered_products(products,round_no,a.pair_order):
                    # Canary reserves120seconds per sample; pressure600. Never
                    # start a sample without its full budget+normal cleanup reserve.
                    sample_budget=min(120 if a.cell=='canary' else 600,
                                      (a.budget_seconds-60)//(a.rounds*len(backends)*len(products)))
                    if sample_budget<1: raise BudgetAbort('insufficient per-sample budget')
                    if deadline-time.monotonic() < sample_budget+30:
                        raise BudgetAbort('time budget aborted before next sample; no incomplete mutation started')
                    if shutil.disk_usage(temp).free < 2*GIB+GIB:
                        raise BudgetAbort('host capacity blocked: need2GiB image+1GiB evidence reserve')
                    identity=f'{backend}-{product["label"]}-{round_no}'
                    record=dict(identity=identity,backend=backend,product=product['label'],round=round_no,status='running',correct=False,productType=product['type'])
                    report['records'].append(record);save()
                    isolated=Path(tempfile.mkdtemp(prefix='stress-'+identity+'-',dir=temp))
                    image=isolated/'store.img';mount=isolated/'mount';runtime=isolated/'runtime-state.json'
                    with image.open('xb') as stream: stream.truncate(2*GIB)
                    mount.mkdir();mounted=False;runtime_attempted=False;runtime_ready=False;sampler_started=False
                    try:
                        record['mkfs']=command(['mkfs.btrfs','-d','single','-m','dup',image])
                        command(['mount','-o','loop,noatime',image,mount]);mounted=True
                        if command(['stat','-f','-c','%T',mount]).strip()!='btrfs': raise RuntimeError('wrong filesystem')
                        record['emptySpace']=physical_space(mount)
                        if product['type']=='layerfs':
                            runtime_attempted=True
                            record['runtime']=json.loads(command(['/usr/bin/python3','feasibility/stress_runtime_storage.py','enter','--state',runtime,'--mount',mount,'--archive',product['imageArchive'],'--image',product['image']]))
                            runtime_ready=True
                        record['runtimeReadySpace']=physical_space(mount)
                        capacity_guard(record['runtimeReadySpace']['filesystemUsedBytes'],retained)
                        ledger=a.output/(identity+'-steps.jsonl')
                        if product['type']=='sprig':
                            args=['/usr/bin/python3','feasibility/stress_sample.py','run','--root',mount/'sample','--source',fixture_dir/'tree','--oracle',oracle,'--fixture',fixture_path,'--binary',product['binary'],'--production-sha',product['sha'],'--backend',backend,'--records',ledger.resolve(),'--budget-seconds',str(sample_budget)]
                            if noop: args.append('--noop-checkpoint')
                            if diagnostic: args.append('--diagnostic')
                        else:
                            opts=dict(root=str(mount/'sample'),measuredMount=str(mount),source=str(fixture_dir/'tree'),fixturePath=str(fixture_path),daemonPath=product['daemonPath'],layerfsSdkPath=product['layerfsSdkPath'],image=product['image'],recordsPath=str(ledger.resolve()),sampleBudgetSeconds=sample_budget,noopCheckpoint=noop)
                            options=a.output/(identity+'-options.json');options.write_text(json.dumps(opts))
                            args=['node','feasibility/stress_layerfs.mjs',str(options.resolve())]
                        if deadline-time.monotonic() < sample_budget+30:
                            raise BudgetAbort('runtime/image setup consumed admission budget; sampler not started')
                        sampler_started=True
                        sample_started=time.monotonic()
                        proc=subprocess.run([str(x) for x in args],capture_output=True,text=True,check=False)
                        record['wholeSampleSubprocessWallSeconds']=time.monotonic()-sample_started
                        record['wholeSampleSubprocessWallScope']='authoritative matched sampler process launch through exit, including preparation, verification, accounting, normal cleanup and evidence serialization; excludes external image/runtime/fixture setup'
                        (a.output/(identity+'-stdout.json')).write_text(proc.stdout)
                        (a.output/(identity+'-stderr.txt')).write_text(proc.stderr)
                        record['sampleReturncode']=proc.returncode
                        try: record['sample']=json.loads(proc.stdout)
                        except ValueError: raise RuntimeError('sample did not emit oneJSON report; raw stdout retained')
                        if proc.returncode==2 or record['sample'].get('status') in ('budget_aborted','capacity_blocked'):
                            raise BudgetAbort('sample budget aborted; partial evidence retained')
                        if proc.returncode or not record['sample'].get('ok'):
                            raise RuntimeError('sample failed; raw report retained')
                        record['correct']=True;record['status']='passed'
                    finally:
                        cleanup=[]
                        runtime_state=None
                        if runtime.exists():
                            try:
                                runtime_state=json.loads(runtime.read_text())
                                if not isinstance(runtime_state,dict): runtime_state={'restored':False,'malformed':True}
                            except (OSError,ValueError): runtime_state={'restored':False,'unreadable':True}
                        blocked=cleanup_admission(record,sampler_started=sampler_started,
                            runtime_attempted=runtime_attempted,runtime_ready=runtime_ready,
                            runtime_state=runtime_state)
                        record['recoveryMetadata']=dict(image=str(image),mount=str(mount),
                            runtimeState=str(runtime),samplerStarted=sampler_started,
                            runtimeReady=runtime_ready,cleanupAdmissionBlocked=blocked,
                            runtimeStateExists=runtime.exists(),
                            runtimeRestored=runtime_state.get('restored') if runtime_state else None,
                            instruction='On uncertainty retain state; no automatic restart, service stop, forced unmount or retry. Ephemeral runner termination is external to harness.')
                        if blocked: cleanup.append(blocked)
                        if not cleanup and runtime_ready:
                            try: command(['/usr/bin/python3','feasibility/stress_runtime_storage.py','leave','--state',runtime])
                            except Exception as e: cleanup.append(str(e))
                        if mounted and not cleanup:
                            try: command(['umount','-i',mount])
                            except Exception as e: cleanup.append(str(e))
                        record['isolatedImageRetained']=str(image)
                        if cleanup:
                            record.update(correct=False,status='cleanup_blocked',cleanupErrors=cleanup)
                            save();raise RuntimeError('normal cleanup blocked; no forced unmount or deletion')
                        save()
        report.update(complete=True,status='passed')
    except BudgetAbort as error:
        report.update(status='budget_aborted',budgetReason=str(error))
    except Exception as error:
        report.update(status='failed',error=str(error),traceback=traceback.format_exc())
    finally: save()
    print(json.dumps(report))
    return 0 if report['complete'] else (2 if report['status']=='budget_aborted' else 1)

if __name__=='__main__':sys.exit(main())
