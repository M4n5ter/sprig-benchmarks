"""Offline fixed-pin/order/deadline/full-evidence gates; no mount or Rust."""
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import stress_cache_ablation as a
from stress_fixture import generate,expected_after
from stress_cache_fixture import CACHE_CELLS
from stress_run import validate_products


def sample_fixture(root,product=None,identity='native-main-0',params=None):
    product=product or dict(label='main',sha=a.PINS['main'],binarySha256='a'*64)
    source=root/'source';fixture=generate(source,**(params or dict(files=4,size=1024,width=1,steps=1)))
    results=root/'stress-results';results.mkdir();directory=results/(identity+'-steps.jsonl.logs');directory.mkdir()
    digest=a.digest(json.dumps(fixture).encode());checks=[];archive=[]
    for index,(label,expected_hash) in enumerate(a.expected_oracles(fixture,True).items()):
        count=max(0,int(label.split('-')[-1])-1) if label.startswith(('checkpoint-','restore-')) else 0
        value=expected_after(fixture,count);body=json.dumps(value).encode();path=directory/f'{index:06d}-oracle-{index:06d}.json';path.write_bytes(body)
        archive.append(dict(source='/original/'+path.name,archived=str(path),bytes=len(body),sha256=a.digest(body)))
        checks.append(dict(label=label,verified=True,oracleSha256=expected_hash))
    sample={key:True for key in ('ok','exactMetadataOracle','originalMainViewUnchanged','originalSecondViewUnchanged','sourceUnchanged','allAcknowledgedIdsPresent')}
    sample.update(status='passed',backend='native',production_sha=product['sha'],binarySha256=product['binarySha256'],fixtureSha256=digest,
                  capacityPreflight=dict(filesystemBytes=2*1024**3,reserveBytes=256*1024**2,retainedEstimateBytes=28*1024),
                  diagnostic=False,instrumentation='off',lifecycleTraceEvidence={'validRecords':0},remainingMounts=[],lifecycle={'cleanup':{'complete':True},'daemons':[]},
                  fullHistoricalSnapshotReadbacks=len(fixture['edits'])+1,expectedCheckpointOperations=len(fixture['edits'])+1,checkpointOperationCount=len(fixture['edits'])+1,fullTreeChecks=checks,completeLogArchive=archive,
                  activeSpace={'filesystemUsedBytes':1000000},postHistorySpace={'filesystemUsedBytes':2000000},restore_seconds=10.0,checkpoint_seconds=2.0,
                  checkpoint_steps=[{'noop':True,'checkpoint_seconds':1},{'noop':False,'checkpoint_seconds':1}],historical_restore_steps=[{'restore_seconds':5},{'restore_seconds':5}])
    return sample,product,fixture,digest,results


def canary_fixture(root,products,budget):
    results=root/'stress-results';results.mkdir(parents=True)
    report=dict(schema=a.SCHEMA,ablationStage='canary',cell='canary',backends=['native'],rounds=1,expectedRecords=3,complete=True,status='passed',products=products,records=[],noopCheckpoint=True,sharedAblationBudget=budget,outputDirectory=str(results))
    for product in products:
        identity=f"native-{product['label']}-0";part=root/identity;part.mkdir()
        sample,_,source,sha,original=sample_fixture(part,product,identity,a.CANARY_PARAMETERS)
        logs=original/(identity+'-steps.jsonl.logs');shutil.move(str(logs),str(results/logs.name))
        for item in sample['completeLogArchive']:item['archived']=str(results/logs.name/Path(item['archived']).name)
        raw=json.dumps(sample).encode();(results/(identity+'-stdout.json')).write_bytes(raw)
        report['records'].append(dict(identity=identity,product=product['label'],round=0,correct=True,status='passed',sampleReturncode=0,sample=sample,rawReportSha256=a.digest(raw)))
        report['fixtureSha256']=sha
    (results/'fixture.json').write_text(json.dumps(source,indent=2))
    path=results/'stress-comparison.json';path.write_text(json.dumps(report))
    return path


