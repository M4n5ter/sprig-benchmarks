"""Offline guards for the explicit inventory-only series; no Rust or mounted workload."""
import copy,json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import stress_cache_inventory as inv
import stress_cache_inventory_summary as summary
import stress_cache_ablation as old
from test_stress_cache_ablation import sample_fixture,canary_fixture


def products():
    return [dict(label=label,type='sprig',sha=sha,binary=f'/bin/{label}',binarySha256=('1' if i==0 else '2')*64,sourcePath=f'/sources/{label}') for i,(label,sha) in enumerate(inv.PINS.items())]


def fixture(root):
    results=root/'stress-results';results.mkdir();ps=products()
    report=dict(schema=inv.SCHEMA,ablationStage='reverse-latin',cell=inv.CELL,backends=['native'],rounds=3,expectedRecords=9,complete=True,status='passed',products=ps,records=[],noopCheckpoint=True,outputDirectory=str(results),inventoryConfirmation=inv.identity(ps),sharedAblationBudget=dict(jobStartedEpochSeconds=100,jobDeadlineEpochSeconds=2500,measurementStartedEpochSeconds=500,measurementDeadlineEpochSeconds=1700,maximumMeasurementSeconds=1200))
    canary=canary_fixture(root/'canary',ps,report['sharedAblationBudget']);value=json.loads(canary.read_text());value.update(schema=inv.SCHEMA,inventoryConfirmation=inv.identity(ps));canary.write_text(json.dumps(value))
    report['canaryPrerequisite']={'path':str(canary),'sha256':inv.digest(canary.read_bytes())}
    for round_no in range(3):
        for product in inv.order(ps,round_no,'reverse-latin'):
            identity=f"native-{product['label']}-{round_no}";part=root/identity;part.mkdir()
            sample,_,source,sha,original=sample_fixture(part,product,identity)
            logs=original/(identity+'-steps.jsonl.logs');shutil.move(str(logs),str(results/logs.name))
            for item in sample['completeLogArchive']:item['archived']=str(results/logs.name/Path(item['archived']).name)
            ratio=1 if product['label']=='main' else .6;sample['restore_seconds']*=ratio
            raw=json.dumps(sample).encode();(results/(identity+'-stdout.json')).write_bytes(raw)
            report['records'].append(dict(identity=identity,product=product['label'],round=round_no,correct=True,status='passed',sampleReturncode=0,sample=sample,rawReportSha256=inv.digest(raw),wholeSampleSubprocessWallSeconds=12*ratio))
            report['fixtureSha256']=sha
    (results/'fixture.json').write_text(json.dumps(source,indent=2));path=results/'stress-comparison.json';path.write_text(json.dumps(report))
    return path,source['parameters'],canary


