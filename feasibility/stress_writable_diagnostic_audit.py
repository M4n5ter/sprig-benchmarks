#!/usr/bin/env python3
"""Exact Python-integer raw diagnostic audit; no workload, retries, or primary-guard changes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
from stress_cargo_ab_summary import require,strict_json,read_regular,digest,finite,validate_sample,verify_archives,pressure_operation_summaries
from stress_cargo_pressure_profiles import experiment_for
from stress_writable_diagnostic_sample import SOURCE_SHA,PARENT_SHA,ALGORITHM_BASE,PRESSURE_SHA,SCHEMA,LOG_CAP,CLOCK_CODE,REPORT_RESERVE_BYTES
from stress_writable_diagnostic_trace import validate_clock_proof,parse_trace_log,analyze_trace

RUN_SCHEMA='sprig-writable-diagnostic-canary-v1'
MANIFEST_SCHEMA='sprig-writable-diagnostic-identity-v1'
ORDER=[('off',0),('on',0),('on',1),('off',1)]
ARTIFACT_CAP=1024**3


def validate_identity(value):
    require(isinstance(value,dict) and set(value)=={'schema','sha','parent','algorithmBase','binary','binarySha256','sourcePath','pressureScriptSha256'},'fixed single-ELF manifest fields required')
    require(value['schema']==MANIFEST_SCHEMA and value['sha']==SOURCE_SHA and value['parent']==PARENT_SHA and value['algorithmBase']==ALGORITHM_BASE and value['pressureScriptSha256']==PRESSURE_SHA,'diagnostic source/helper identity mismatch')
    require(isinstance(value['binarySha256'],str) and re.fullmatch('[a-f0-9]{64}',value['binarySha256']),'binary hash required')
    for name in ('binary','sourcePath'):
        require(isinstance(value[name],str) and Path(value[name]).is_absolute() and str(Path(value[name]))==value[name] and '..' not in Path(value[name]).parts,'canonical identity path required')
    return value


def audit_sample(raw_path,manifest_path,image,protocol_sha,archive_root,arm,pair):
    require((arm,pair) in ORDER and type(pair) is int,'fixed sample identity')
    identity=validate_identity(strict_json(read_regular(manifest_path)));body=read_regular(raw_path);sample=strict_json(body)
    require(sample.get('schema')==SCHEMA and sample.get('diagnosticArm')==arm and sample.get('diagnosticEnvironment')=={'SPRIG_WRITABLE_DIAGNOSTICS':'1' if arm=='on' else None,'SPRIG_LIFECYCLE_TRACE':None},'diagnostic arm/env mismatch')
    require(sample.get('diagnosticSource')=={k:identity[k] for k in ('sha','parent','algorithmBase')},'diagnostic source mismatch')
    product={**identity,'label':arm}
    reference=dict(image=image,protocolSha256=protocol_sha,experimentSpec=experiment_for('normal-rename2-1024-v2'))
    # Reject oversized server logs before the shared whole-archive reader can
    # allocate them; immutable failed bytes still remain with the collector.
    for row in sample.get('completeLogArchive',[]):
        source=row.get('source','');archived=Path(row.get('archived',''))
        if Path(source).name.startswith('writable-') and Path(source).suffix=='.log':
            require(type(row.get('bytes')) is int and 0<=row['bytes']<=LOG_CAP,'complete server log exceeds16MiB')
            require(archived.parts[-3:]==('inc0',f'{arm}-{pair}.jsonl.logs',archived.name),'server archive exact suffix mismatch')
            local=archive_root/'inc0'/f'{arm}-{pair}.jsonl.logs'/archived.name
            require(local.is_file() and not local.is_symlink() and local.stat().st_size<=LOG_CAP,'actual complete server log exceeds16MiB or is unsafe')
    admission=sample.get('diagnosticArchiveAdmission',{});require(admission.get('admitted') is True and admission.get('maximumBytes')==ARTIFACT_CAP and admission.get('reportReserveBytes')==REPORT_RESERVE_BYTES and admission.get('collectionReserveBytes')==2*1024**2,'pre-copy whole-archive admission missing')
    for name in ('existingNamedExternalBytes','plannedArchiveBytes','projectedAdmissionBytes'):
        require(type(admission.get(name)) is int and admission[name]>=0,'invalid archive admission bytes')
    require(admission['projectedAdmissionBytes']==admission['existingNamedExternalBytes']+admission['plannedArchiveBytes']+REPORT_RESERVE_BYTES+2*1024**2 and admission['projectedAdmissionBytes']<=ARTIFACT_CAP,'pre-copy artifact cap predicate failed')
    declared=sample.get('completeLogArchive',[]);planned=admission.get('plannedFiles',[])
    require(isinstance(planned,list) and len(planned)==len(declared) and [{k:r[k] for k in ('source','archived','bytes')} for r in planned]==[{k:r[k] for k in ('source','archived','bytes')} for r in declared] and admission['plannedArchiveBytes']==sum(r['bytes'] for r in declared),'full planned archive and actual copy differ')
    require(sample.get('diagnosticArchiveCopy',{}).get('complete') is True and sample['diagnosticArchiveCopy'].get('completedFiles')==len(declared) and not sample.get('partialLogArchive'),'archive copy incomplete')
    archive_count=validate_sample(sample,reference,product,0,pair,archive_root)
    contents=verify_archives(sample,archive_root,0,arm,pair)
    bindings=sample.get('diagnosticCommandBindings');require(isinstance(bindings,list) and bindings,'missing explicit product env bindings')
    require(all(r.get('arm')==arm and r.get('executable')==identity['binary'] and r.get('environmentValue')==('1' if arm=='on' else None) for r in bindings),'product command environment mismatch')
    proof=validate_clock_proof(sample.get('diagnosticClockProof'))
    clock_rows=[r for r in sample['commands'] if r.get('purpose')=='diagnostic_clock_domain'];pressure_rows=[r for r in sample['commands'] if r.get('purpose')=='normal_pressure']
    require(len(clock_rows)==len(pressure_rows)==1,'clock/pressure command must be unique')
    clock,pressure=clock_rows[0],pressure_rows[0];binding=sample.get('diagnosticClockBinding')
    require(binding=={k:clock[k] for k in ('containerId','workspaceGeneration','stdoutPath')},'clock proof exact command binding mismatch')
    require(all(clock[k]==pressure[k] for k in ('containerId','workspaceGeneration')) and pressure['workspaceGeneration']==sample['checkpointGeneration']['before'],'pressure must bind exact pre-checkpoint generation')
    require(clock.get('returncode')==0 and clock.get('stdinSha256')==digest(CLOCK_CODE.encode()) and contents.get(clock['stdoutPath'])==clock['stdout'].encode(),'clock probe raw output/helper identity missing')
    observed=strict_json(clock['stdout']);require(observed==dict(domain=proof['container'],monotonicNs=proof['containerMonotonicNs']),'clock proof differs from exact raw output')
    require(int(sample['normalPressure']['monotonicOriginNs'])>=proof['hostAfterNs'],'pressure origin predates completed clock sandwich')
    root=Path(sample['root']);require(root.is_absolute(),'absolute sampler root required')
    logs=[]
    for row in sample['completeLogArchive']:
        path=Path(row['source'])
        if path.name.startswith('writable-') and path.suffix=='.log':
            require(path.parent.parent==root/'library/native' and re.fullmatch(r'writable-[0-9]+-[0-9]+\.log',path.name),'server log outside exact native generation')
            require(row['bytes']<=LOG_CAP,'complete server log exceeds16MiB; no truncation')
            logs.append(row)
    require(len(logs)==5 and len({r['source'] for r in logs})==5 and len({Path(r['source']).parent.name for r in logs})==4,'expected exactly five complete writable server logs across four generations')
    post=sample.get('postNormalCleanupSpace',{});require(post.get('deviceBytes')==4*1024**3 and type(post.get('availableBytes')) is int and post['availableBytes']>=128*1024**2,'post-cleanup4GiB/reserve proof missing')
    require(finite(post.get('filesystemUsedBytes'),'post-cleanup physical Used')<=4*1024**3 and post['availableBytes']<=4*1024**3,'post-cleanup physical bounds changed')
    source_logs=post.get('sourceLogs');require(isinstance(source_logs,list) and len(source_logs)==5,'post-cleanup source log inventory missing')
    require({r['source'] for r in source_logs}=={r['source'] for r in logs},'source/archive server log inventory differs')
    by_source={r['source']:r for r in source_logs}
    for row in logs:
        src=by_source[row['source']]
        require(src.get('bytes')==row['bytes'] and src.get('sha256')==row['sha256'] and type(src.get('allocatedBytes')) is int and src['allocatedBytes']>=0,'source/archive size/hash/allocation mismatch')
    require(post.get('sourceLogLogicalBytes')==sum(r['bytes'] for r in logs) and post.get('sourceLogAllocatedBytes')==sum(r['allocatedBytes'] for r in source_logs),'source log charge mismatch')
    parsed={r['source']:parse_trace_log(contents[r['source']],enabled=arm=='on') for r in logs}
    if arm=='on':
        for trace in parsed.values():
            events=trace['events'];require(events and events[-1]['operation']=='journal_sync' and events[-1]['success'] is True and all(e['success'] for e in events if e['operation']=='journal_sync'),'every enabled log must reflect successful normal destroy without any failed sync')
    generation=sample['checkpointGeneration']['before'];selected=[r for r in logs if Path(r['source']).parent.name==generation]
    require(len(selected)==1,'exactly one pressure-generation server log required')
    selected=selected[0];analysis=analyze_trace(parsed[selected['source']],sample['normalPressure']) if arm=='on' else None
    metrics={'wholeInternalSeconds':sample['full_task_seconds'],'activeWholeFilesystemBytes':sample['activeSpace']['filesystemUsedBytes'],'postCleanupWholeFilesystemBytes':post['filesystemUsedBytes'],'sourceLogLogicalBytes':post['sourceLogLogicalBytes'],'sourceLogAllocatedBytes':post['sourceLogAllocatedBytes']}
    metrics.update({'phase.'+k:finite(v,'phase '+k) for k,v in sample['phase_seconds'].items()})
    metrics.update({'transport.'+k:finite(v,'transport '+k) for k,v in sample['transport_seconds'].items()})
    pressure=sample['normalPressure'];workers=pressure['workers']
    metrics['wrapperLoop.unionWindowSeconds']=(max(w['finishedNs'] for w in workers)-min(w['startedNs'] for w in workers))/1e9
    metrics['wrapperLoop.lifetimeOverlapSeconds']=pressure['workerLifetimeOverlapNs']/1e9
    for worker in workers:metrics[f"wrapperLoop.worker{worker['worker']}Seconds"]=(worker['finishedNs']-worker['startedNs'])/1e9
    intervals=[e for worker in workers for e in worker['operationIntervals']]
    metrics['wrapperOperation.windowSeconds']=(max(e['endNs'] for e in intervals)-min(e['startNs'] for e in intervals))/1e9
    operations=pressure_operation_summaries(sample)
    for op,stats in operations.items():
        for name,value in stats.items():
            if type(value) in (int,float) and name not in ('n',):metrics['operation.'+op+'.'+name]=finite(value,name)
    return dict(schema='sprig-writable-diagnostic-sample-audit-v1',correct=True,arm=arm,pair=pair,rawReportSha256=digest(body),manifestSha256=digest(read_regular(manifest_path)),sourceSha=identity['sha'],binarySha256=identity['binarySha256'],archiveFilesVerified=archive_count,serverLogs=5,pressureGeneration=generation,pressureServerLog={k:selected[k] for k in ('source','archived','bytes','sha256')},clockJoin='exact Python u64 integers; verified common namespace/offsets and sandwich',analysis=analysis,metrics=metrics,notes=['Wrapper/scoped wall overlap is not causality or request ownership. CPU sums use only fully contained scopes, never clipped prorating.','Two pairs only; no significance/equivalence/stable overhead claim. Original untraced series remains separate.'])


def summarize(run_path,manifest_path,archive_root):
    run=strict_json(read_regular(run_path));identity=validate_identity(strict_json(read_regular(manifest_path)))
    out=dict(schema='sprig-writable-diagnostic-canary-summary-v1',complete=False,expectedSamples=4,records=[],errors=[],comparisons=None,automaticRetry=False,automaticFallback=False,automaticPromotion=False,sourceStatus=run.get('status'),sourceError=run.get('error'),attemptedRecords=run.get('records',[]),notRun=run.get('notRun',[]))
    try:
        require(run.get('schema')==RUN_SCHEMA and run.get('identity')==identity and run.get('identitySha256')==digest(read_regular(manifest_path)),'diagnostic manifest/run identity mismatch')
        require(type(run.get('expectedRecords')) is int and run['expectedRecords']==4 and type(run.get('incremental')) is int and run['incremental']==0 and run.get('imageBytes')==4*1024**3 and run.get('order')==[dict(arm=a,pair=p) for a,p in ORDER] and run.get('artifactBudgetBytes')==ARTIFACT_CAP,'finite canary shape/resources changed')
        budget=run.get('sharedJobBudget',{});start=finite(budget.get('startedEpochSeconds'),'job start',True);deadline=finite(budget.get('deadlineEpochSeconds'),'job deadline',True)
        require(0<deadline-start<=2400 and budget.get('minimumSampleSeconds')==180 and budget.get('cleanupReserveSeconds')==300,'absolute admission deadline/reserves changed')
        require(run.get('notRun')==[],'complete report still has not-run samples')
        require(run.get('complete') is True and run.get('status')=='passed' and len(run.get('records',[]))==4,'incomplete/failed canary; preserve remaining not-run samples')
        for index,(arm,pair) in enumerate(ORDER):
            row=run['records'][index];require(row.get('arm')==arm and type(row.get('pair')) is int and row['pair']==pair and row.get('correct') is True and type(row.get('sampleReturncode')) is int and row['sampleReturncode']==0 and not row.get('cleanupErrors'),'sample failed/order changed')
            for name in ('budgetAdmission','postRuntimeBudgetAdmission'):
                gate=row.get(name,{});require(gate.get('startedEpochSeconds')==start and gate.get('deadlineEpochSeconds')==deadline and gate.get('admitted') is True and gate.get('workReserveSeconds')==180 and gate.get('cleanupReserveSeconds')==300 and gate.get('requiredSeconds')==480 and finite(gate.get('remainingSeconds'),'remaining job budget')>=480,'sample admission budget proof missing/changed')
            capacity=row.get('capacityAdmission',{})
            for key in ('availableBytes','requiredBytes','deviceBytes','targetAllocatedBytes','fixtureLogicalBytes','pressureReserveBytes'):
                require(type(capacity.get(key)) is int and capacity[key]>=0,'invalid capacity proof '+key)
            required=max(512*1024**2,4*capacity['targetAllocatedBytes']+8*capacity['fixtureLogicalBytes']+256*1024**2)+128*1024**2
            require(capacity['deviceBytes']==4*1024**3 and capacity['targetAllocatedBytes']>0 and capacity['pressureReserveBytes']==128*1024**2 and capacity['requiredBytes']==required and capacity['availableBytes']>=required and capacity.get('admitted') is True,'capacity admission predicate changed')
            inventory=row.get('postSampleArtifactInventory',{})
            require(type(inventory.get('bytes')) is int and inventory['bytes']>=0 and inventory.get('collectionReserveBytes')==2*1024**2 and inventory.get('admissionBytes')==inventory['bytes']+2*1024**2 and inventory['admissionBytes']<=ARTIFACT_CAP and inventory.get('maximumBytes')==ARTIFACT_CAP and inventory.get('completeNamedInventory') is True,'artifact inventory/cap predicate changed')
            name=f'stress-writable-diagnostic-{arm}-{pair}.json';require(row.get('rawReportPath')=='results/'+name,'fixed raw report name required')
            audit=audit_sample(run_path.parent/name,manifest_path,run['image'],run['protocolSha256'],archive_root,arm,pair)
            require(audit['rawReportSha256']==row.get('rawReportSha256'),'raw sample hash changed')
            audit['metrics']['wholeSampleSeconds']=finite(row.get('wholeSampleSubprocessWallSeconds'),'whole subprocess',True);out['records'].append(audit)
        indexed={(r['arm'],r['pair']):r for r in out['records']};keys=set(out['records'][0]['metrics']);require(all(set(r['metrics'])==keys for r in out['records']),'metric sets differ')
        fields={}
        for name in sorted(keys):
            pairs=[]
            for p in range(2):
                off=indexed['off',p]['metrics'][name];on=indexed['on',p]['metrics'][name];ratio=on/off if off>0 else None
                pairs.append(dict(pair=p,order='off/on' if p==0 else 'on/off',off=off,on=on,onOverOff=ratio,percentChange=(ratio-1)*100 if ratio is not None else None))
            ratios=[r['onOverOff'] for r in pairs];fields[name]=dict(pairs=pairs,medianPairedRatio=statistics.median(ratios) if all(r is not None for r in ratios) else None,n=2,p95=None,p99=None)
        out.update(complete=True,comparisons=fields)
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:out['errors'].append(str(error))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    one=sub.add_parser('sample');one.add_argument('--sample',type=Path,required=True);one.add_argument('--arm',choices=['off','on'],required=True);one.add_argument('--pair',type=int,choices=[0,1],required=True);one.add_argument('--image',required=True);one.add_argument('--protocol-sha',required=True)
    all_=sub.add_parser('summary');all_.add_argument('--report',type=Path,required=True)
    for x in (one,all_):
        for key in ('manifest','archive-root','output'):x.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    try:result=audit_sample(a.sample,a.manifest,a.image,a.protocol_sha,a.archive_root,a.arm,a.pair) if a.command=='sample' else summarize(a.report,a.manifest,a.archive_root)
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:result=dict(correct=False,complete=False,error=str(error))
    encoded=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode();limit=(1 if a.command=='sample' else 16)*1024**2
    require(len(encoded)<=limit,'diagnostic audit/summary exceeds explicit reserved output bound; no write')
    with a.output.open('xb') as f:f.write(encoded)
    print(json.dumps({'complete':result.get('correct',result.get('complete',False)),'output':str(a.output),'error':result.get('error',result.get('errors'))}))
    sys.exit(0 if result.get('correct',result.get('complete',False)) else 1)
