#!/usr/bin/env python3
"""Synthetic evidence only; no product, process, Docker, compiler or mount."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import stress_cargo_collect as c

class CleanSyncTTLCollectorTests(unittest.TestCase):
    def roots(self,tmp):
        base=Path(tmp);results=base/'results';results.mkdir();temporary=base/'temporary';temporary.mkdir()
        return results,temporary,base/'out'
    def collect(self,results,temporary,out):
        return c.collect(results,temporary,out,os.getuid(),os.getgid(),clean_sync_ttl=True)
    def report(self,mode=0):
        return dict(schema='sprig-stress-cargo-clean-sync-ttl-v1',rounds=6,expectedRecords=18,incremental=mode,complete=False,abcExperiment=copy.deepcopy(c.CLEAN_SYNC_TTL_EXPERIMENT),records=[])
    def test_exact_new_allowlist_and_old_mode_isolation(self):
        for mode in (0,1):
            for product in c.CLEAN_SYNC_TTL_PRODUCTS:
                for block in range(6):
                    self.assertTrue(c.allowed('results',(f'stress-cargo-{product}-inc{mode}-{block}.json',),clean_sync_ttl=True))
                    self.assertTrue(c.allowed('records',(f'inc{mode}',f'{product}-{block}.jsonl.logs','.complete.stdout'),clean_sync_ttl=True))
        for name in ('stress-cargo-sprig-count-inc0-0.json','stress-cargo-sprig-narrow-inc1-5.json','stress-cargo-layerfs-inc0-0.json','stress-cargo-sprig-read-ttl-inc0-6.json','stress-cargo-directory-abc-products.json','stress-cargo-latest-direct-identity.json'):
            self.assertFalse(c.allowed('results',(name,),clean_sync_ttl=True),name)
        for name in ('cst-source-selection.json','cst-read-ttl-source-hashes.txt','cst-clean-sync-tests.txt','stress-cargo-clean-sync-ttl-plan.json'):
            self.assertTrue(c.allowed('results',(name,),clean_sync_ttl=True));self.assertFalse(c.allowed('results',(name,)))
        self.assertFalse(c.allowed('results',('stress-cargo-sprig-read-ttl-inc0-0.json',),abc=True))
        self.assertTrue(c.allowed('results',('stress-cargo-sprig-count-inc0-5.json',),abc=True))
    def test_empty_early_failure_is_explicitly_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            results,temporary,out=self.roots(tmp)
            with patch.object(c,'ABC_EVIDENCE_CAP',1):
                with self.assertRaisesRegex(ValueError,'no archive copied'):self.collect(results,temporary,out)
            self.assertFalse(out.exists())
            self.collect(results,temporary,out);receipt=json.loads((out/'collection.json').read_text())
            self.assertEqual(receipt['series'],'sprig-stress-cargo-clean-sync-ttl-v1');self.assertEqual(receipt['budgetBytes'],1024**3)
            self.assertEqual(receipt['files'],[])
    def test_oversize_full_plan_rejected_before_copy_with_sources_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            results,temporary,out=self.roots(tmp);source=results/'cst-read-ttl-release-build.log';source.write_bytes(b'x'*65536)
            before=source.read_bytes()
            with patch.object(c,'ABC_EVIDENCE_CAP',32768),patch.object(c,'ABC_MANIFEST_RESERVE',8192):
                with self.assertRaisesRegex(ValueError,'no archive copied'):self.collect(results,temporary,out)
            self.assertFalse(out.exists());self.assertEqual(source.read_bytes(),before)
    def test_all36_and_hidden_archives_preserved_without_old_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            results,temporary,out=self.roots(tmp);data=b'complete raw bytes\n'
            for mode in (0,1):
                report=self.report(mode);report['complete']=True
                for block in range(6):
                    for product in c.CLEAN_SYNC_TTL_PRODUCTS:
                        directory=temporary/f'stress-cargo-records/inc{mode}/{product}-{block}.jsonl.logs';directory.mkdir(parents=True)
                        source=directory/'.complete.stdout';source.write_bytes(data)
                        sample={'ok':True,'completeLogArchive':[{'archived':str(source),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
                        (results/f'stress-cargo-{product}-inc{mode}-{block}.json').write_text(json.dumps(sample))
                        report['records'].append(dict(product=product,round=block,incremental=mode,sample=sample))
                (results/f'stress-cargo-clean-sync-ttl-{mode}.json').write_text(json.dumps(report))
            (results/'stress-cargo-directory-abc-products.json').write_text('not this series')
            (temporary/'stress-cargo-records/inc0/sprig-count-0.jsonl.logs').symlink_to('/nonexistent-not-owned',target_is_directory=True)
            self.collect(results,temporary,out);receipt=json.loads((out/'collection.json').read_text())
            self.assertTrue(receipt['complete']);self.assertEqual(receipt['declaredArchiveVerification']['sampleDeclarations'],72)
            self.assertEqual(receipt['declaredArchiveVerification']['verifiedUniqueFiles'],36)
            self.assertFalse((out/'results/stress-cargo-directory-abc-products.json').exists())
            self.assertEqual((out/'records/inc1/sprig-read-ttl-5.jsonl.logs/.complete.stdout').read_bytes(),data)
    def test_malformed_or_historical_report_retained_as_failure(self):
        for failure in ('old_schema','old_experiment','wrong_rounds','wrong_mode','old_label','duplicate','bad_round','wrong_record_mode','complete_short'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                results,temporary,out=self.roots(tmp);report=self.report();record=dict(product='sprig-read-ttl',round=5,incremental=0,status='not-run');report['records']=[record]
                if failure=='old_schema':report['schema']='sprig-stress-cargo-directory-abc-v1'
                if failure=='old_experiment':report['abcExperiment']=c.ABC_EXPERIMENT
                if failure=='wrong_rounds':report['rounds']=4
                if failure=='wrong_mode':report['incremental']=1
                if failure=='old_label':record['product']='sprig-narrow'
                if failure=='duplicate':report['records'].append(dict(record))
                if failure=='bad_round':record['round']=6
                if failure=='wrong_record_mode':record['incremental']=True
                if failure=='complete_short':report['complete']=True
                source=results/'stress-cargo-clean-sync-ttl-0.json';source.write_text(json.dumps(report));before=source.read_bytes()
                with self.assertRaisesRegex(ValueError,'completeness failed'):self.collect(results,temporary,out)
                self.assertFalse(json.loads((out/'collection.json').read_text())['complete'])
                self.assertEqual(source.read_bytes(),before);self.assertEqual((out/'results'/source.name).read_bytes(),before)
    def test_missing_declared_archive_is_not_a_complete_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            results,temporary,out=self.roots(tmp);path=temporary/'stress-cargo-records/inc0/sprig-clean-sync-0.jsonl.logs/missing.log'
            sample={'ok':True,'completeLogArchive':[{'archived':str(path),'bytes':1,'sha256':'a'*64}]}
            (results/'stress-cargo-sprig-clean-sync-inc0-0.json').write_text(json.dumps(sample))
            with self.assertRaisesRegex(ValueError,'completeness failed'):self.collect(results,temporary,out)
            self.assertFalse(json.loads((out/'collection.json').read_text())['complete'])
    def test_explicit_modes_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            results,temporary,out=self.roots(tmp)
            for other in ('abc','latest_direct'):
                with self.assertRaisesRegex(ValueError,'mutually exclusive'):
                    c.collect(results,temporary,out,os.getuid(),os.getgid(),clean_sync_ttl=True,**{other:True})
                self.assertFalse(out.exists())
    def test_final_budget_failure_preserves_authoritative_incomplete_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            results,temporary,out=self.roots(tmp);(results/'environment.txt').write_text('retained')
            original=c.verify_declared_archives
            def overflow(*args,**kwargs):
                value=original(*args,**kwargs);c.ABC_EVIDENCE_CAP=1;return value
            with patch.object(c,'ABC_EVIDENCE_CAP',c.ABC_EVIDENCE_CAP),patch.object(c,'verify_declared_archives',side_effect=overflow):
                with self.assertRaisesRegex(ValueError,'budget exceeded'):self.collect(results,temporary,out)
            self.assertFalse(json.loads((out/'collection.json').read_text())['complete'])
            self.assertEqual((results/'environment.txt').read_text(),'retained')

if __name__=='__main__':unittest.main()