class InventoryConfirmationTests(unittest.TestCase):
    def checked(self,path,params,canary):
        with patch.object(summary,'cache_cell_parameters',return_value=(params,True)):return summary.summarize(path,canary)

    def test_fixed_reverse_order_cell_and_old_selection_remain_separate(self):
        ps=products();orders=[[p['label'] for p in inv.order(ps,r,'reverse-latin')] for r in range(3)]
        self.assertEqual(orders,[['portable','inventory','main'],['inventory','main','portable'],['main','portable','inventory']])
        self.assertEqual([p['label'] for p in inv.order(ps,0,'canary')],list(inv.PINS))
        inv.validate_selection('reverse-latin','native',3,inv.CELL,'forward')
        for args in [('reverse-latin','native',3,'files-10000','forward'),('forward-latin','native',3,inv.CELL,'forward'),('reverse-latin','writable',3,inv.CELL,'forward'),('reverse-latin','native',1,inv.CELL,'forward'),('reverse-latin','native',3,inv.CELL,'reverse')]:
            with self.assertRaises(ValueError):inv.validate_selection(*args)
        with self.assertRaises(ValueError):old.verify_products(ps)
        source=Path(__file__).with_name('stress_run.py').read_text();self.assertIn("choices=['canary','forward-latin']",source);self.assertIn("if len(products)==1 and a.cell!='canary': parser.error('pressure requires two paired products')",source)

    def test_reviewed_prior_attestation_exact_bytes_sources_and_positive_edge(self):
        proof=inv.prerequisite();self.assertEqual(proof['run'],40302159760);self.assertIn('not-fresh-raw-reaudit',proof['kind']);self.assertLess(proof['restoreMedianPairedRatio'],.9)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in inv.BUNDLE_HASHES:shutil.copyfile(inv.BUNDLE/name,root/name)
            for name in inv.BUNDLE_HASHES:
                p=root/name;original=p.read_bytes();p.write_bytes(original+b' ')
                with self.assertRaisesRegex(ValueError,'prerequisite bytes changed'):inv.prerequisite(root)
                p.write_bytes(original)
            (root/'provenance-audit.json').unlink()
            with self.assertRaises((ValueError,OSError)):inv.prerequisite(root)

    def test_equal_hash_allowed_only_known_inventory_portable_pair_and_proof(self):
        ps=products();self.assertEqual(inv.validate_product_identity(ps),ps);self.assertTrue(inv.identity(ps)['releaseSourceEquivalence']['binaryHashesEqual'])
        for change in (lambda p:p[0].update(binarySha256=p[1]['binarySha256']),lambda p:p[2].update(sha=old.PINS['admission']),lambda p:p[2].update(label='admission'),lambda p:p[2].update(binary=p[1]['binary']),lambda p:p[2].update(sourcePath=p[1]['sourcePath']),lambda p:p[2].update(extra=True)):
            bad=copy.deepcopy(ps);change(bad)
            with self.assertRaises(ValueError):inv.validate_product_identity(bad)
        report=dict(schema=inv.SCHEMA,inventoryConfirmation=inv.identity(ps));inv.validate_report_identity(report,ps)
        for change in (lambda r:r.pop('inventoryConfirmation'),lambda r:r['inventoryConfirmation']['releaseSourceEquivalence'].update(releaseProductionPrefixSha256='0'*64),lambda r:r['inventoryConfirmation']['prerequisite'].update(head='0'*40),lambda r:r.update(schema=old.SCHEMA)):
            bad=copy.deepcopy(report);change(bad)
            with self.assertRaises(ValueError):inv.validate_report_identity(bad,ps)

    def test_actual_source_and_binary_verification_gate_equal_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ps=products();prefix=b'// production\n';seam=b'    #[cfg(test)]\n    tests::inject_fill_fault()?;\n';boundary=b'#[cfg(test)]\nmod tests {'
            bodies={'inventory':prefix+boundary+b' old }','portable':prefix+seam+boundary+b' new }'}
            for i,p in enumerate(ps):
                binary=root/(p['label']+'-binary');binary.write_bytes(b'main' if i==0 else b'equal-release');binary.chmod(0o755)
                source=root/(p['label']+'-source');(source/'src').mkdir(parents=True)
                if i:(source/'src/file_cache.rs').write_bytes(bodies[p['label']])
                p.update(binary=str(binary),binarySha256=inv.digest(binary.read_bytes()),sourcePath=str(source))
            altered=False
            def git(args,text):
                p=next(p for p in ps if p['sourcePath']==args[2]);action=args[3]
                if action=='rev-parse':return p['sha']+'\n'
                if action=='status':return ''
                if action=='ls-tree':return f"100644 blob {p['label']}\tsrc/file_cache.rs\n100644 blob {'wrong' if altered and p['label']=='portable' else 'same'}\tCargo.toml\n"
                raise AssertionError(args)
            with patch.object(inv,'FILE_HASHES',{k:inv.digest(v) for k,v in bodies.items()}),patch.object(inv,'PRODUCTION_PREFIX_SHA256',inv.digest(prefix)),patch.object(inv.subprocess,'check_output',side_effect=git):
                self.assertEqual(inv.verify_products(ps),ps)
                altered=True
                with self.assertRaisesRegex(ValueError,'other tracked'):inv.verify_products(ps)
                altered=False;Path(ps[2]['sourcePath'],'src/file_cache.rs').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'file bytes changed'):inv.verify_products(ps)

    def test_all_nine_reverse_records_equal_binary_control_and_raw_canaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,params,canary=fixture(Path(tmp));result=self.checked(path,params,canary)
            self.assertTrue(result['complete'],result['errors']);self.assertEqual(len(result['records']),9)
            self.assertEqual(set(result['comparisons']),{'main-to-inventory','inventory-to-portable','main-to-portable'})
            self.assertEqual(result['comparisons']['inventory-to-portable']['restore_seconds']['medianPairedRatio'],1)
            self.assertTrue(all(r['proof']['fullTreeChecks']==11 for r in result['records']))
            self.assertTrue(all(r['notMeasured']['metadata_branch_seconds']['value'] is None for r in result['records']))

    def test_failed_missing_wrong_order_source_proof_deadline_suppresses_every_ratio(self):
        changes=[lambda r:r.update(complete=False,status='failed'),lambda r:r['records'].pop(),lambda r:r['records'].reverse(),lambda r:r['products'][2].update(sha=old.PINS['admission']),lambda r:r.pop('inventoryConfirmation'),lambda r:r['inventoryConfirmation']['releaseSourceEquivalence'].update(binaryHashesEqual=False),lambda r:r.update(ablationStage='forward-latin'),lambda r:r['sharedAblationBudget'].update(measurementDeadlineEpochSeconds=1701),lambda r:r['canaryPrerequisite'].update(sha256='0'*64)]
        for change in changes:
            with tempfile.TemporaryDirectory() as tmp:
                path,params,canary=fixture(Path(tmp));report=json.loads(path.read_text());change(report);path.write_text(json.dumps(report));result=self.checked(path,params,canary)
                self.assertFalse(result['complete']);self.assertIsNone(result['comparisons']);self.assertEqual(len(result['records']),len(report['records']))
        with tempfile.TemporaryDirectory() as tmp:
            path,params,canary=fixture(Path(tmp));canary.unlink();result=self.checked(path,params,canary);self.assertFalse(result['complete']);self.assertIsNone(result['comparisons'])

    def test_canary_proof_missing_is_not_excused_by_rehashed_outer_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,params,canary=fixture(Path(tmp));value=json.loads(canary.read_text());value.pop('inventoryConfirmation');canary.write_text(json.dumps(value))
            report=json.loads(path.read_text());report['canaryPrerequisite']['sha256']=inv.digest(canary.read_bytes());path.write_text(json.dumps(report))
            result=self.checked(path,params,canary);self.assertFalse(result['complete']);self.assertIsNone(result['comparisons'])

    def test_expired_budget_before_images_and_mutually_exclusive_entry_modes(self):
        import stress_run as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'products.json';config.write_text(json.dumps(products()));output=root/'canary'/'stress-results'
            env=dict(GITHUB_ACTIONS='true',RUNNER_TEMP=str(root),STRESS_CACHE_JOB_STARTED_EPOCH='100',STRESS_CACHE_JOB_DEADLINE_EPOCH='2500',STRESS_CACHE_MEASURE_STARTED_EPOCH='500',STRESS_CACHE_MEASURE_DEADLINE_EPOCH='1700')
            args=['stress_run.py','--products',str(config),'--cell','canary','--backend','native','--rounds','1','--inventory-confirmation-stage','canary','--output',str(output)]
            with patch.object(runner.sys,'argv',args),patch.dict(os.environ,env),patch.object(runner.os,'geteuid',return_value=0),patch.object(inv,'verify_products',side_effect=lambda p:p),patch.object(runner.time,'time',return_value=1800),patch.object(runner,'command') as command,patch('builtins.print'):
                self.assertEqual(runner.main(),2);command.assert_not_called()
            report=json.loads((output/'stress-comparison.json').read_text());self.assertEqual(report['records'],[]);self.assertEqual(report['schema'],inv.SCHEMA);self.assertEqual(report['status'],'budget_aborted')
            with patch.object(runner.sys,'argv',args+['--ablation-stage','canary']),patch.dict(os.environ,env),patch.object(runner.os,'geteuid',return_value=0),patch.object(runner,'command') as command:
                with self.assertRaises(SystemExit):runner.main()
                command.assert_not_called()

if __name__=='__main__':unittest.main()
