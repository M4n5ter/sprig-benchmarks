#!/usr/bin/env python3
"""Audit all three-pin screening samples before any within-round ratio is emitted."""
import argparse
import json
import math
import re
from pathlib import Path
import statistics
from stress_cache_ablation import SCHEMA,PINS,order,regular,digest,require,validate_sample,validate_canary
from stress_cache_fixture import CACHE_CELLS,cache_cell_parameters
from stress_stats import latency_summary


def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0


def summarize(path,canary_path=None):
    out=dict(schema='sprig-stress-cache-ablation-summary-v1',complete=False,status='incomplete',expectedSamples=9,records=[],errors=[],comparisons=None,
             notes=['Three Latin rounds are a small-N screen, not significance or promotion; reverse-Latin confirmation is separately reviewed.',
                    'Each source pin appears once per round and once per position; compare main→inventory, inventory→admission and main→admission separately.',
                    'Whole Used includes retained trees/cache/history; no empty-image subtraction. Timers overlap and must not be added.',
                    'History p95/p99 describe dependent operations within one sample, not independent trial counts. All samples and regressions retained.'])
    try:
        require(canary_path is not None,'complete raw canary evidence is required for any ratios')
        raw=regular(path).read_bytes();report=json.loads(raw);out['reportSha256']=digest(raw)
        out['sourceStatus']=report.get('status');out['sourceError']=report.get('error',report.get('budgetReason'))
        require(report.get('schema')==SCHEMA and report.get('ablationStage')=='forward-latin','requires explicit forward-Latin screen')
        require(report.get('cell') in CACHE_CELLS and report.get('backends')==['native'] and report.get('rounds')==3 and report.get('expectedRecords')==9,'screen shape mismatch')
        require(report.get('complete') is True and report.get('status')=='passed','screen incomplete or failed')
        out['cell']=report['cell'];out['products']=report['products']
        require(isinstance(report['products'],list) and all(isinstance(p,dict) for p in report['products']) and [p.get('label') for p in report['products']]==list(PINS),'screen labels mismatch')
        for p in report['products']:
            require(p.get('sha')==PINS[p['label']] and p.get('type')=='sprig','screen source pin mismatch')
            require(isinstance(p.get('binarySha256'),str) and re.fullmatch('[a-f0-9]{64}',p['binarySha256']),'invalid binary hash')
        require(len({p['binarySha256'] for p in report['products']})==3,'binary identities must be distinct')
        budget=report.get('sharedAblationBudget',{})
        a,b,c,d=(budget.get(k) for k in ('jobStartedEpochSeconds','jobDeadlineEpochSeconds','measurementStartedEpochSeconds','measurementDeadlineEpochSeconds'))
        require(all(type(v) is int for v in (a,b,c,d)) and 0<a<=c<d<=b and b-a<=2400 and d-c<=1200 and budget.get('maximumMeasurementSeconds')==1200,'screen resource deadline mismatch')
        prerequisite=report.get('canaryPrerequisite');require(isinstance(prerequisite,dict) and isinstance(prerequisite.get('sha256'),str) and len(prerequisite['sha256'])==64,'missing canary prerequisite')
        if canary_path is not None:
            canary=validate_canary(canary_path,report['products'],budget)
            require(canary['sha256']==prerequisite['sha256'],'screen prerequisite no longer binds exact canary report')
        fixture=json.loads((path.parent/'fixture.json').read_text());require(digest(json.dumps(fixture).encode())==report['fixtureSha256'],'fixture bytes identity mismatch')
        params,noop=cache_cell_parameters(report['cell']);params.setdefault('symlink',False);require(fixture['parameters']==params and report['noopCheckpoint'] is noop,'fixed fixture recipe mismatch')
        rows=report.get('records');require(isinstance(rows,list) and len(rows)==9,'all nine planned records required')
    except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError) as error:
        out['errors'].append(str(error))
        report=locals().get('report',{})
        rows=report.get('records',[]) if isinstance(report,dict) else []
        fixture=locals().get('fixture');noop=locals().get('noop')
    for index,row in enumerate(rows if isinstance(rows,list) else []):
        audit={'index':index};out['records'].append(audit)
        try:
            require(isinstance(row,dict),'invalid record')
            for key in ('identity','product','round','correct','status','sampleReturncode','cleanupErrors','recoveryMetadata'):
                if key in row:audit[key]=row[key]
            require(index<9 and type(row.get('round')) is int and row.get('round')==index//3 and row.get('product')==order(report['products'],index//3,'forward-latin')[index%3]['label'],'record Latin order mismatch')
            require(row.get('correct') is True and row.get('status')=='passed' and row.get('sampleReturncode')==0 and not row.get('cleanupErrors'),'failed screen sample')
            identity=f"native-{row['product']}-{row['round']}";require(row.get('identity')==identity,'sample identity mismatch')
            body=regular(path.parent/(identity+'-stdout.json')).read_bytes();require(digest(body)==row.get('rawReportSha256'),'standalone raw sample hash mismatch')
            sample=json.loads(body);product=next(p for p in report['products'] if p['label']==row['product'])
            audit['proof']=validate_sample(sample,product,fixture,noop,report['fixtureSha256'],path.parent,identity,report['outputDirectory'])
            require(row.get('sample')==sample,'embedded/raw exact native sample differs')
            values={'wholeSampleSeconds':row['wholeSampleSubprocessWallSeconds'],'activeWholeFilesystemBytes':sample['activeSpace']['filesystemUsedBytes'],'postHistoryWholeFilesystemBytes':sample['postHistorySpace']['filesystemUsedBytes']}
            values.update({key:value for key,value in sample.items() if key.endswith('_seconds')})
            # The inherited production schema explicitly omits this probe; it
            # is not a measured zero and must stay visible outside comparisons.
            audit['notMeasured']={}
            if 'metadata_branch_seconds' in values and (values['metadata_branch_seconds'] is None or sample.get('metadata_branch_probe')=='omitted'):
                require(values['metadata_branch_seconds'] is None and sample.get('metadata_branch_available') is True and sample.get('metadata_branch_probe')=='omitted' and sample.get('metadata_branch_unavailable_reason') is None,'invalid omitted metadata-branch marker')
                audit['notMeasured']['metadata_branch_seconds']={'value':None,'reason':'production metadata_branch_probe explicitly omitted'}
                del values['metadata_branch_seconds']
            require(all(finite(value) for value in values.values()),'invalid measured metric')
            audit['metrics']=values
            for source,key in [('checkpoint_steps','checkpoint_seconds'),('historical_restore_steps','restore_seconds')]:
                operations=[r[key] for r in sample[source] if not r.get('noop')]
                audit[source+'DescriptiveTails']=latency_summary(operations) if operations else None
        except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError,StopIteration) as error:
            audit['validationError']=str(error);out['errors'].append(f'record{index}: {error}')
    if out['errors']:return out
    indexed={(r['round'],r['product']):r for r in out['records']};metrics=set(out['records'][0]['metrics'])
    if any(set(r['metrics'])!=metrics for r in out['records']):out['errors'].append('metric set differs');return out
    comparisons={}
    for baseline,candidate in [('main','inventory'),('inventory','admission'),('main','admission')]:
        fields={}
        for name in sorted(metrics):
            pairs=[]
            for round_no in range(3):
                b=indexed[round_no,baseline]['metrics'][name];c=indexed[round_no,candidate]['metrics'][name];ratio=c/b if b>0 else None
                pairs.append(dict(round=round_no,baseline=b,candidate=c,candidateOverBaseline=ratio,percentChange=(ratio-1)*100 if ratio is not None else None))
            ratios=[p['candidateOverBaseline'] for p in pairs];valid=all(r is not None and r>0 for r in ratios)
            fields[name]=dict(pairs=pairs,medianPairedRatio=statistics.median(ratios) if all(r is not None for r in ratios) else None,
                              geometricMeanPairedRatio=math.exp(statistics.mean(math.log(r) for r in ratios)) if valid else None,
                              baselineValues=[p['baseline'] for p in pairs],candidateValues=[p['candidate'] for p in pairs],n=3,p95=None,p99=None)
        comparisons[baseline+'-to-'+candidate]=fields
    out.update(complete=True,status='passed',comparisons=comparisons)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--canary-report',type=Path,required=True);a=p.parse_args()
    result=summarize(a.report,a.canary_report)
    with a.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'complete':result['complete'],'status':result['status'],'records':len(result['records']),'errors':result['errors']}))
    raise SystemExit(0 if result['complete'] else 1)
