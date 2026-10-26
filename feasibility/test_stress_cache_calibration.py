"""Offline one-build/copy/schema/correctness guards; no Rust or runtime measurement."""
import copy,json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import stress_cache_calibration as cal
import stress_cache_calibration_summary as summary
import stress_cache_inventory as previous
import stress_cache_ablation as legacy
from test_stress_cache_ablation import sample_fixture,canary_fixture


def build_fixture(root):
    root.mkdir();bin=root/'bin';bin.mkdir();sources={k:root/('sprig-'+k) for k in ('main','portable')}
    for path in sources.values():path.mkdir()
    products=[]
    for label,pin in cal.PINS.items():
        binary=bin/(label+'-sprig');binary.write_bytes(b'main' if label=='main' else b'one portable release build');binary.chmod(0o755)
        products.append(dict(label=label,type='sprig',sha=pin,binary=str(binary),binarySha256=cal.digest(binary.read_bytes()),sourcePath=str(sources['main' if label=='main' else 'portable'])))
    origin=bin/'portable-sprig';origin.write_bytes(Path(products[1]['binary']).read_bytes());origin.chmod(0o755)
    records=root/'results';records.mkdir();log=records/'portable-release-build.log';log.write_text('   Compiling sprig v0.2.0 ('+str(sources['portable'])+')\n')
    proof=dict(schema=cal.PROOF_SCHEMA,source=dict(sha=cal.PINS['copy1'],path=str(sources['portable'])),builtBinary=dict(path=str(origin),sha256=cal.digest(origin.read_bytes())),releaseBuildLog=dict(path=str(log),bytes=log.stat().st_size,sha256=cal.digest(log.read_bytes())),copies=[dict(label=p['label'],path=p['binary'],sha256=p['binarySha256']) for p in products[1:]],releaseBuildCount=1,copyMethod='install -m 0755 from one built binary')
    path=records/'cache-identical-build.json';path.write_text(json.dumps(proof));return products,path


def fixture(root,copy2_factors=(1,1,1)):
    products,proof=build_fixture(root/'build');evidence=cal.load_build_evidence(proof,products)
    results=root/'stress-results';results.mkdir()
    report=dict(schema=cal.SCHEMA,ablationStage='reverse-latin',cell=cal.CELL,backends=['native'],rounds=3,expectedRecords=9,complete=True,status='passed',products=products,records=[],noopCheckpoint=True,outputDirectory=str(results),inventoryCalibration=cal.identity(products,evidence),sharedAblationBudget=dict(jobStartedEpochSeconds=100,jobDeadlineEpochSeconds=2500,measurementStartedEpochSeconds=500,measurementDeadlineEpochSeconds=1700,maximumMeasurementSeconds=1200))
    canary=canary_fixture(root/'canary',products,report['sharedAblationBudget']);value=json.loads(canary.read_text());value.update(schema=cal.SCHEMA,inventoryCalibration=cal.identity(products,evidence));canary.write_text(json.dumps(value));report['canaryPrerequisite']=dict(path=str(canary),sha256=cal.digest(canary.read_bytes()))
    for round_no in range(3):
        for product in cal.order(products,round_no,'reverse-latin'):
            identity=f"native-{product['label']}-{round_no}";part=root/identity;part.mkdir();sample,_,source,sha,original=sample_fixture(part,product,identity)
            logs=original/(identity+'-steps.jsonl.logs');shutil.move(str(logs),str(results/logs.name))
            for item in sample['completeLogArchive']:item['archived']=str(results/logs.name/Path(item['archived']).name)
            ratio=1 if product['label']=='main' else .6*(copy2_factors[round_no] if product['label']=='copy2' else 1)
            sample['restore_seconds']*=ratio;sample['warm_fork_seconds']=.2 if product['label']!='copy2' else .4
            raw=json.dumps(sample).encode();(results/(identity+'-stdout.json')).write_bytes(raw);report['records'].append(dict(identity=identity,product=product['label'],round=round_no,correct=True,status='passed',sampleReturncode=0,sample=sample,rawReportSha256=cal.digest(raw),wholeSampleSubprocessWallSeconds=12*ratio));report['fixtureSha256']=sha
    (results/'fixture.json').write_text(json.dumps(source,indent=2));path=results/'stress-comparison.json';path.write_text(json.dumps(report));return path,source['parameters'],canary,proof


