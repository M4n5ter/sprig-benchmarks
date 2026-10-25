#!/usr/bin/env python3
"""Run one exact-backend full-tree canary and one approved cell under ONE budget.
No retries, process timeout/kill, pruning, or completion claim after a budget abort.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from verify_stress_artifact import verify


def phase_budget(remaining, canary):
    # Keep30seconds for sequence evidence, in addition to child normal-cleanup
    # admission reserve. The child itself caps each operation/sample start.
    available=int(remaining)-30
    if available<60: raise ValueError('insufficient remaining shared budget')
    return min(300 if canary else 1200,available)


def validate_backend(proof, backend):
    if any(r['backend']!=backend for r in proof['records']):
        raise ValueError('measured backend differs from requested backend')


def validate_canary(root, products, backend):
    proof=verify(root)
    validate_backend(proof,backend)
    if proof['diagnostic'] or len(proof['records'])!=len(products):
        raise ValueError('unexpected canary product/diagnostic count')
    if proof['sourcePins']!={p['label']:p['sha'] for p in products}:
        raise ValueError('canary source pins differ from pressure binaries')
    if any(r['backend']!=backend or r['fullTreeChecks']!=15 or r['historicalReadbacks']!=4 for r in proof['records']):
        raise ValueError('canary full-tree or restore gate incomplete')
    return proof


def validate_native_canary(root, products):
    return validate_canary(root,products,'native')


def binary_hashes(products):
    return {p['label']:hashlib.sha256(Path(p['binary']).read_bytes()).hexdigest() for p in products}


def validate_binary_identity(proof, expected):
    actual={r['product']:r['binarySha256'] for r in proof['records']}
    if actual != expected:
        raise ValueError('measured binary hashes differ from frozen sequence identities')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--products',type=Path,required=True)
    p.add_argument('--cell',choices=['cache-history-repeated-300','files-10000','files-4096','history-hot-100'],required=True)
    p.add_argument('--backend',choices=['native','writable'],default='native')
    p.add_argument('--pair-order',choices=['forward','reverse'],default='forward')
    p.add_argument('--budget-seconds',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not 60<=a.budget_seconds<=1200: p.error('shared budget must be60..1200seconds')
    if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true': p.error('authorized root GitHub runner only')
    temp=Path(os.environ.get('RUNNER_TEMP',''))
    if not temp.is_absolute() or not a.output.is_absolute() or not a.output.is_relative_to(temp) or a.output==temp:
        p.error('output strictly belowRUNNER_TEMP required')
    products=json.loads(a.products.read_text())
    if len(products)!=2 or any(x['type']!='sprig' or x.get('diagnostic') for x in products):
        p.error('exact two primary Sprig binary configs required')
    a.output.mkdir(parents=True,exist_ok=False)
    frozen_hashes=binary_hashes(products)
    frozen_config=a.products.read_bytes()
    start=time.monotonic();deadline=start+a.budget_seconds
    report=dict(schema='sprig-stress-sequence-v1',status='running',complete=False,
                sharedBudgetSeconds=a.budget_seconds,cell=a.cell,backend=a.backend,pairOrder=a.pair_order,
                products=products,binarySha256=frozen_hashes,phases=[])
    def save():
        report['elapsedSeconds']=time.monotonic()-start
        (a.output/'sequence.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        for label,cell in [('canary','canary'),('pressure',a.cell)]:
            if a.products.read_bytes()!=frozen_config or binary_hashes(products)!=frozen_hashes:
                raise ValueError('configured product binaries changed between sequence phases')
            try: budget=phase_budget(deadline-time.monotonic(),label=='canary')
            except ValueError as error:
                report.update(status='budget_aborted',error=str(error));break
            phase=a.output/label;phase.mkdir()
            args=[sys.executable,str(Path(__file__).with_name('stress_run.py')),'--products',str(a.products),
                  '--cell',cell,'--backend',a.backend,'--rounds','1','--pair-order',a.pair_order,
                  '--budget-seconds',str(budget),'--output',str(phase/'stress-results')]
            row=dict(phase=label,cell=cell,budgetSeconds=budget,startedAfterSeconds=time.monotonic()-start)
            report['phases'].append(row);save()
            print(f'Starting {label}: {cell}; shared-budget allocation {budget}s',flush=True)
            proc=subprocess.run(args,capture_output=True,text=True,check=False)
            (phase/'driver-stdout.json').write_text(proc.stdout);(phase/'driver-stderr.txt').write_text(proc.stderr)
            row['returncode']=proc.returncode
            if proc.returncode:
                report.update(status='budget_aborted' if proc.returncode==2 else 'failed',error=f'{label} incomplete; no later phase started')
                save();break
            if label=='canary': proof=validate_canary(phase,products,a.backend)
            else: proof=verify(phase)
            validate_backend(proof,a.backend)
            validate_binary_identity(proof,frozen_hashes)
            (phase/'verified.json').write_text(json.dumps(proof,indent=2)+'\n')
            row.update(verified=True,fullTreeChecks=proof['totalFullTreeChecks'],historicalReadbacks=proof['totalHistoricalReadbacks'])
            save()
        else: report.update(complete=True,status='passed')
    except Exception as error:
        report.update(status='failed',error=str(error))
    finally: save()
    print(json.dumps(report))
    return 0 if report['complete'] else (2 if report['status']=='budget_aborted' else 1)

if __name__=='__main__':sys.exit(main())
