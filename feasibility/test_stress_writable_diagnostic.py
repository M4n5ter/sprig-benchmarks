"""Synthetic-only identity/oracle/transport/collection gates; no product, Rust, mount or Docker."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_stress_cargo_ab_summary import fixture as ordinary_fixture
from test_stress_writable_diagnostic_trace import pressure_report,clock_proof,sample_trace,raw_log,ORIGIN,trace_from,event
import stress_writable_diagnostic_audit as audit
import stress_writable_diagnostic_collect as collect
import stress_writable_diagnostic_sample as sampler
from stress_cargo_sample import StressCargoSample,stress_report


def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n');return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_plan(sample):
    rows=sample['completeLogArchive'];size=sum(r['bytes'] for r in rows)
    sample['diagnosticArchiveAdmission']=dict(admitted=True,maximumBytes=1024**3,reportReserveBytes=sampler.REPORT_RESERVE_BYTES,collectionReserveBytes=2*1024**2,existingNamedExternalBytes=1000,plannedArchiveBytes=size,projectedAdmissionBytes=1000+size+sampler.REPORT_RESERVE_BYTES+2*1024**2,plannedFiles=[{k:r[k] for k in ('source','archived','bytes')} for r in rows])
    sample['diagnosticArchiveCopy']=dict(complete=True,completedFiles=len(rows),sourceFilesRetained=True)


def fixture(base):
    seed=base/'seed';seed.mkdir();paths,_=ordinary_fixture(seed);sample=json.loads((paths[0].parent/'stress-cargo-sprig-baseline-inc0-0.json').read_text())
    results=base/'results';results.mkdir();temporary=base/'temporary';temporary.mkdir();archives=temporary/'stress-writable-diagnostic-records';archives.mkdir()
    manifest=dict(schema=audit.MANIFEST_SCHEMA,sha=sampler.SOURCE_SHA,parent=sampler.PARENT_SHA,algorithmBase=sampler.ALGORITHM_BASE,binary='/fixed/diagnostic-sprig',binarySha256='a'*64,sourcePath='/fixed/source',pressureScriptSha256=sampler.PRESSURE_SHA)
    manifest_path=results/'writable-diagnostic-identity.json';manifest_hash=dump(manifest_path,manifest)
    run=dict(schema=audit.RUN_SCHEMA,complete=True,status='passed',identity=manifest,identitySha256=manifest_hash,expectedRecords=4,incremental=0,imageBytes=4*1024**3,image=sample['image'],protocolSha256=sample['protocolSha256'],order=[dict(arm=a,pair=p) for a,p in audit.ORDER],records=[],notRun=[],artifactBudgetBytes=1024**3,sharedJobBudget=dict(startedEpochSeconds=100,deadlineEpochSeconds=2500,minimumSampleSeconds=180,cleanupReserveSeconds=300))
    for arm,pair in audit.ORDER:
        s=copy.deepcopy(sample);s.update(schema=sampler.SCHEMA,diagnosticArm=arm,production_sha=sampler.SOURCE_SHA,binarySha256=manifest['binarySha256'],root='/original/sample',transport_seconds={'exec':1.0},diagnosticEnvironment={'SPRIG_WRITABLE_DIAGNOSTICS':'1' if arm=='on' else None,'SPRIG_LIFECYCLE_TRACE':None},diagnosticSource={k:manifest[k] for k in ('sha','parent','algorithmBase')},diagnosticCommandBindings=[dict(sequence=1,executable=manifest['binary'],arm=arm,environmentValue='1' if arm=='on' else None)],checkpointGeneration={'before':'g1','after':'g2'})
        pressure=pressure_report();pressure_raw=json.dumps(pressure)+'\n';s.update(normalPressure=pressure,normalPressureScriptSha256=sampler.PRESSURE_SHA,normalPressureRawSha256=hashlib.sha256(pressure_raw.encode()).hexdigest());s['phase_seconds']['normal_pressure']=1.0
        tree=s['checkpointTreeOracle'];spec=pressure['spec']
        def entry(name):return dict(path=name,type='file',mode=420,mtime_ns=int(spec['witnessMtimeNs']),size=64,sha256='e'*64)
        obs=entry('pressure-rename2/observations.json');obs['sha256']=s['normalPressureRawSha256'];tree['entries'].append(obs)
        for worker in (0,1):
            d=f'pressure-rename2/worker-{worker}';tree['entries'] += [entry(d+f'/unrelated/{i:04d}') for i in range(1024)]
            for name in ('witness','witness-link'):
                row=entry(d+'/active/'+name);row['mode']=0o640;tree['entries'].append(row)
            row=entry(d+'/active/symlink');row.update(type='symlink',target='witness');tree['entries'].append(row);tree['hardlink_groups'].append([d+'/active/witness',d+'/active/witness-link'])
        logs=archives/'inc0'/f'{arm}-{pair}.jsonl.logs';logs.mkdir(parents=True);s['completeLogArchive']=[];s['commands']=[]
        def archived(name,source,body):
            (logs/name).write_bytes(body);row=dict(source=source,archived=str(logs/name),bytes=len(body),sha256=hashlib.sha256(body).hexdigest());s['completeLogArchive'].append(row);return row
        for purpose in ('pre_checkpoint_oracle','restore_verify'):
            body=json.dumps(tree)+'\n';source='/original/'+purpose+'.stdout';archived(purpose+'.stdout',source,body.encode());s['commands'].append(dict(purpose=purpose,returncode=0,stdoutPath=source,stdout=body))
        source='/original/pressure.stdout';archived('pressure.stdout',source,pressure_raw.encode());s['commands'].append(dict(purpose='normal_pressure',returncode=0,stdoutPath=source,stdout=pressure_raw,stdinSha256=sampler.PRESSURE_SHA,containerId='container-fixed',workspaceGeneration='g1'))
        proof=clock_proof();proof.update(hostBeforeNs=ORIGIN-3,containerMonotonicNs=ORIGIN-2,hostAfterNs=ORIGIN-1);s['diagnosticClockProof']=proof
        source='/original/clock.stdout';body=json.dumps(dict(domain=proof['container'],monotonicNs=proof['containerMonotonicNs']))+'\n';archived('clock.stdout',source,body.encode());s['commands'].append(dict(purpose='diagnostic_clock_domain',returncode=0,stdinSha256=hashlib.sha256(sampler.CLOCK_CODE.encode()).hexdigest(),stdoutPath=source,stdout=body,containerId='container-fixed',workspaceGeneration='g1'));s['diagnosticClockBinding']=dict(containerId='container-fixed',workspaceGeneration='g1',stdoutPath=source)
        rows=[]
        for i,generation in enumerate(('g0','g0','g1','g2','g3')):
            source=f'/original/sample/library/native/{generation}/writable-{100+i}-{1000+i}.log';body=raw_log(sample_trace()) if arm=='on' else b'';row=archived(f'{i:06}-writable-{100+i}-{1000+i}.log',source,body);rows.append(dict(source=source,bytes=len(body),allocatedBytes=4096 if body else 0,sha256=row['sha256']))
        s['postNormalCleanupSpace']=dict(deviceBytes=4*1024**3,availableBytes=2*1024**3,filesystemUsedBytes=500000,sourceLogs=rows,sourceLogLogicalBytes=sum(x['bytes'] for x in rows),sourceLogAllocatedBytes=sum(x['allocatedBytes'] for x in rows))
        archive_plan(s)
        name=f'stress-writable-diagnostic-{arm}-{pair}.json';digest=dump(results/name,s);run['records'].append(dict(arm=arm,pair=pair,correct=True,sampleReturncode=0,rawReportPath='results/'+name,rawReportSha256=digest,wholeSampleSubprocessWallSeconds=10+(arm=='on'),capacityAdmission=dict(availableBytes=2*1024**3,requiredBytes=640*1024**2,deviceBytes=4*1024**3,targetAllocatedBytes=1,fixtureLogicalBytes=1,pressureReserveBytes=128*1024**2,admitted=True),postSampleArtifactInventory=dict(bytes=1000,collectionReserveBytes=2*1024**2,admissionBytes=1000+2*1024**2,maximumBytes=1024**3,completeNamedInventory=True),budgetAdmission=dict(startedEpochSeconds=100,deadlineEpochSeconds=2500,admitted=True,workReserveSeconds=180,cleanupReserveSeconds=300,requiredSeconds=480,remainingSeconds=1000),postRuntimeBudgetAdmission=dict(startedEpochSeconds=100,deadlineEpochSeconds=2500,admitted=True,workReserveSeconds=180,cleanupReserveSeconds=300,requiredSeconds=480,remainingSeconds=900)))
    run_path=results/'writable-diagnostic-canary.json';dump(run_path,run);return run_path,manifest_path,archives,temporary


class DiagnosticTests(unittest.TestCase):
    def test_complete_four_raw_oracles_and_noise_pairs(self):
        with tempfile.TemporaryDirectory() as t:
            path,manifest,archives,_=fixture(Path(t));result=audit.summarize(path,manifest,archives)
            self.assertTrue(result['complete'],result['errors']);self.assertEqual(len(result['records']),4)
            self.assertEqual(result['comparisons']['wholeSampleSeconds']['n'],2)
            self.assertIsNone(result['comparisons']['wholeSampleSeconds']['p99'])
            self.assertAlmostEqual(result['comparisons']['wholeSampleSeconds']['medianPairedRatio'],1.1)
            self.assertIsNone(result['records'][0]['analysis']);self.assertIsNotNone(result['records'][1]['analysis'])
            self.assertFalse(result['automaticRetry']);self.assertFalse(result['automaticFallback']);self.assertIn('wrapperLoop.worker0Seconds',result['comparisons']);self.assertIn('wrapperOperation.windowSeconds',result['comparisons'])

    def test_identity_order_missing_and_failure_suppress_every_ratio(self):
        changes=(lambda r:r.update(schema='sprig-stress-cargo-own-ab-v2'),lambda r:r.update(complete=False),lambda r:r['records'].pop(),lambda r:r['records'].reverse(),lambda r:r['records'][0].update(sampleReturncode=1),lambda r:r['records'][0].update(rawReportSha256='0'*64),lambda r:r.update(incremental=1),lambda r:r.update(imageBytes=8*1024**3),lambda r:r['sharedJobBudget'].update(deadlineEpochSeconds=2501),lambda r:r['records'][0]['postRuntimeBudgetAdmission'].update(remainingSeconds=479),lambda r:r.update(artifactBudgetBytes=2*1024**3),lambda r:r['records'][0].update(pair=False),lambda r:r['records'][0]['capacityAdmission'].update(availableBytes=1),lambda r:r['records'][0]['postSampleArtifactInventory'].update(admissionBytes=2*1024**3))
        with tempfile.TemporaryDirectory() as t:
            path,manifest,archives,_=fixture(Path(t));original=json.loads(path.read_text())
            for change in changes:
                with self.subTest(change=change):
                    r=copy.deepcopy(original);change(r);dump(path,r);value=audit.summarize(path,manifest,archives);self.assertFalse(value['complete']);self.assertIsNone(value['comparisons'])

    def test_wrong_generation_clock_env_and_postcleanup_refused(self):
        with tempfile.TemporaryDirectory() as t:
            path,manifest,archives,_=fixture(Path(t));raw=path.parent/'stress-writable-diagnostic-on-0.json';original=json.loads(raw.read_text());run=json.loads(path.read_text())
            changes=(lambda s:s['checkpointGeneration'].update(before='g2'),lambda s:s.update(diagnosticArm='off'),lambda s:s['diagnosticEnvironment'].update(SPRIG_WRITABLE_DIAGNOSTICS=None),lambda s:s['diagnosticClockBinding'].update(containerId='other'),lambda s:s['postNormalCleanupSpace'].update(availableBytes=1),lambda s:s['postNormalCleanupSpace']['sourceLogs'].pop(),lambda s:s['diagnosticClockProof'].update(hostAfterNs=True),lambda s:s['lifecycle']['cleanup'].update(complete=False),lambda s:s['commands'][-1].update(stdinSha256='0'*64))
            for change in changes:
                with self.subTest(change=change):
                    s=copy.deepcopy(original);change(s);dump(raw,s)
                    with self.assertRaises(ValueError):audit.audit_sample(raw,manifest,run['image'],run['protocolSha256'],archives,'on',0)

    def test_single_elf_fixed_manifest_and_primary_trace_guard_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            _,manifest,_,_=fixture(Path(t));value=json.loads(manifest.read_text())
            for key,wrong in [('sha','0'*40),('parent','0'*40),('pressureScriptSha256','0'*64),('binary','relative')]:
                v=copy.deepcopy(value);v[key]=wrong
                with self.assertRaises(ValueError):audit.validate_identity(v)
        with patch.dict(os.environ,{'SPRIG_WRITABLE_DIAGNOSTICS':'1'},clear=True):
            with self.assertRaises(Exception):StressCargoSample(stress_report()).prepare(SimpleNamespace())
            with self.assertRaises(Exception):sampler.command_environment('on',True)
        with patch.dict(os.environ,{},clear=True):
            self.assertNotIn('SPRIG_WRITABLE_DIAGNOSTICS',sampler.command_environment('off',True))
            self.assertNotIn('SPRIG_WRITABLE_DIAGNOSTICS',sampler.command_environment('on',False))
            self.assertEqual(sampler.command_environment('on',True)['SPRIG_WRITABLE_DIAGNOSTICS'],'1')

    def test_collector_complete_inventory_hashes_and_cap(self):
        with tempfile.TemporaryDirectory() as t:
            path,_,_,temporary=fixture(Path(t));base=Path(t);destination=base/'collected'
            before=collect.inventory(path.parent,temporary);self.assertLess(before['admissionBytes'],1024**3)
            with patch.object(collect.os,'chown'),patch.object(collect.os,'fchown'):
                result=collect.collect(path.parent,temporary,destination,1234,1234)
            self.assertTrue(result['declaredArchiveVerification']['ok']);self.assertEqual(result['declaredArchiveVerification']['samples'],4)
            self.assertEqual(result['completeBytes'],before['bytes'])
            self.assertTrue(all(hashlib.sha256((destination/r['path']).read_bytes()).hexdigest()==r['sha256'] for r in result['files']))
            with patch.object(collect,'CAP',before['bytes']):
                with self.assertRaises(ValueError):collect.inventory(path.parent,temporary)
            (path.parent/'environment.txt').symlink_to('/dev/null')
            with self.assertRaises(ValueError):collect.inventory(path.parent,temporary)

    def test_collector_preserves_failed_raw_and_reports_missing_archive(self):
        with tempfile.TemporaryDirectory() as t:
            path,_,archives,temporary=fixture(Path(t));raw=path.parent/'stress-writable-diagnostic-on-0.json';s=json.loads(raw.read_text());s['ok']=False;s['error']={'message':'retained synthetic validation failure'};dump(raw,s)
            target=archives/'inc0/on-0.jsonl.logs/clock.stdout';target.unlink()
            with patch.object(collect.os,'chown'),patch.object(collect.os,'fchown'):
                with self.assertRaises(ValueError):collect.collect(path.parent,temporary,Path(t)/'collected',1234,1234)
            self.assertEqual(json.loads((Path(t)/'collected/results'/raw.name).read_text())['error'],s['error'])
            self.assertFalse(json.loads((Path(t)/'collected/collection.json').read_text())['declaredArchiveVerification']['ok'])

    def test_sampler_product_only_env_no_child_clock_or_workload(self):
        s=sampler.DiagnosticSample(stress_report());s.arm='on';s.binary=Path('/fixed/sprig');s.logs=None
        answer=SimpleNamespace(stdout='ok',stderr='',returncode=0)
        with patch.dict(os.environ,{},clear=True),patch.object(sampler.subprocess,'run',return_value=answer) as run,patch.object(s,'event'):
            s.command(['/fixed/sprig','show']);self.assertEqual(run.call_args.kwargs['env']['SPRIG_WRITABLE_DIAGNOSTICS'],'1')
            s.command(['docker','inspect']);self.assertNotIn('SPRIG_WRITABLE_DIAGNOSTICS',run.call_args.kwargs['env'])
        self.assertEqual(len(s.report['diagnosticCommandBindings']),1)

    def test_all_five_enabled_logs_must_have_clean_normal_footer(self):
        with tempfile.TemporaryDirectory() as t:
            path,manifest,archives,_=fixture(Path(t));raw=path.parent/'stress-writable-diagnostic-on-0.json';original=json.loads(raw.read_text());run=json.loads(path.read_text())
            for bad in (trace_from([]),trace_from([event()]),trace_from([event('journal_sync',ORIGIN-10,ORIGIN-9,success=False),event('journal_sync',ORIGIN+30000,ORIGIN+30001)])):
                s=copy.deepcopy(original);row=next(r for r in s['completeLogArchive'] if '/g0/writable-' in r['source']);body=raw_log(bad);target=archives/'inc0/on-0.jsonl.logs'/Path(row['archived']).name;target.write_bytes(body);row.update(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
                source=next(x for x in s['postNormalCleanupSpace']['sourceLogs'] if x['source']==row['source']);source.update(bytes=row['bytes'],sha256=row['sha256']);s['postNormalCleanupSpace']['sourceLogLogicalBytes']=sum(r['bytes'] for r in s['postNormalCleanupSpace']['sourceLogs']);archive_plan(s);dump(raw,s)
                with self.assertRaisesRegex(ValueError,'every enabled log'):audit.audit_sample(raw,manifest,run['image'],run['protocolSha256'],archives,'on',0)

    def test_five_logs_must_span_exactly_four_generation_directories(self):
        with tempfile.TemporaryDirectory() as t:
            path,manifest,archives,_=fixture(Path(t));raw=path.parent/'stress-writable-diagnostic-on-0.json';s=json.loads(raw.read_text());run=json.loads(path.read_text())
            row=next(r for r in s['completeLogArchive'] if '/g0/writable-' in r['source']);old=row['source'];row['source']=old.replace('/g0/','/g-extra/');source=next(r for r in s['postNormalCleanupSpace']['sourceLogs'] if r['source']==old);source['source']=row['source'];archive_plan(s);dump(raw,s)
            with self.assertRaisesRegex(ValueError,'four generations'):audit.audit_sample(raw,manifest,run['image'],run['protocolSha256'],archives,'on',0)

    def test_log_allocation_inventory_follows_sync_and_streams_complete_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'sample';root.mkdir();library=root/'library';log=library/'native/g1/writable-123-456.log';log.parent.mkdir(parents=True);log.write_bytes(b'x'*(1024**2+17))
            s=sampler.DiagnosticSample(stress_report());s.root=root;s.library=library;s.logs=root/'logs';s.logs.mkdir();s.records=Path(t)/'ledger.jsonl';s.records.write_text('{}\n');s.artifact_results=Path(t)/'results';s.artifact_results.mkdir();s.report['lifecycle']['cleanup']['complete']=True
            synced=[];old_lstat=Path.lstat
            def inspect(p,*args,**kwargs):
                if p==log:self.assertTrue(synced,'allocation sampled before sync')
                return old_lstat(p,*args,**kwargs)
            def command(args,**kwargs):
                self.assertFalse(kwargs['record_event'])
                if args[2]=='sync':synced.append(True);return ''
                if args[2]=='usage':return 'Used: 100000\nDevice size: 4294967296\n'
                return 'Data, single: total=1, used=1'
            with patch.dict(os.environ,{'RUNNER_TEMP':t}),patch.object(s,'command',side_effect=command),patch.object(Path,'lstat',inspect),patch.object(Path,'read_bytes',side_effect=AssertionError('unbounded read_bytes forbidden for source/archive logs')):
                s.post_cleanup_observation();s.preserve_logs()
            row=s.report['postNormalCleanupSpace']['sourceLogs'][0];self.assertEqual(row['bytes'],1024**2+17);self.assertEqual(row['allocatedBytes'],log.stat().st_blocks*512)
            archived=next(r for r in s.report['completeLogArchive'] if r['source']==str(log));self.assertEqual(archived['sha256'],row['sha256']);self.assertEqual(Path(archived['archived']).stat().st_size,row['bytes'])

    def test_oversize_whole_archive_preflight_copies_nothing_and_loses_no_source(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);root=base/'sample';root.mkdir();s=sampler.DiagnosticSample(stress_report());s.root=root;s.library=root/'library';s.logs=root/'logs';s.logs.mkdir();s.records=base/'ledger.jsonl';s.records.write_text('{}\n');s.artifact_results=base/'results';s.artifact_results.mkdir()
            log=s.library/'native/g1/writable-123-456.log';log.parent.mkdir(parents=True);body=b'complete synthetic oversized plan';log.write_bytes(body)
            cap=sampler.REPORT_RESERVE_BYTES+sampler.COLLECTION_RESERVE+len(body)-1
            with patch.dict(os.environ,{'RUNNER_TEMP':t}),patch.object(sampler,'ARTIFACT_BUDGET_BYTES',cap):
                with self.assertRaisesRegex(Exception,'no subset copied'):s.preserve_logs()
            self.assertFalse(Path(str(s.records)+'.logs').exists());self.assertEqual(log.read_bytes(),body)
            self.assertFalse(s.report['diagnosticArchiveAdmission']['admitted']);self.assertNotIn('completeLogArchive',s.report)
            self.assertEqual(s.report['diagnosticArchiveAdmission']['plannedArchiveBytes'],len(body))

    def test_source_growth_after_preflight_fails_closed_and_retains_partial_metadata(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);root=base/'sample';root.mkdir();s=sampler.DiagnosticSample(stress_report());s.root=root;s.library=root/'library';s.logs=root/'logs';s.logs.mkdir();s.records=base/'ledger.jsonl';s.records.write_text('{}\n');s.artifact_results=base/'results';s.artifact_results.mkdir()
            log=s.library/'native/g1/writable-123-456.log';log.parent.mkdir(parents=True);log.write_bytes(b'original');old_open=sampler.os.open
            def changed(file,flags,*args,**kwargs):
                if Path(file)==log:
                    with log.open('ab') as f:f.write(b'changed')
                return old_open(file,flags,*args,**kwargs)
            with patch.dict(os.environ,{'RUNNER_TEMP':t}),patch.object(sampler.os,'open',side_effect=changed):
                with self.assertRaisesRegex(Exception,'source changed'):s.preserve_logs()
            self.assertEqual(log.read_bytes(),b'originalchanged');self.assertNotIn('completeLogArchive',s.report)
            self.assertFalse(s.report['diagnosticArchiveCopy']['complete']);self.assertTrue(s.report['diagnosticArchiveCopy']['failedFile']['sourceRetained']);self.assertEqual(s.report['diagnosticArchiveCopy']['failedFile']['bytesWritten'],0)


if __name__=='__main__':unittest.main()