class CalibrationTests(unittest.TestCase):
    def checked(self,path,params,canary,proof):
        with patch.object(summary,'cache_cell_parameters',return_value=(params,True)):return summary.summarize(path,canary,proof)

    def test_fixed_identical_copy_identity_never_relaxes_old_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            ps,proof=build_fixture(Path(tmp)/'build');cal.validate_product_identity(ps)
            for change in (lambda p:p[2].update(binarySha256='f'*64),lambda p:p[2].update(sourcePath='/another/checkout'),lambda p:p[2].update(binary=p[1]['binary']),lambda p:p[2].update(sha=previous.PINS['inventory']),lambda p:p[0].update(binarySha256=p[1]['binarySha256']),lambda p:p[1].update(sourcePath='/x/../sprig-portable')):
                bad=copy.deepcopy(ps);change(bad)
                with self.assertRaises(ValueError):cal.validate_product_identity(bad)
            for verify in (legacy.verify_products,previous.verify_products):
                with self.assertRaises(ValueError):verify(ps)
            self.assertEqual([[p['label'] for p in cal.order(ps,r,'reverse-latin')] for r in range(3)],[['copy2','copy1','main'],['copy1','main','copy2'],['main','copy2','copy1']])
            for args in [('forward-latin','native',3,cal.CELL,'forward'),('reverse-latin','native',3,'files-10000','forward'),('reverse-latin','projection',3,cal.CELL,'forward'),('reverse-latin','native',1,cal.CELL,'forward')]:
                with self.assertRaises(ValueError):cal.validate_selection(*args)

    def test_live_one_build_byte_identity_and_independent_inode_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            ps,proof=build_fixture(Path(tmp)/'build')
            def git(args,text):return next(p['sha'] for p in ps if p['sourcePath']==args[2])+'\n' if args[3]=='rev-parse' else ''
            with patch.object(cal.subprocess,'check_output',side_effect=git):self.assertEqual(cal.verify_products(ps,proof),ps)
            with patch.object(cal.subprocess,'check_output',side_effect=lambda args,text:'0'*40+'\n' if args[3]=='rev-parse' else ''):
                with self.assertRaisesRegex(ValueError,'checkout pin'):cal.verify_products(ps,proof)
            with patch.object(cal.subprocess,'check_output',side_effect=lambda args,text:git(args,text) if args[3]=='rev-parse' else ' M changed'):
                with self.assertRaisesRegex(ValueError,'source changed'):cal.verify_products(ps,proof)
            p=Path(ps[2]['binary']);original=p.read_bytes();p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'byte-for-byte'):cal.load_build_evidence(proof,ps,live=True)
            p.write_bytes(original);p.unlink();os.link(ps[1]['binary'],p)
            with self.assertRaisesRegex(ValueError,'hardlink aliases'):cal.load_build_evidence(proof,ps,live=True)

    def test_wrong_source_multiple_builds_hashes_copy_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ps,path=build_fixture(Path(tmp)/'build');proof=json.loads(path.read_text())
            for change in (lambda p:p['source'].update(sha='0'*40),lambda p:p.update(releaseBuildCount=2),lambda p:p.update(releaseBuildCount=True),lambda p:p['builtBinary'].update(sha256='0'*64),lambda p:p['copies'].reverse(),lambda p:p['releaseBuildLog'].update(path='/bad/wrong.log'),lambda p:p.update(extra='unreviewed')):
                bad=copy.deepcopy(proof);change(bad)
                with self.assertRaises(ValueError):cal.validate_build_proof(bad,ps)
            log=path.parent/'portable-release-build.log';log.write_text(log.read_text()*2);proof['releaseBuildLog'].update(bytes=log.stat().st_size,sha256=cal.digest(log.read_bytes()));path.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError,'exactly one'):cal.load_build_evidence(path,ps)

    def test_archived_proof_relocation_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ps,path=build_fixture(root/'build');original=path.read_bytes();target=root/'relocated';shutil.copytree(path.parent,target)
            evidence=cal.load_build_evidence(target/path.name,ps);self.assertEqual(evidence['sha256'],cal.digest(original));self.assertEqual((target/path.name).read_bytes(),original)
            (target/'portable-release-build.log').write_text('changed')
            with self.assertRaisesRegex(ValueError,'log bytes changed'):cal.load_build_evidence(target/path.name,ps)

    def test_all_nine_exact_samples_noise_gate_and_shared_baseline_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=fixture(Path(tmp));result=self.checked(*args);self.assertTrue(result['complete'],result['errors']);a=result['calibrationAssessment'];self.assertTrue(a['noiseMedianGatePassed']);self.assertTrue(a['allNoisePairsWithinMedianBand']);self.assertEqual(a['sharedBaselineIndependentRounds'],3);self.assertFalse(a['automaticPromotion']);self.assertTrue(all(a['eachSharedBaselineArmMedianGate'].values()))
            self.assertEqual(result['comparisons']['copy1-to-copy2']['warm_fork_seconds']['medianPairedRatio'],2)
            self.assertEqual(len(result['records']),9);self.assertTrue(all(r['proof']['fullTreeChecks']==11 for r in result['records']))

    def test_noise_failure_is_inconclusive_not_rerun_or_filtered_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=self.checked(*fixture(Path(tmp),(1.2,1.2,1.2)));self.assertTrue(result['complete']);a=result['calibrationAssessment'];self.assertFalse(a['noiseMedianGatePassed']);self.assertFalse(a['automaticRerun']);self.assertIn('inconclusive',a['interpretation']);self.assertEqual(len(a['noisePairs']['restore_seconds']),3)

    def test_wild_scatter_is_visible_even_when_median_gate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=self.checked(*fixture(Path(tmp),(.5,1,2)));a=result['calibrationAssessment'];self.assertTrue(a['noiseMedianGatePassed']);self.assertFalse(a['allNoisePairsWithinMedianBand']);self.assertEqual([p['candidateOverBaseline'] for p in a['noisePairs']['restore_seconds']],[.5,1,2]);self.assertIn('inspect every pair/scatter',a['interpretation'])

    def test_wrong_order_missing_proof_source_and_raw_failures_suppress_ratios(self):
        changes=(lambda r:r['records'].pop(),lambda r:r['records'].reverse(),lambda r:r.pop('inventoryCalibration'),lambda r:r['inventoryCalibration']['singleBuildEvidence'].update(sha256='0'*64),lambda r:r['products'][2].update(sha=previous.PINS['inventory']),lambda r:r.update(complete=False,status='failed'),lambda r:r['sharedAblationBudget'].update(measurementDeadlineEpochSeconds=1701))
        for change in changes:
            with tempfile.TemporaryDirectory() as tmp:
                path,params,canary,proof=fixture(Path(tmp));r=json.loads(path.read_text());change(r);path.write_text(json.dumps(r));result=self.checked(path,params,canary,proof);self.assertFalse(result['complete']);self.assertIsNone(result['comparisons']);self.assertEqual(len(result['records']),len(r['records']))
        with tempfile.TemporaryDirectory() as tmp:
            path,params,canary,proof=fixture(Path(tmp));proof.unlink();result=self.checked(path,params,canary,proof);self.assertFalse(result['complete']);self.assertIsNone(result['comparisons'])

    def test_primary_zero_timing_and_rehashed_missing_canary_proof_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,params,canary,proof=fixture(Path(tmp));r=json.loads(path.read_text());row=r['records'][0];row['sample']['restore_seconds']=0;raw=json.dumps(row['sample']).encode();(path.parent/(row['identity']+'-stdout.json')).write_bytes(raw);row['rawReportSha256']=cal.digest(raw);path.write_text(json.dumps(r));self.assertFalse(self.checked(path,params,canary,proof)['complete'])
        with tempfile.TemporaryDirectory() as tmp:
            path,params,canary,proof=fixture(Path(tmp));r=json.loads(canary.read_text());r.pop('inventoryCalibration');canary.write_text(json.dumps(r));outer=json.loads(path.read_text());outer['canaryPrerequisite']['sha256']=cal.digest(canary.read_bytes());path.write_text(json.dumps(outer));self.assertFalse(self.checked(path,params,canary,proof)['complete'])

    def test_expired_budget_and_mixed_modes_stop_before_runtime(self):
        import stress_run as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ps,proof=build_fixture(root/'build');config=root/'products.json';config.write_text(json.dumps(ps));output=root/'canary'/'stress-results';env=dict(GITHUB_ACTIONS='true',RUNNER_TEMP=str(root),STRESS_CACHE_JOB_STARTED_EPOCH='100',STRESS_CACHE_JOB_DEADLINE_EPOCH='2500',STRESS_CACHE_MEASURE_STARTED_EPOCH='500',STRESS_CACHE_MEASURE_DEADLINE_EPOCH='1700')
            args=['stress_run.py','--products',str(config),'--cell','canary','--backend','native','--rounds','1','--inventory-calibration-stage','canary','--inventory-calibration-build-proof',str(proof),'--output',str(output)]
            with patch.object(runner.sys,'argv',args),patch.dict(os.environ,env),patch.object(runner.os,'geteuid',return_value=0),patch.object(cal,'verify_products',side_effect=lambda p,path:p),patch.object(runner.time,'time',return_value=1800),patch.object(runner,'command') as command,patch('builtins.print'):
                self.assertEqual(runner.main(),2);command.assert_not_called()
            report=json.loads((output/'stress-comparison.json').read_text());self.assertEqual(report['records'],[]);self.assertEqual(report['schema'],cal.SCHEMA)
            missing=list(args);i=missing.index('--inventory-calibration-build-proof');del missing[i:i+2]
            with patch.object(runner.sys,'argv',missing),patch.dict(os.environ,env),patch.object(runner.os,'geteuid',return_value=0),patch.object(runner,'command') as command:
                with self.assertRaises(SystemExit):runner.main()
                command.assert_not_called()
            with patch.object(runner.sys,'argv',args+['--inventory-confirmation-stage','canary']),patch.dict(os.environ,env),patch.object(runner.os,'geteuid',return_value=0),patch.object(runner,'command') as command:
                with self.assertRaises(SystemExit):runner.main()
                command.assert_not_called()

if __name__=='__main__':unittest.main()
