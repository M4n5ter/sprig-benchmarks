#!/usr/bin/env python3
"""Fixed three-pin native screening gates; never weakens legacy paired guards."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from stress_fixture import expected_after

SCHEMA='sprig-stress-cache-ablation-v1'
PINS={'main':'b300693e01c652c1a9631c61b7a439892d8f75cd',
      'inventory':'c392d45079314cdcf9813371ec9120d78be7bcd6',
      'admission':'f481aaba987d960bf119e95b68f5b38da56e1581'}
STAGES=('canary','forward-latin','reverse-latin')
CANARY_PARAMETERS=dict(files=16,size=4096,depth=4,width=4,links=4,steps=3,pattern='hot',symlink=True)

def require(ok,message):
    if not ok:raise ValueError(message)

def digest(body):return hashlib.sha256(body).hexdigest()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()

def regular(path,executable=False):
    p=Path(path)
    require(p.is_absolute() and p.resolve(strict=True)==p and p.is_file() and not p.is_symlink(),'canonical regular file required')
    require(not executable or os.access(p,os.X_OK),'executable required')
    return p

def verify_products(products):
    require(isinstance(products,list) and len(products)==3,'exactly three ablation pins required')
    require(all(isinstance(p,dict) for p in products) and [p.get('label') for p in products]==list(PINS),'fixed ordered ablation labels required')
    for p in products:
        require(set(p)=={'label','type','sha','binary','binarySha256','sourcePath'},'unexpected ablation product fields')
        require(p['type']=='sprig' and p['sha']==PINS[p['label']],'fixed Sprig source pin required')
        binary=regular(p['binary'],True);require(re.fullmatch('[a-f0-9]{64}',p['binarySha256']) and digest(binary.read_bytes())==p['binarySha256'],'binary identity mismatch')
        source=Path(p['sourcePath']);require(source.is_absolute() and source.resolve(strict=True)==source and source.is_dir() and not source.is_symlink(),'canonical source directory required')
        require(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==p['sha'],'source checkout pin mismatch')
        require(subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()=='','source checkout changed')
    for name in ('binary','binarySha256','sourcePath'):
        require(len({p[name] for p in products})==3,'distinct '+name+' required')
    return products

def order(products,round_no,stage):
    require(stage in STAGES,'unknown ablation stage')
    require(type(round_no) is int and 0<=round_no<(1 if stage=='canary' else 3),'invalid ablation round')
    labels=list(PINS)
    if stage=='reverse-latin':labels.reverse()
    labels=labels[round_no:]+labels[:round_no]
    by_label={p['label']:p for p in products}
    return [by_label[label] for label in labels]

def validate_selection(stage,backend,rounds,cell,allowed_cells,pair_order):
    require(stage in STAGES and backend=='native' and pair_order=='forward','ablation is explicit native-only Latin order')
    require(type(rounds) is int and rounds==(1 if stage=='canary' else 3),'ablation requires exactly one canary or three Latin rounds')
    require(cell=='canary' if stage=='canary' else cell in allowed_cells,'unreviewed ablation cell/stage')

def shared_budget(environ,now):
    names={'jobStartedEpochSeconds':'STRESS_CACHE_JOB_STARTED_EPOCH','jobDeadlineEpochSeconds':'STRESS_CACHE_JOB_DEADLINE_EPOCH',
           'measurementStartedEpochSeconds':'STRESS_CACHE_MEASURE_STARTED_EPOCH','measurementDeadlineEpochSeconds':'STRESS_CACHE_MEASURE_DEADLINE_EPOCH'}
    values={key:int(environ[name]) for key,name in names.items()}
    a,b,c,d=[values[k] for k in names]
    require(0<a<b and b-a<=2400,'job deadline must fit40minutes inside45minute workflow')
    require(a<=c<d<=b and d-c<=1200,'one shared measurement deadline must fit1200seconds and original job deadline')
    require(isinstance(now,(int,float)) and math.isfinite(now),'invalid clock')
    values.update(maximumMeasurementSeconds=1200,remainingSeconds=d-now)
    return values

def expected_oracles(fixture,noop):
    operations=len(fixture['edits'])+int(noop)
    initial=digest(canonical(fixture['initial']))
    expected={name:initial for name in ('source-setup','main-initial','work-initial','second-initial')}
    for prefix in ('checkpoint','restore'):
        for ordinal in range(1,operations+1):
            expected[f'{prefix}-{ordinal}']=digest(canonical(expected_after(fixture,ordinal-int(noop))))
    expected.update({name:initial for name in ('source-unchanged','main-unchanged','second-unchanged')})
    return expected

def validate_sample(sample,product,fixture,noop,fixture_sha,results,identity,original_results=None):
    require(isinstance(sample,dict),'missing native sample')
    for flag in ('ok','exactMetadataOracle','originalMainViewUnchanged','originalSecondViewUnchanged','sourceUnchanged','allAcknowledgedIdsPresent'):
        require(sample.get(flag) is True,'native correctness gate failed: '+flag)
    require(sample.get('status')=='passed','native sample status incomplete')
    require(sample.get('backend')=='native' and sample.get('production_sha')==product['sha'] and sample.get('binarySha256')==product['binarySha256'],'native sample source/binary/backend mismatch')
    require(sample.get('fixtureSha256')==fixture_sha,'native sample fixture mismatch')
    capacity=sample.get('capacityPreflight',{})
    require(capacity.get('filesystemBytes')==2*1024**3 and capacity.get('reserveBytes')==256*1024**2 and 0<=capacity.get('retainedEstimateBytes',-1)<=1024**3,'native capacity geometry changed')
    require(sample.get('diagnostic') is False and sample.get('instrumentation')=='off' and sample.get('lifecycleTraceEvidence',{}).get('validRecords')==0,'instrumented cache run refused')
    require(sample.get('remainingMounts')==[] and sample.get('lifecycle',{}).get('cleanup',{}).get('complete') is True and sample['lifecycle'].get('daemons')==[],'normal native cleanup unconfirmed')
    operations=len(fixture['edits'])+int(noop)
    require(sample.get('fullHistoricalSnapshotReadbacks')==operations and sample.get('expectedCheckpointOperations')==operations and sample.get('checkpointOperationCount')==operations,'native historical readback count mismatch')
    expected=expected_oracles(fixture,noop);checks=sample.get('fullTreeChecks')
    require(isinstance(checks,list) and [c.get('label') for c in checks]==list(expected),'full-tree check set/order mismatch')
    archive=sample.get('completeLogArchive');require(isinstance(archive,list) and archive,'native archive missing')
    snapshots={};names=set();directory=Path(original_results or results)/(identity+'-steps.jsonl.logs')
    for item in archive:
        path=Path(item['archived']);require(path.parent==directory and re.fullmatch(r'[A-Za-z0-9_.-]+',path.name),'archive outside exact native sample')
        require(path.name not in names,'duplicate native archive declaration');names.add(path.name)
        body=regular(Path(results)/directory.name/path.name).read_bytes();require(type(item.get('bytes')) is int and len(body)==item['bytes'] and digest(body)==item.get('sha256'),'native archive bytes/hash mismatch')
        match=re.fullmatch(r'\d{6}-oracle-(\d{6})\.json',path.name)
        if match:
            index=int(match[1]);require(index not in snapshots,'duplicate full-tree oracle archive');snapshots[index]=json.loads(body)
    require(set(snapshots)==set(range(len(checks))),'complete raw oracle set missing')
    for index,check in enumerate(checks):
        require(check.get('verified') is True and check.get('oracleSha256')==expected[check['label']],'declared full-tree oracle mismatch')
        require(digest(canonical(snapshots[index]))==expected[check['label']],'raw exact-ns/content/hardlink oracle mismatch')
    return {'fullTreeChecks':len(checks),'historicalReadbacks':operations,'archivedFilesVerified':len(archive)}

def validate_canary(path,products,budget,*,schema=SCHEMA):
    path=regular(path);raw=path.read_bytes();report=json.loads(raw)
    require(report.get('schema')==schema and report.get('ablationStage')=='canary' and report.get('cell')=='canary','exact ablation canary required')
    require(report.get('complete') is True and report.get('status')=='passed' and report.get('rounds')==1 and report.get('backends')==['native'],'native canary incomplete')
    require(report.get('products')==products,'canary source/binary identities differ')
    require(report.get('noopCheckpoint') is True and report.get('expectedRecords')==3,'canary exact no-op/count contract changed')
    for key in ('jobStartedEpochSeconds','jobDeadlineEpochSeconds','measurementStartedEpochSeconds','measurementDeadlineEpochSeconds','maximumMeasurementSeconds'):
        require(report.get('sharedAblationBudget',{}).get(key)==budget[key],'canary shared deadline changed')
    fixture=json.loads((path.parent/'fixture.json').read_text());require(digest(json.dumps(fixture).encode())==report.get('fixtureSha256'),'canary fixture bytes identity mismatch');rows=report.get('records')
    require(fixture.get('parameters')==CANARY_PARAMETERS,'fixed canary fixture recipe changed')
    require(isinstance(rows,list) and len(rows)==3,'all three canaries required')
    for row,p in zip(rows,products):
        require(isinstance(row,dict) and row.get('identity')==f"native-{p['label']}-0" and not row.get('cleanupErrors'),'canary identity/cleanup mismatch')
        require(row.get('product')==p['label'] and row.get('round')==0 and row.get('correct') is True and row.get('status')=='passed' and row.get('sampleReturncode')==0,'canary record failed/order mismatch')
        sample_path=path.parent/(row['identity']+'-stdout.json');sample_bytes=regular(sample_path).read_bytes()
        require(digest(sample_bytes)==row.get('rawReportSha256'),'canary exact raw hash mismatch')
        sample=json.loads(sample_bytes);require(row.get('sample')==sample,'canary embedded/raw sample differs')
        proof=validate_sample(sample,p,fixture,True,report['fixtureSha256'],path.parent,row['identity'],report.get('outputDirectory'))
        require(proof['fullTreeChecks']==15 and proof['historicalReadbacks']==4,'canary full-tree/history contract changed')
    return {'path':str(path),'sha256':digest(raw)}
