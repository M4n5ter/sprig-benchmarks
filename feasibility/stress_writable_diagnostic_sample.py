#!/usr/bin/env python3
"""Separate opt-in wall/CPU diagnostic sample; primary sampler/trace-off guards stay unchanged."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import traceback
from cargo_transport_sample import CargoTransportSample
from current_sample import CurrentSample
from stress_cargo_sample import StressCargoSample,stress_report
from stress_cargo_prepare import validate_manifest
from cas_sample import Parser,require
from stress_cargo_pressure_long import SPEC
from stress_writable_diagnostic_trace import validate_clock_proof
from stress_writable_diagnostic_collect import candidates, CAP as ARTIFACT_BUDGET_BYTES, COLLECTION_RESERVE

SOURCE_SHA='73a462885c7b5bc88d64764152ab8fab08eba055'
PARENT_SHA='0f00ac4afbfc42b76c63a31833eabb07b82152f2'
ALGORITHM_BASE='b300693e01c652c1a9631c61b7a439892d8f75cd'
PRESSURE_SHA='58e5171ba44661a00065297155025a0c75839892cb5c21c770d22e84f4e0b501'
SCHEMA='sprig-writable-diagnostic-sample-v1'
LOG_CAP=16*1024**2
RAW_REPORT_MAX_BYTES=128*1024**2
REPORT_RESERVE_BYTES=192*1024**2  #128MiB raw transport plus bounded audit/report metadata, within1GiB
CLOCK_CODE='''import json,os,time
from pathlib import Path
def snapshot():
 return dict(timeNamespace=os.readlink('/proc/self/ns/time'),timeForChildrenNamespace=os.readlink('/proc/self/ns/time_for_children'),timensOffsets=Path('/proc/self/timens_offsets').read_text(),monotonicResolutionNs=round(time.clock_getres(time.CLOCK_MONOTONIC)*10**9),cpuResolutionNs=round(time.clock_getres(time.CLOCK_THREAD_CPUTIME_ID)*10**9))
print(json.dumps(dict(domain=snapshot(),monotonicNs=time.clock_gettime_ns(time.CLOCK_MONOTONIC))))
'''


def host_domain():
    return dict(timeNamespace=os.readlink('/proc/self/ns/time'),timeForChildrenNamespace=os.readlink('/proc/self/ns/time_for_children'),timensOffsets=Path('/proc/self/timens_offsets').read_text(),monotonicResolutionNs=round(time.clock_getres(time.CLOCK_MONOTONIC)*10**9),cpuResolutionNs=round(time.clock_getres(time.CLOCK_THREAD_CPUTIME_ID)*10**9))


def stream_digest(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def command_environment(arm,product=False):
    require(arm in ('off','on'),'explicit fixed diagnostic arm required')
    env=dict(os.environ)
    require('SPRIG_LIFECYCLE_TRACE' not in env and 'SPRIG_WRITABLE_DIAGNOSTICS' not in env,'inherited tracing forbidden; explicit arm only')
    if product and arm=='on':env['SPRIG_WRITABLE_DIAGNOSTICS']='1'
    return env


class DiagnosticSample(StressCargoSample):
    def prepare(self,args):
        require(args.diagnostic_arm in ('off','on') and args.production_sha==SOURCE_SHA and args.backend=='writable' and args.incremental==0,'fixed diagnostic source/backend/inc0 only')
        for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','DOCKER_TLS','SPRIG_LIFECYCLE_TRACE','SPRIG_WRITABLE_DIAGNOSTICS'):
            require(key not in os.environ,'unexpected inherited routing/diagnostic setting',variable=key)
        self.artifact_results=Path(args.artifact_results)
        require(self.artifact_results==Path.cwd()/'results' and self.artifact_results.resolve(strict=True)==self.artifact_results and self.artifact_results.is_dir(),'exact existing external results root required')
        self.arm=args.diagnostic_arm
        self.pressure_profile=SPEC['profile']
        self.pressure_source=(Path(__file__).parent/'stress_cargo_pressure_long.py').read_bytes()
        require(hashlib.sha256(self.pressure_source).hexdigest()==PRESSURE_SHA,'frozen long-pressure helper changed')
        self.report.update(schema=SCHEMA,diagnosticArm=self.arm,diagnosticEnvironment={'SPRIG_WRITABLE_DIAGNOSTICS':'1' if self.arm=='on' else None,'SPRIG_LIFECYCLE_TRACE':None},normalPressureScriptSha256=PRESSURE_SHA,diagnosticSource={'sha':SOURCE_SHA,'parent':PARENT_SHA,'algorithmBase':ALGORITHM_BASE})
        self.manifest=validate_manifest(json.loads(Path(args.manifest).read_text()))
        # Explicit separate entry: reuse all ordinary transport/fixture checks,
        # not the primary StressCargoSample.prepare trace-off acceptance path.
        CargoTransportSample.prepare(self,args)
        self.flush_command_logs()
        require(self.fixture==self.manifest['initial'],'fixture oracle differs from DAG manifest')
        require(hashlib.sha256((self.source/'Cargo.lock').read_bytes()).hexdigest()==self.manifest['lockfileSha256'],'lockfile identity mismatch')
        self.report['dagManifest']={k:v for k,v in self.manifest.items() if k!='initial'}
        self.report['binarySha256']=hashlib.sha256(self.binary.read_bytes()).hexdigest()

    def command(self,arguments,*,cwd=None,record_event=True):
        args=[str(value) for value in arguments];self.sequence+=1
        product=getattr(self,'binary',None) is not None and args[0]==str(self.binary)
        env=command_environment(getattr(self,'arm','off'),product)
        proc=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',check=False,env=env)
        self.pending_command_logs.append(dict(sequence=self.sequence,argv=args,stdout=proc.stdout,stderr=proc.stderr,returncode=proc.returncode))
        if product:self.report.setdefault('diagnosticCommandBindings',[]).append(dict(sequence=self.sequence,executable=args[0],arm=self.arm,environmentValue=env.get('SPRIG_WRITABLE_DIAGNOSTICS')))
        if record_event:
            self.flush_command_logs();self.event('command_finished',sequence=self.sequence,executable=args[0],operation=args[1] if len(args)>1 else None,returncode=proc.returncode,stdoutBytes=len(proc.stdout.encode()),stderrBytes=len(proc.stderr.encode()))
        require(proc.returncode==0,'command failed; no automatic retry',argv=args,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)
        return proc.stdout

    def normal_pressure(self,tree):
        host=host_domain();before=time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        raw=self.runtime(tree,'python3 -B -',input_data=CLOCK_CODE,purpose='diagnostic_clock_domain')
        after=time.clock_gettime_ns(time.CLOCK_MONOTONIC);container=json.loads(raw)
        proof=dict(schema='sprig-writable-clock-proof-v1',clock='CLOCK_MONOTONIC',hostBeforeNs=before,containerMonotonicNs=container['monotonicNs'],hostAfterNs=after,host=host,container=container['domain'])
        self.report['diagnosticClockProof']=proof
        validate_clock_proof(proof)
        command=self.report['commands'][-1]
        self.report['diagnosticClockBinding']={k:command[k] for k in ('containerId','workspaceGeneration','stdoutPath')}
        super().normal_pressure(tree)
        pressure_command=self.report['commands'][-1]
        require(all(pressure_command[k]==self.report['diagnosticClockBinding'][k] for k in ('containerId','workspaceGeneration')),'pressure clock probe/container generation mismatch')
        require(host_domain()==host,'host clock domain changed across pressure')

    def post_cleanup_observation(self):
        require(self.report.get('lifecycle',{}).get('cleanup',{}).get('complete') is True and self.report.get('remainingMounts')==[] and self.report.get('remainingContainers')==[],'post-cleanup observation needs confirmed normal cleanup')
        mount=self.root.parent
        self.command(['btrfs','filesystem','sync',mount],record_event=False)
        # Inspect allocation only AFTER the same measurement sync has realized
        # delayed allocation for completed buffered footer writes.
        logs=[]
        for path in sorted((self.library/'native').glob('*/writable-*.log')):
            st=path.lstat();require(path.is_file() and not path.is_symlink() and st.st_nlink==1,'unsafe writable source log')
            logs.append(dict(source=str(path),bytes=st.st_size,allocatedBytes=st.st_blocks*512,sha256=stream_digest(path)))
        usage=self.command(['btrfs','filesystem','usage','-b',mount],record_event=False)
        groups=self.command(['btrfs','filesystem','df','-b',mount],record_event=False)
        used=re.search(r'^\s*Used:\s*(\d+)\s*$',usage,re.M);device=re.search(r'^\s*Device size:\s*(\d+)\s*$',usage,re.M)
        require(used and device,'post-cleanup physical space is malformed');st=os.statvfs(mount)
        self.report['postNormalCleanupSpace']=dict(filesystemUsedBytes=int(used[1]),deviceBytes=int(device[1]),availableBytes=st.f_bavail*st.f_frsize,usageRaw=usage,groupsRaw=groups,sourceLogs=logs,sourceLogLogicalBytes=sum(r['bytes'] for r in logs),sourceLogAllocatedBytes=sum(r['allocatedBytes'] for r in logs),boundary='after all ordinary server/container exits and buffered dumps, before external archive copy and runtime leave/outer unmount; original active metric unchanged')
        self.flush_command_logs()

    def preserve_logs(self):
        self.flush_command_logs()
        CurrentSample.preserve_logs(self)  # bounded previews, never used for trace analysis
        if not self.root or not self.records:return
        archive=Path(str(self.records)+'.logs')
        files=sorted(set(self.logs.glob('*'))|set((self.library/'native').glob('*/writable-*.log')))
        planned=[]
        for index,source in enumerate(files):
            st=source.lstat();require(stat.S_ISREG(st.st_mode) and not source.is_symlink() and st.st_nlink==1,'unsafe full diagnostic log path')
            planned.append(dict(source=str(source),archived=str(archive/('%06d-'%index+source.name)),bytes=st.st_size,identity=dict(device=st.st_dev,inode=st.st_ino,mtimeNs=st.st_mtime_ns,ctimeNs=st.st_ctime_ns)))
        temporary=Path(os.environ['RUNNER_TEMP'])
        current=candidates(self.artifact_results,temporary)
        existing=sum(row['bytes'] for row in current);planned_bytes=sum(row['bytes'] for row in planned)
        admission=dict(schema='sprig-writable-diagnostic-archive-admission-v1',existingNamedExternalBytes=existing,plannedArchiveBytes=planned_bytes,reportReserveBytes=REPORT_RESERVE_BYTES,collectionReserveBytes=COLLECTION_RESERVE,projectedAdmissionBytes=existing+planned_bytes+REPORT_RESERVE_BYTES+COLLECTION_RESERVE,maximumBytes=ARTIFACT_BUDGET_BYTES,plannedFiles=planned,admitted=False)
        self.report['diagnosticArchiveAdmission']=admission
        require(admission['projectedAdmissionBytes']<=ARTIFACT_BUDGET_BYTES,'full archive plus existing evidence/report reserve exceeds1GiB; keep source image/logs, no subset copied')
        require(not archive.exists() and not archive.is_symlink(),'refuse existing archive directory')
        planned_report={**self.report,'completeLogArchive':[{k:r[k] for k in ('source','archived','bytes')}|{'sha256':'0'*64} for r in planned]}
        require(len(json.dumps(planned_report,sort_keys=True).encode())<=RAW_REPORT_MAX_BYTES-1024**2,'planned standalone report exceeds128MiB transport reserve; retain source image')
        admission['admitted']=True;archive.mkdir();rows=[]
        self.report['diagnosticArchiveCopy']=dict(complete=False,completedFiles=0,sourceFilesRetained=True)
        try:
            for row in planned:
                source=Path(row['source']);target=Path(row['archived']);h=hashlib.sha256();size=0
                fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as inp,target.open('xb') as out:
                    st=os.fstat(inp.fileno())
                    def unchanged(st):
                        return stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==row['bytes'] and dict(device=st.st_dev,inode=st.st_ino,mtimeNs=st.st_mtime_ns,ctimeNs=st.st_ctime_ns)==row['identity']
                    require(unchanged(st),'source changed after archive admission')
                    try:
                        while size<row['bytes']:
                            chunk=inp.read(min(1024*1024,row['bytes']-size));require(chunk,'source shrank during copy')
                            out.write(chunk);h.update(chunk);size+=len(chunk)
                        require(not inp.read(1) and unchanged(os.fstat(inp.fileno())) and unchanged(source.lstat()),'source grew/changed during bounded archive copy')
                    except BaseException:
                        self.report['partialLogArchive']=[*rows,dict(source=str(source),archived=str(target),bytes=size,sha256=h.hexdigest(),partial=True)]
                        raise
                rows.append(dict(source=str(source),archived=str(target),bytes=size,sha256=h.hexdigest()))
                self.report['diagnosticArchiveCopy']['completedFiles']=len(rows)
            self.report['completeLogArchive']=rows
            self.report['diagnosticArchiveCopy']['complete']=True
        except BaseException as error:
            self.report.setdefault('partialLogArchive',rows)
            self.report['diagnosticArchiveCopy']['error']=str(error)
            if 'row' in locals():self.report['diagnosticArchiveCopy']['failedFile']=dict(source=row['source'],archived=row['archived'],bytesWritten=size,targetExists=target.exists(),sourceRetained=source.exists())
            raise


def main():
    report=stress_report();sample=DiagnosticSample(report);started=time.perf_counter()
    try:
        parser=Parser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True,parser_class=Parser);run=sub.add_parser('run')
        for name in ('root','source','oracle','binary','image','manifest','records','production-sha','artifact-results'):run.add_argument('--'+name,required=True)
        run.add_argument('--backend',choices=['writable'],required=True);run.add_argument('--incremental',type=int,choices=[0],required=True);run.add_argument('--diagnostic-arm',choices=['off','on'],required=True)
        args=parser.parse_args();sample.timed('preflight',lambda:sample.prepare(args));sample.execute()
    except BaseException as error:
        report['ok']=False;report['error']=dict(type=type(error).__name__,message=str(error),details=getattr(error,'details',{}),traceback=traceback.format_exc())
    finally:
        try:
            sample.cleanup()
            if sample.root and report.get('lifecycle',{}).get('cleanup',{}).get('complete') is True:sample.post_cleanup_observation()
        except BaseException as error:
            report['ok']=False;report.setdefault('cleanupErrors',[]).append(dict(message=str(error)))
        # Preserve COMPLETE logs even if a size/coverage/CPU gate will fail in
        # the separate auditor. Never trim or substitute runtimeLogs previews.
        try:sample.preserve_logs()
        except BaseException as error:report['ok']=False;report.setdefault('cleanupErrors',[]).append(dict(message=str(error)))
        report['full_task_seconds']=time.perf_counter()-started
    if sample.root:
        try:(sample.root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        except BaseException as error:report['ok']=False;report['reportWriteError']=str(error)
    raw=json.dumps(report,sort_keys=True)
    if len(raw.encode())+1>RAW_REPORT_MAX_BYTES:
        # The complete report remains on its original image; do not present a
        # selected subset as successful or start another sample.
        print(json.dumps(dict(schema=SCHEMA,ok=False,diagnosticArm=report.get('diagnosticArm'),error={'message':'standalone report exceeds128MiB reserved transport'},completeReportRetainedOnImage=str(sample.root/'report.json') if sample.root else None,completeLogArchiveClaimed=False)))
        return 1
    print(raw);return 0 if report.get('ok') else 1

if __name__=='__main__':sys.exit(main())
