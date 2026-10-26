"""Preparation only. Root/benchmark owner may run these pure fixture validators; no Cargo/ELF execution."""
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('run_release',HERE/'run_release.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


def approved_manifest():
    m=json.loads((HERE/'manifest.template.json').read_text())
    m['approvedForExecution']=True
    m['variants']['narrow']={'productionCommit':'a'*40,'expectedTests':list(m['variants']['count']['expectedTests'])}
    m['toolchain']['requested']='1.99.1'
    return m


def receipts(m):
    result={}
    for index,variant in enumerate(r.VARIANTS):
        result[variant]={'schema':'sprig-release-build-receipt-v1','ok':True,'variant':variant,'productionCommit':m['variants'][variant]['productionCommit'],'manifestSha256':'f'*64,
          'binary':{'sha256':str(index+1)*64},'budget':{'clockSha256':'c'*64},
          'rootArtifact':{'passed':True,'compilerArtifact':{'fresh':False,'profile':{'opt_level':'3','debug_assertions':False,'overflow_checks':False}}},
          'inventory':{'passed':True,'actualNames':m['variants'][variant]['expectedTests']},
          'source':{'appendOnly':True,'instrumentationSha256':m['instrumentationSha256']},
          'toolchain':{tool:{'sha256':'d'*64,'versionSha256':'e'*64} for tool in ['cargo','rustc']}}
    return result


class ReleaseProtocolTests(unittest.TestCase):
    def test_final_accounting_uses_strict_shared_audit(self):
        helper=mock.Mock()
        helper.evidence_size.return_value=17
        with mock.patch.object(r,'accounting_helper',return_value=helper):
            self.assertEqual(r.allocated(Path('/owned/evidence')),17)
        helper.evidence_size.assert_called_once_with(Path('/owned/evidence'))
        source=(HERE/'run_release.py').read_text()
        self.assertIn("live_cleanup_root=fixture if suite=='lifecycle' else None",source)

    def test_pending_template_is_not_executable(self):
        with self.assertRaisesRegex(ValueError,'approved'):
            r.validate_manifest(json.loads((HERE/'manifest.template.json').read_text()))

    def test_missing_successor_or_inventory_is_not_executable(self):
        for field in ['productionCommit','expectedTests']:
            m=approved_manifest();m['variants']['narrow'][field]=None
            with self.assertRaises(ValueError):r.validate_manifest(m)

    def test_floating_compiler_rejected(self):
        for channel in ['stable','beta','nightly','']:
            m=approved_manifest();m['toolchain']['requested']=channel
            with self.assertRaises(ValueError):r.validate_manifest(m)

    def test_duplicate_variant_and_reduced_controls_rejected(self):
        m=approved_manifest();m['variants']['narrow']['productionCommit']=m['variants']['count']['productionCommit']
        with self.assertRaises(ValueError):r.validate_manifest(m)
        m=approved_manifest();m['profiles']['attr'].pop()
        with self.assertRaises(ValueError):r.validate_manifest(m)

    def test_caps_cannot_silently_expand(self):
        m=approved_manifest();m['limits']['admissionSeconds']+=1
        with self.assertRaises(ValueError):r.validate_manifest(m)

    def test_six_orders_balance_every_pair_and_position(self):
        m=r.validate_manifest(approved_manifest())
        orders=m['fullOrders']
        for a,b in itertools.combinations(r.VARIANTS,2):
            self.assertEqual(sum(order.index(a)<order.index(b) for order in orders),3)
        for variant in r.VARIANTS:
            self.assertEqual([sum(order[pos]==variant for order in orders) for pos in range(3)],[2,2,2])
        m['fullOrders'][5]=m['fullOrders'][0]
        with self.assertRaises(ValueError):r.validate_manifest(m)

    def test_schedule_keeps_canary_and_all_negative_controls(self):
        records=r.make_schedule(approved_manifest())
        self.assertEqual(len(records),411)
        self.assertTrue(all(row['status']=='not-run' for row in records))
        self.assertEqual(sum(row['phase']=='canary' for row in records),15)
        full=[row for row in records if row['phase']=='full']
        self.assertEqual(len(full),396)
        for suite,profile in {(row['suite'],row['profile']) for row in full}:
            self.assertEqual(len([row for row in full if row['suite']==suite and row['profile']==profile]),18)
        self.assertEqual(len({(row['suite'],row['profile']) for row in full}),22)

    def test_clock_requires_same_boot_and_never_resets(self):
        self.assertEqual(r.validate_clock({'startedMonotonic':100,'bootId':'boot'},200,'boot'),2500)
        for clock in [{'startedMonotonic':201,'bootId':'boot'},{'startedMonotonic':100,'bootId':'other'}, {'startedMonotonic':float('nan'),'bootId':'boot'}, {'startedMonotonic':True,'bootId':'boot'}]:
            with self.assertRaises(ValueError):r.validate_clock(clock,200,'boot')

    def test_distinct_fresh_release_artifacts_required(self):
        m=approved_manifest();good=receipts(m)
        r.validate_build_identity(good,m,'f'*64,'c'*64)
        modifications=[('fresh',True),('opt_level','0'),('debug_assertions',True),('overflow_checks',True)]
        for key,value in modifications:
            bad=copy.deepcopy(good)
            target=bad['count']['rootArtifact']['compilerArtifact']
            if key=='fresh':target[key]=value
            else:target['profile'][key]=value
            with self.assertRaises(ValueError):r.validate_build_identity(bad,m,'f'*64,'c'*64)
        bad=copy.deepcopy(good);bad['narrow']['binary']['sha256']=bad['count']['binary']['sha256']
        with self.assertRaisesRegex(ValueError,'identical ELF'):r.validate_build_identity(bad,m,'f'*64,'c'*64)

    def test_build_clock_cannot_reset_before_timing(self):
        m=approved_manifest();good=receipts(m)
        with self.assertRaisesRegex(ValueError,'setup clock'):
            r.validate_build_identity(good,m,'f'*64,'b'*64)

    def test_exact_inventory_instrumentation_compiler_required(self):
        m=approved_manifest();good=receipts(m)
        bad=copy.deepcopy(good);bad['narrow']['inventory']['actualNames']=bad['narrow']['inventory']['actualNames'][:-1]
        with self.assertRaises(ValueError):r.validate_build_identity(bad,m,'f'*64,'c'*64)
        bad=copy.deepcopy(good);bad['narrow']['source']['instrumentationSha256']={}
        with self.assertRaises(ValueError):r.validate_build_identity(bad,m,'f'*64,'c'*64)
        bad=copy.deepcopy(good);bad['narrow']['toolchain']['rustc']['versionSha256']='a'*64
        with self.assertRaises(ValueError):r.validate_build_identity(bad,m,'f'*64,'c'*64)

    def test_reference_validators_preserve_oracle_and_positive_exact_durations(self):
        m=approved_manifest();v=r.load_validator(m,HERE)
        for value in [True,0,-1,2**53]:
            with self.assertRaises(ValueError):v.validate_durations({'callsPerBatch':100,'batchesNanoseconds':[value]*32},100,32)
        with self.assertRaises(ValueError):v.validate_attr_report({'schema':'sprig-directory-attr-core-v3','oraclePassed':False},m['profiles']['attr'][0])

    def test_no_partial_results_can_be_summarized(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            r.summarize(r.make_schedule(approved_manifest()),None)

    def test_sparse_evidence_cannot_hide_logical_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            sparse=root/'sparse'
            with sparse.open('wb') as stream:stream.truncate(4*1024**2)
            info=sparse.stat()
            self.assertGreaterEqual(r.allocated(root),max(info.st_size,info.st_blocks*512))

    def test_release_payload_has_only_three_untimed_parent_widenings(self):
        m=json.loads((HERE/'manifest.template.json').read_text())
        inverses={
          'writable_directory_benchmark.rs':[('&& u64::from(n.parent) == *inode','&& n.parent == *inode')],
          'writable_directory_lifecycle_benchmark.rs':[('&& u64::from(n.parent) == inode','&& n.parent == inode'),
                                                     ('                u64::from(node.parent),','                node.parent,')]}
        for name,changes in inverses.items():
            data=(HERE/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),m['instrumentationSha256'][name])
            original=data.decode()
            for new,old in changes:
                self.assertEqual(original.count(new),1)
                original=original.replace(new,old)
            self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),m['instrumentationDifferenceFromDebug']['originalSha256'][name])

    def test_runner_uses_checked_publication_and_bounded_pipe_capture(self):
        source=(HERE/'run_release.py').read_text()
        self.assertIn('publication.checked_publish(',source)
        self.assertIn('publication.write_checked_json(',source)
        self.assertIn('publication.command(',source)
        self.assertIn("maximum_log_bytes=limits['maximumReportBytes']",source)
        self.assertNotIn('stdout=log',source)

    def test_three_way_ratios_are_same_block_not_pooled(self):
        m=approved_manifest();v=r.load_validator(m,HERE)
        records=r.make_schedule(m)
        for row in records:
            if row['phase']=='canary':continue
            row['status']='passed'
            cases=['root','hot','wide','flat'] if row['suite']=='attr' else ['create-initialization','replay-history']+v.MUTATION_CASES
            factor={'baseline':4,'count':2,'narrow':1}[row['variant']]
            value=(row['block']+1)*factor*100
            row['report']={'cases':[{'case':case,'batchesNanoseconds':[value,value+2,value-2],'callsPerBatch':1,
               'memoryAfterSamples':[{'vmRssKiB':factor*1024,'vmHwmKiB':factor*2048}],
               'memoryBeforeSamples':{'vmRssKiB':factor*1024,'vmHwmKiB':factor*2048}} for case in cases],
               'memory':{'ready':{'rssBytes':factor*1024,'highWaterBytes':factor*2048}}}
        comparisons,memory=r.summarize(records,v)
        self.assertEqual(len(comparisons),336)
        self.assertTrue(memory)
        for row in comparisons:
            expected=.25 if (row['baseline'],row['candidate'])==('baseline','narrow') else .5
            self.assertEqual(row['pairedRatios'],[expected]*6)
            self.assertAlmostEqual(row['geometricMeanPairedRatio'],expected)
            self.assertTrue(row['allSixFaster'])
        records[-1]['status']='failed'
        with self.assertRaises(ValueError):r.summarize(records,v)


if __name__=='__main__':unittest.main()
