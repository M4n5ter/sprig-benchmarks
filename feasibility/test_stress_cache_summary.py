"""Synthetic complete/incomplete nine-sample screen summaries; no benchmark."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from stress_cache_ablation import PINS,SCHEMA,digest,order
from stress_cache_summary import summarize
from test_stress_cache_ablation import sample_fixture,canary_fixture


def fixture(root):
    results=root/'stress-results';results.mkdir()
    products=[dict(label=label,type='sprig',sha=sha,binary=f'/bin/{label}',binarySha256=str(i+1)*64,sourcePath=f'/sources/{label}') for i,(label,sha) in enumerate(PINS.items())]
    report=dict(schema=SCHEMA,ablationStage='forward-latin',cell='files-4096',backends=['native'],rounds=3,expectedRecords=9,complete=True,status='passed',products=products,records=[],noopCheckpoint=True,outputDirectory=str(results),
                sharedAblationBudget=dict(jobStartedEpochSeconds=100,jobDeadlineEpochSeconds=2500,measurementStartedEpochSeconds=500,measurementDeadlineEpochSeconds=1700,maximumMeasurementSeconds=1200),
                canaryPrerequisite={'path':'/prior/stress-results/stress-comparison.json','sha256':'f'*64})
    canary=canary_fixture(root/'canary',products,report['sharedAblationBudget'])
    report['canaryPrerequisite']={'path':str(canary),'sha256':digest(canary.read_bytes())}
    for round_no in range(3):
        for product in order(products,round_no,'forward-latin'):
            identity=f"native-{product['label']}-{round_no}";part=root/identity;part.mkdir()
            sample,p,source,sha,original=sample_fixture(part,product,identity)
            logs=original/(identity+'-steps.jsonl.logs');shutil.move(str(logs),str(results/logs.name))
            for item in sample['completeLogArchive']:item['archived']=str(results/logs.name/Path(item['archived']).name)
            ratio={'main':1,'inventory':1.05,'admission':.8}[product['label']]
            sample['restore_seconds']*=ratio
            raw=json.dumps(sample).encode();(results/(identity+'-stdout.json')).write_bytes(raw)
            report['records'].append(dict(identity=identity,product=product['label'],round=round_no,correct=True,status='passed',sampleReturncode=0,sample=sample,rawReportSha256=digest(raw),wholeSampleSubprocessWallSeconds=12*ratio))
            report['fixtureSha256']=sha
    (results/'fixture.json').write_text(json.dumps(source,indent=2))
    path=results/'stress-comparison.json';path.write_text(json.dumps(report))
    return path,source['parameters']


class SummaryTests(unittest.TestCase):
    def checked(self,path,params):
        with patch('stress_cache_summary.cache_cell_parameters',return_value=(params,True)):return summarize(path,path.parent.parent/'canary'/'stress-results'/'stress-comparison.json')
    def test_all_three_ablation_edges_keep_regressions_and_small_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,params=fixture(Path(tmp));result=self.checked(path,params)
            self.assertTrue(result['complete'],result['errors']);self.assertEqual(len(result['records']),9)
            self.assertEqual(set(result['comparisons']),{'main-to-inventory','inventory-to-admission','main-to-admission'})
            metric=result['comparisons']['main-to-inventory']['wholeSampleSeconds']
            self.assertAlmostEqual(metric['geometricMeanPairedRatio'],1.05);self.assertEqual(metric['n'],3);self.assertIsNone(metric['p99'])
            self.assertTrue(all(p['percentChange']>0 for p in metric['pairs']))
    def test_all_failures_missing_raw_and_wrong_latin_order_suppress_comparisons(self):
        changes=[lambda r:r.update(complete=False,status='failed',error='kept'),lambda r:r['records'].pop(),lambda r:r['records'].reverse(),lambda r:r['products'][0].update(sha='0'*40),lambda r:r['sharedAblationBudget'].update(measurementDeadlineEpochSeconds=1701),lambda r:r.update(ablationStage='reverse-latin'),lambda r:r['canaryPrerequisite'].update(sha256='0'*64),lambda r:r['products'][0].update(binarySha256='invalid')]
        for change in changes:
            with tempfile.TemporaryDirectory() as tmp:
                path,params=fixture(Path(tmp));report=json.loads(path.read_text());change(report);path.write_text(json.dumps(report))
                result=self.checked(path,params);self.assertFalse(result['complete']);self.assertIsNone(result['comparisons']);self.assertEqual(len(result['records']),len(report['records']))
        with tempfile.TemporaryDirectory() as tmp:
            path,params=fixture(Path(tmp));(path.parent/'native-main-0-stdout.json').unlink();result=self.checked(path,params)
            self.assertFalse(result['complete']);self.assertEqual(len(result['records']),9)
    def test_invalid_phase_in_every_sample_is_rejected_not_dropped(self):
        for invalid in (-1,float('nan'),float('inf'),True,'12'):
            with self.subTest(invalid=invalid),tempfile.TemporaryDirectory() as tmp:
                path,params=fixture(Path(tmp));report=json.loads(path.read_text())
                for row in report['records']:
                    row['sample']['restore_seconds']=invalid
                    raw=json.dumps(row['sample']).encode()
                    (path.parent/(row['identity']+'-stdout.json')).write_bytes(raw)
                    row['rawReportSha256']=digest(raw)
                path.write_text(json.dumps(report));result=self.checked(path,params)
                self.assertFalse(result['complete']);self.assertIsNone(result['comparisons']);self.assertEqual(len(result['records']),9)
                self.assertTrue(all('invalid measured metric' in row.get('validationError','') for row in result['records']),result['errors'])

    def test_omitted_canary_suppresses_all_ratios(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,params=fixture(Path(tmp));result=summarize(path)
            self.assertFalse(result['complete']);self.assertIsNone(result['comparisons'])

    def test_missing_report_is_recorded_not_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=summarize(Path(tmp)/'missing.json');self.assertFalse(result['complete']);self.assertTrue(result['errors']);self.assertIsNone(result['comparisons'])

if __name__=='__main__':unittest.main()