class Gates(unittest.TestCase):
    def test_latin_screen_and_reverse_balance_all_positions(self):
        products=[dict(label=label) for label in a.PINS]
        forward=[a.order(products,i,'forward-latin') for i in range(3)]
        reverse=[a.order(products,i,'reverse-latin') for i in range(3)]
        for column in range(3):
            self.assertEqual({r[column]['label'] for r in forward},set(a.PINS))
            self.assertEqual({r[column]['label'] for r in reverse},set(a.PINS))
        self.assertEqual([[p['label'] for p in r] for r in forward],[['main','inventory','admission'],['inventory','admission','main'],['admission','main','inventory']])
        with self.assertRaises(ValueError):a.order(products,3,'forward-latin')
        with self.assertRaises(ValueError):a.order(products,1,'canary')

    def test_explicit_selection_never_relaxes_legacy_two_product_guard(self):
        for cell in CACHE_CELLS:a.validate_selection('forward-latin','native',3,cell,CACHE_CELLS,'forward')
        a.validate_selection('canary','native',1,'canary',CACHE_CELLS,'forward')
        for args in [('forward-latin','writable',3,CACHE_CELLS[0],'forward'),('forward-latin','native',1,CACHE_CELLS[0],'forward'),('canary','native',1,CACHE_CELLS[0],'forward'),('forward-latin','native',3,'canary','forward'),('forward-latin','native',3,CACHE_CELLS[0],'reverse')]:
            with self.assertRaises(ValueError):a.validate_selection(args[0],args[1],args[2],args[3],CACHE_CELLS,args[4])
        with self.assertRaisesRegex(ValueError,'one canary product or two paired'):validate_products([{}, {}, {}])
        source=Path(__file__).with_name('stress_run.py').read_text()
        self.assertIn("if len(products)==1 and a.cell!='canary': parser.error('pressure requires two paired products')",source)
        self.assertIn("choices=['canary','forward-latin']",source) # reverse not exposed before eligible screen

    def test_absolute_measurement_budget_cannot_reset_or_expand(self):
        env=dict(STRESS_CACHE_JOB_STARTED_EPOCH='100',STRESS_CACHE_JOB_DEADLINE_EPOCH='2500',STRESS_CACHE_MEASURE_STARTED_EPOCH='500',STRESS_CACHE_MEASURE_DEADLINE_EPOCH='1700')
        self.assertEqual(a.shared_budget(env,600)['remainingSeconds'],1100)
        self.assertEqual(a.shared_budget(env,1650)['remainingSeconds'],50)
        self.assertLess(a.shared_budget(env,1800)['remainingSeconds'],0)
        for key,value in [('STRESS_CACHE_JOB_DEADLINE_EPOCH','2501'),('STRESS_CACHE_MEASURE_DEADLINE_EPOCH','1701'),('STRESS_CACHE_MEASURE_STARTED_EPOCH','99')]:
            with self.assertRaises(ValueError):a.shared_budget({**env,key:value},600)

    def test_actual_file_hashes_and_fixed_three_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);products=[]
            for i,(label,pin) in enumerate(a.PINS.items()):
                binary=root/(label+'-binary');binary.write_bytes(str(i).encode());binary.chmod(0o755);source=root/(label+'-source');source.mkdir()
                products.append(dict(label=label,type='sprig',sha=pin,binary=str(binary),binarySha256=a.digest(binary.read_bytes()),sourcePath=str(source)))
            def git(command,text):return (next(p['sha'] for p in products if p['sourcePath']==command[2])+'\n') if command[3]=='rev-parse' else ''
            with patch.object(a.subprocess,'check_output',side_effect=git):
                self.assertEqual(a.verify_products(products),products)
                for change in (lambda p:p.reverse(),lambda p:p[0].update(sha='0'*40),lambda p:p[1].update(binary=p[0]['binary']),lambda p:p[0].update(diagnostic=True)):
                    bad=copy.deepcopy(products);change(bad)
                    with self.assertRaises((ValueError,StopIteration)):a.verify_products(bad)
                Path(products[0]['binary']).write_bytes(b'changed')
                with self.assertRaises(ValueError):a.verify_products(products)

    def test_all_raw_exact_oracles_and_normal_cleanup_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample,product,fixture,sha,results=sample_fixture(Path(tmp))
            proof=a.validate_sample(sample,product,fixture,True,sha,results,'native-main-0')
            self.assertEqual(proof,dict(fullTreeChecks=11,historicalReadbacks=2,archivedFilesVerified=11))
            for change in (lambda s:s.update(sourceUnchanged=False),lambda s:s['lifecycle']['cleanup'].update(complete=False),lambda s:s.update(fullHistoricalSnapshotReadbacks=1),lambda s:s['capacityPreflight'].update(filesystemBytes=4*1024**3),lambda s:s['fullTreeChecks'].pop()):
                bad=copy.deepcopy(sample);change(bad)
                with self.assertRaises(ValueError):a.validate_sample(bad,product,fixture,True,sha,results,'native-main-0')
            item=sample['completeLogArchive'][0];file=Path(item['archived']);value=json.loads(file.read_text());value['entries'][0]['mtime_ns']+=1;body=json.dumps(value).encode();file.write_bytes(body);item.update(bytes=len(body),sha256=a.digest(body))
            with self.assertRaisesRegex(ValueError,'raw exact-ns'):a.validate_sample(sample,product,fixture,True,sha,results,'native-main-0')

    def test_all_three_exact_canaries_and_original_deadline_are_mandatory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);products=[dict(label=label,type='sprig',sha=sha,binarySha256=str(i+1)*64) for i,(label,sha) in enumerate(a.PINS.items())]
            budget=a.shared_budget(dict(STRESS_CACHE_JOB_STARTED_EPOCH='100',STRESS_CACHE_JOB_DEADLINE_EPOCH='2500',STRESS_CACHE_MEASURE_STARTED_EPOCH='500',STRESS_CACHE_MEASURE_DEADLINE_EPOCH='1700'),600)
            path=canary_fixture(root,products,budget);original=path.read_bytes()
            self.assertEqual(a.validate_canary(path,products,budget)['sha256'],a.digest(original))
            for change in (lambda r:r['records'].pop(),lambda r:r['records'].reverse(),lambda r:r['records'][0].update(correct=False),lambda r:r['records'][0].update(identity='../../unsafe'),lambda r:r['records'][0].update(rawReportSha256='0'*64),lambda r:r['sharedAblationBudget'].update(measurementStartedEpochSeconds=501),lambda r:r['records'][0]['sample'].update(ok=False),lambda r:r.update(noopCheckpoint=False)):
                report=json.loads(original);change(report);path.write_text(json.dumps(report))
                with self.assertRaises(ValueError):a.validate_canary(path,products,budget)
            path.write_bytes(original)
            (path.parent/'native-main-0-stdout.json').unlink()
            with self.assertRaises(OSError):a.validate_canary(path,products,budget)

    def test_expired_absolute_budget_stops_before_image_or_runtime_command(self):
        import stress_run as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'products.json';config.write_text(json.dumps([dict(label=label,type='sprig',sha=sha) for label,sha in a.PINS.items()]))
            output=root/'canary'/'stress-results'
            env=dict(GITHUB_ACTIONS='true',RUNNER_TEMP=str(root),STRESS_CACHE_JOB_STARTED_EPOCH='100',STRESS_CACHE_JOB_DEADLINE_EPOCH='2500',STRESS_CACHE_MEASURE_STARTED_EPOCH='500',STRESS_CACHE_MEASURE_DEADLINE_EPOCH='1700')
            argv=['stress_run.py','--products',str(config),'--cell','canary','--backend','native','--rounds','1','--ablation-stage','canary','--output',str(output)]
            with patch.object(runner.sys,'argv',argv),patch.dict(os.environ,env),patch.object(runner.os,'geteuid',return_value=0),patch.object(runner,'verify_ablation_products',side_effect=lambda p:p),patch.object(runner.time,'time',return_value=1800),patch.object(runner,'command') as command,patch('builtins.print'):
                self.assertEqual(runner.main(),2)
                command.assert_not_called()
            report=json.loads((output/'stress-comparison.json').read_text())
            self.assertEqual(report['records'],[]);self.assertEqual(report['status'],'budget_aborted');self.assertFalse(report['complete']);self.assertEqual(list(root.rglob('store.img')),[])

if __name__=='__main__':unittest.main()
