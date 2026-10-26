import hashlib,json,os,stat,tempfile,unittest
from pathlib import Path
from stress_cargo_collect import collect, allowed

class Tests(unittest.TestCase):
    def test_failed_setup_copies_only_named_evidence_and_preserves_private_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);results=base/'results';results.mkdir();temporary=base/'temp';temporary.mkdir()
            pilot=temporary/'stress-cargo-capacity-pilot';pilot.mkdir(mode=0o700)
            (pilot/'inc0.stdout').write_text('full pilot output');(pilot/'inc0.stderr').write_text('')
            (pilot/'incremental-0').mkdir();(pilot/'incremental-0'/'secret').write_text('excluded')
            (results/'stress-cargo-comparison-0.json').write_text('{"complete":false}')
            (results/'daemon.json.original').write_text('excluded config')
            dest=base/'artifacts';rows=collect(results,temporary,dest,os.getuid(),os.getgid())
            self.assertEqual(len(rows),3);self.assertEqual(stat.S_IMODE(pilot.stat().st_mode),0o700)
            self.assertEqual((dest/'capacity/inc0.stdout').read_text(),'full pilot output')
            self.assertFalse((dest/'results/daemon.json.original').exists())
            self.assertEqual(stat.S_IMODE((dest/'capacity/inc0.stdout').stat().st_mode),0o644)
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode),0o755)
            self.assertEqual(len(json.loads((dest/'collection.json').read_text())['files']),3)
    def test_missing_sources_before_any_setup_still_produces_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir()
            self.assertEqual(collect(b/'results',t,b/'out',os.getuid(),os.getgid()),[])
    def test_symlink_evidence_is_rejected_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();r=b/'results';r.mkdir();secret=b/'secret';secret.write_text('no')
            (r/'environment.txt').symlink_to(secret)
            with self.assertRaises(OSError):collect(r,t,b/'out',os.getuid(),os.getgid())
    def test_allowlisted_archived_logs_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();d=t/'stress-cargo-records/inc0';d.mkdir(parents=True)
            (d/'sprig-writable-0.jsonl').write_text('{}\n');logs=d/'sprig-writable-0.jsonl.logs';logs.mkdir();(logs/'000001-example.stderr').write_text('complete')
            self.assertEqual(len(collect(b/'results',t,b/'out',os.getuid(),os.getgid())),2)

    def test_declared_jsonl_archive_is_copied_and_verified(self):
        self.archive_case(None)
    def test_missing_hash_size_and_unsafe_declared_archive_fail_closed(self):
        for failure in ('missing','hash','size','outside','empty','comparison_only','malformed','null_path','null_sample'):
            with self.subTest(failure=failure):self.archive_case(failure)
    def archive_case(self,failure):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();r=b/'results';r.mkdir()
            directory=t/'stress-cargo-records/inc0/sprig-writable-0.jsonl.logs';directory.mkdir(parents=True)
            source=directory/'000055-lifecycle.jsonl';data=b'{"event":"normal cleanup"}\n'
            if failure not in ('missing','comparison_only'):source.write_bytes(data)
            item={'archived':str(source),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            if failure=='hash':item['sha256']='0'*64
            if failure=='size':item['bytes']+=1
            if failure=='outside':item['archived']=str(b/'private.jsonl')
            if failure=='null_path':item['archived']=None
            sample={'ok':True,'completeLogArchive':[] if failure=='empty' else [item]}
            if failure=='comparison_only':
                (r/'stress-cargo-comparison-0.json').write_text(json.dumps({'records':[{'product':'sprig-writable','round':0,'sample':sample}]}))
            else:(r/'stress-cargo-sprig-writable-inc0-0.json').write_text(json.dumps(sample))
            if failure=='malformed':(r/'stress-cargo-sprig-writable-inc0-0.json').write_text('{')
            if failure=='null_sample':(r/'stress-cargo-sprig-writable-inc0-0.json').write_text('null')
            out=b/'out'
            if failure:
                with self.assertRaisesRegex(ValueError,'completeness failed'):collect(r,t,out,os.getuid(),os.getgid())
            else:collect(r,t,out,os.getuid(),os.getgid())
            coverage=json.loads((out/'collection.json').read_text())['declaredArchiveVerification']
            self.assertEqual(coverage['ok'],failure is None)
            if failure is None:
                self.assertEqual(coverage['verifiedUniqueFiles'],1)
                self.assertEqual((out/'records/inc0/sprig-writable-0.jsonl.logs/000055-lifecycle.jsonl').read_bytes(),data)

class OwnABTests(unittest.TestCase):
    def test_exact_new_names_only(self):
        for product in ('sprig-baseline','sprig-candidate'):
            self.assertTrue(allowed('results',(f'stress-cargo-{product}-inc1-2.json',)))
            self.assertTrue(allowed('records',('inc1',f'{product}-2.jsonl')))
            self.assertTrue(allowed('records',('inc0',f'{product}-0-options.json')))
        for name in ('stress-cargo-own-ab-2.json','stress-cargo-own-ab-0.json.extra','stress-cargo-sprig-other-inc0-0.json'):
            self.assertFalse(allowed('results',(name,)))

    def test_exact_additional_evidence_names(self):
        names='stress-cargo-ab-products.json baseline-source-hashes.txt candidate-source-hashes.txt baseline-binary-hash.txt candidate-binary-hash.txt baseline-release-build.log candidate-release-build.log baseline-tests.txt candidate-tests.txt baseline-projection-gate.json candidate-projection-gate.json baseline-writable-gate.json candidate-writable-gate.json'.split()
        for name in names:
            self.assertTrue(allowed('results',(name,)))
            self.assertFalse(allowed('results',(name+'.extra',)))
        self.assertFalse(allowed('results',('other-release-build.log',)))

    def test_own_ab_both_products_and_individual_reports(self):
        self.case(None)

    def test_malformed_archive_and_cross_family_identity_rejected(self):
        for failure in ('wrong_product','old_report_new_product','new_report_old_product',
                        'wrong_archive_product','wrong_incremental_path','duplicate',
                        'bad_entry','bad_size','bad_hash','bad_round_bool','bad_round_string',
                        'wrong_schema','wrong_incremental','bool_incremental','missing_incremental','own_round_one'):
            with self.subTest(failure=failure):self.case(failure)

    def case(self,failure):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);t=b/'temp';t.mkdir();r=b/'results';r.mkdir();records=[]
            for product in ('sprig-baseline','sprig-candidate'):
                directory=t/f'stress-cargo-records/inc1/{product}-0.jsonl.logs'
                directory.mkdir(parents=True);source=directory/'000001-lifecycle.jsonl'
                data=b'{}\n';source.write_bytes(data)
                item={'archived':str(source),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                if product=='sprig-baseline':
                    if failure=='wrong_archive_product':item['archived']=str(source).replace('sprig-baseline','sprig-candidate')
                    if failure=='wrong_incremental_path':item['archived']=str(source).replace('/inc1/','/inc0/')
                    if failure=='bad_size':item['bytes']=str(len(data))
                    if failure=='bad_hash':item['sha256']=None
                sample={'ok':True,'completeLogArchive':[item]}
                if product=='sprig-baseline' and failure=='duplicate':sample['completeLogArchive'].append(item)
                if product=='sprig-baseline' and failure=='bad_entry':sample['completeLogArchive']=[None]
                records.append({'product':product,'round':0,'sample':sample})
                (r/f'stress-cargo-{product}-inc1-0.json').write_text(json.dumps(sample))
            report='stress-cargo-own-ab-1.json'
            if failure=='wrong_product':records[0]['product']='sprig-other'
            if failure=='old_report_new_product':report='stress-cargo-comparison-1.json'
            if failure=='new_report_old_product':records[0]['product']='sprig-writable'
            if failure=='bad_round_bool':records[0]['round']=False
            if failure=='bad_round_string':records[0]['round']='0'
            value={'schema':'sprig-stress-cargo-own-ab-v1','incremental':1,'records':records}
            if failure=='wrong_schema':value['schema']='sprig-stress-cargo-comparison-v2'
            if failure=='wrong_incremental':value['incremental']=0
            if failure=='bool_incremental':value['incremental']=True
            if failure=='missing_incremental':del value['incremental']
            if failure=='own_round_one':records[0]['round']=1
            (r/report).write_text(json.dumps(value))
            out=b/'out'
            if failure:
                with self.assertRaisesRegex(ValueError,'completeness failed'):collect(r,t,out,os.getuid(),os.getgid())
            else:
                collect(r,t,out,os.getuid(),os.getgid())
                coverage=json.loads((out/'collection.json').read_text())['declaredArchiveVerification']
                self.assertEqual(coverage,{'ok':True,'sampleDeclarations':4,'verifiedUniqueFiles':2,'errors':[]})
                with self.assertRaisesRegex(ValueError,'new artifact destination'):collect(r,t,out,os.getuid(),os.getgid())



class RepeatedOwnABTests(unittest.TestCase):
    def test_precise_fourth_round_allowlist(self):
        for product in ('sprig-baseline','sprig-candidate'):
            self.assertTrue(allowed('results',(f'stress-cargo-{product}-inc1-3.json',)))
            self.assertTrue(allowed('records',('inc1',f'{product}-3.jsonl')))
            self.assertFalse(allowed('results',(f'stress-cargo-{product}-inc1-4.json',)))
        self.assertFalse(allowed('results',('stress-cargo-layerfs-inc1-3.json',)))
        self.assertFalse(allowed('records',('inc1','sprig-writable-3.jsonl')))

    def test_explicit_pressure_identity_is_collected_separately(self):
        from stress_cargo_collect import ORDINARY_EXPERIMENT
        from stress_cargo_pressure import SPEC,pressure_identity
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);temporary=base/'temp';temporary.mkdir();results=base/'results';results.mkdir()
            report=dict(schema='sprig-stress-cargo-own-ab-v2',incremental=0,rounds=4,records=[],complete=False,
                        experimentSpec={**ORDINARY_EXPERIMENT,'profile':SPEC['profile'],'pressure':pressure_identity()})
            (results/'stress-cargo-own-ab-0.json').write_text(json.dumps(report))
            collect(results,temporary,base/'out',os.getuid(),os.getgid())
            report['experimentSpec']['pressure']['scriptSha256']='0'*64
            (results/'stress-cargo-own-ab-0.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'completeness failed'):collect(results,temporary,base/'bad',os.getuid(),os.getgid())

    def test_fourth_round_archive_and_fixed_experiment_identity(self):
        from stress_cargo_collect import ORDINARY_EXPERIMENT
        for failure in (None,'wrong_profile','legacy','wrong_rounds','missing_file'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                b=Path(tmp);t=b/'temp';t.mkdir();r=b/'results';r.mkdir()
                directory=t/'stress-cargo-records/inc0/sprig-baseline-3.jsonl.logs';directory.mkdir(parents=True)
                source=directory/'000001-lifecycle.jsonl';data=b'{}\n'
                if failure!='missing_file':source.write_bytes(data)
                sample={'ok':True,'completeLogArchive':[{'archived':str(source),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
                report={'schema':'sprig-stress-cargo-own-ab-v2','incremental':0,'rounds':4,'experimentSpec':dict(ORDINARY_EXPERIMENT),'records':[{'product':'sprig-baseline','round':3,'sample':sample}]}
                if failure=='wrong_profile':report['experimentSpec']['profile']='other'
                if failure=='legacy':report['schema']='sprig-stress-cargo-own-ab-v1'
                if failure=='wrong_rounds':report['rounds']=3
                (r/'stress-cargo-own-ab-0.json').write_text(json.dumps(report))
                if failure:
                    with self.assertRaisesRegex(ValueError,'completeness failed'):collect(r,t,b/'out',os.getuid(),os.getgid())
                else:
                    collect(r,t,b/'out',os.getuid(),os.getgid())
                    self.assertEqual(json.loads((b/'out/collection.json').read_text())['declaredArchiveVerification']['verifiedUniqueFiles'],1)

if __name__=='__main__':unittest.main()
