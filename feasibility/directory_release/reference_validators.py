#!/usr/bin/env python3
"""Root-owned paired core-attribute/lifecycle comparison. Preparation never executes it."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time

BASE = Path('/tmp/sprig-directory-counts-benchmark')
WORKSPACE = Path('/workspace/scratch/5016a09b9681')
TESTS = {
    'attr': 'writable::directory_benchmark::ordinary_directory_attribute_pressure',
    'lifecycle': 'writable::directory_lifecycle_benchmark::ordinary_directory_lifecycle_pressure',
}
FLOOR = 1536 * 1024**2
OUTPUT_LIMIT = 64 * 1024**2
PER_PROCESS_SECONDS = 120
TOTAL_SECONDS = 30 * 60
PROFILES = [
    ('nested-empty',0,0,'nested',64,1),
    ('nested-2048',2048,0,'nested',64,1),
    ('nested-16384',16384,0,'nested',64,1),
    ('flat-root',2048,0,'flat-root',64,1),
    ('aliases-root',2048,0,'hardlinks-root',64,1),
    ('aliases-nested',2048,0,'hardlinks-nested',64,1),
    ('retired-heavy',128,2048,'nested',64,1),
    ('true-tiny',0,0,'nested',0,1),
    ('below-guard-255',250,0,'nested',0,1),
    ('at-guard-256',251,0,'nested',0,1),
    ('above-guard-257',252,0,'nested',0,1),
    ('budget4-at',248,0,'nested',0,4),
    ('budget4-over',247,0,'nested',0,5),
    ('budget8-at',500,0,'nested',0,8),
    ('budget8-over',499,0,'nested',0,9),
    ('cap64-at',4028,0,'nested',0,64),
    ('cap64-over',4027,0,'nested',0,65),
    ('aliases-above-guard',2048,128,'hardlinks-nested',64,1),
]
LIFECYCLE_PROFILES = [
    ('tiny',0,0,0),
    ('file-heavy',2048,0,0),
    ('directory-heavy',0,512,0),
    ('retired-history',128,0,128),
]
MUTATION_CASES = [
    'directory-create', 'directory-remove', 'directory-rename-same-parent',
    'directory-rename-cross-parent', 'directory-overwrite', 'directory-subtree-rename',
    'file-create', 'file-hardlink',
]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def valid_hash(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def exact_integer(value, expected):
    return type(value) is int and value == expected


def validate_memory(value, lifecycle=False):
    if not isinstance(value,dict) or value.get('source') != '/proc/self/status':
        raise ValueError('actual Linux process RSS/HWM readout unavailable')
    keys = ['vmRssKiB','vmHwmKiB'] if lifecycle else ['rssBytes','highWaterBytes']
    if lifecycle and value.get('available') is not True:
        raise ValueError('incomplete lifecycle process memory readout')
    if any(type(value.get(k)) is not int or value[k] <= 0 for k in keys):
        raise ValueError('invalid process memory readout')
    if value[keys[1]] < value[keys[0]]:
        raise ValueError('process high-water memory less than current RSS')


def validate_layout(report):
    size, alignment = report.get('nodeSizeBytes'), report.get('nodeAlignmentBytes')
    if type(size) is not int or not 0 < size <= 4096 or type(alignment) is not int or alignment <= 0 or alignment & (alignment - 1) or size % alignment:
        raise ValueError('invalid actual Node layout')


def validate_durations(row, calls, batches):
    values=row.get('batchesNanoseconds')
    if not exact_integer(row.get('callsPerBatch'),calls):
        raise ValueError('case API call count mismatch')
    if not isinstance(values,list) or len(values)!=batches or any(type(v) is not int or not 0<v<2**53 for v in values):
        raise ValueError('invalid exact raw batch durations')


def validate_attr_report(report, profile):
    _, unrelated, retired, layout, wide, hot = profile
    if report.get('schema') != 'sprig-directory-attr-core-v3' or report.get('oraclePassed') is not True or report.get('oracleBeforeTiming') is not True:
        raise ValueError('benchmark report schema/oracle mismatch')
    unique_nodes = 4 + hot + 2*wide + (min(unrelated,1) if layout.startswith('hardlinks-') else unrelated) + retired
    exact = {'unrelatedFiles':unrelated,'retiredDirectories':retired,'wideSubdirectories':wide,'hotSubtreeEntries':hot,'uniqueNodes':unique_nodes,'liveNodes':unique_nodes-retired}
    if report.get('layout') != layout or any(type(report.get(k)) is not int or report[k] != v for k,v in exact.items()):
        raise ValueError('benchmark profile/unique-node count mismatch')
    cases = report.get('cases')
    expected = {'root':5,'hot':3 if hot else 2,'wide':2+wide,'flat':2}
    if not isinstance(cases,list) or len(cases) != 4 or {r.get('case') for r in cases} != set(expected):
        raise ValueError('case identity/count mismatch')
    for row in cases:
        validate_durations(row,100,32)
        if not exact_integer(row.get('expectedNlink'),expected[row['case']]):
            raise ValueError('case batch/nlink mismatch')
    validate_layout(report)
    if not exact_integer(report.get('nodeValueBytes'),unique_nodes*report['nodeSizeBytes']):
        raise ValueError('inline Node value accounting mismatch')
    memory=report.get('memory')
    if not isinstance(memory,dict) or set(memory) != {'initial','initialized','ready','afterTimedCalls'}:
        raise ValueError('missing attribute memory checkpoints')
    for value in memory.values(): validate_memory(value)
    if not valid_hash(report.get('fixtureHash')):
        raise ValueError('invalid fixture identity')


def validate_state(state, size):
    if not isinstance(state,dict): raise ValueError('missing lifecycle state')
    for key in ['uniqueNodes','namespacePaths','liveDirectoryNodes','retiredDirectoryNodes','journalFrames','journalBytes','inlineNodePayloadBytes']:
        if type(state.get(key)) is not int or state[key]<0: raise ValueError('invalid lifecycle state count')
    if state['uniqueNodes'] < state['liveDirectoryNodes'] + state['retiredDirectoryNodes'] or not 0 < state['journalBytes'] <= 1024**2:
        raise ValueError('lifecycle node/journal bounds mismatch')
    if state['inlineNodePayloadBytes'] != state['uniqueNodes']*size or not valid_hash(state.get('topologyFingerprint')):
        raise ValueError('lifecycle layout/topology identity mismatch')


def validate_lifecycle_report(report, profile):
    name,files,dirs,retired=profile
    exact={'baseEntries':4+files+dirs,'paddingFiles':files,'paddingDirectories':dirs,'setupRetiredDirectories':retired,
           'successfulGenerationsRetained':0,'maximumFixtureJournalBytes':1024**2,'maximumReportBytes':1024**2}
    if report.get('schema')!='sprig-directory-lifecycle-core-v1' or report.get('profile')!=name or report.get('oraclePassed') is not True:
        raise ValueError('lifecycle report identity/oracle mismatch')
    if any(not exact_integer(report.get(k),v) for k,v in exact.items()) or not valid_hash(report.get('fixtureHash')):
        raise ValueError('lifecycle fixture/bounds mismatch')
    validate_layout(report)
    for key in ['memoryBeforeCases','memoryAfterCases']: validate_memory(report.get(key),True)
    cases=report.get('cases')
    expected=['create-initialization','replay-history']+MUTATION_CASES
    if not isinstance(cases,list) or [row.get('case') for row in cases]!=expected:
        raise ValueError('lifecycle case order/identity mismatch')
    for row in cases:
        case=row['case']
        if row.get('ownedGenerationsRemovedAfterVerification') is not True: raise ValueError('lifecycle cleanup not verified')
        if case in ['create-initialization','replay-history']:
            validate_durations(row,1,8)
            if not exact_integer(row.get('samples'),8) or row.get('oraclePassedBeforeTiming') is not True or row.get('oraclePassedAfterEverySample') is not True:
                raise ValueError('lifecycle initialization/replay oracle mismatch')
            validate_memory(row.get('memoryBeforeSamples'),True)
            samples=row.get('memoryAfterSamples')
            if not isinstance(samples,list) or len(samples)!=8: raise ValueError('missing lifecycle sample memory')
            for value in samples: validate_memory(value,True)
            if case=='create-initialization':
                states=row.get('stateAfterSamples')
                if not isinstance(states,list) or len(states)!=8: raise ValueError('missing create sample states')
                for state in states:
                    validate_state(state,report['nodeSizeBytes'])
                    if state['uniqueNodes']!=4+files+dirs or state['namespacePaths']!=4+files+dirs or state['journalFrames']!=1 or state['liveDirectoryNodes']!=4+dirs or state['retiredDirectoryNodes']!=0:
                        raise ValueError('create sample state mismatch')
            else:
                if not exact_integer(row.get('setupRetiredDirectories'),retired) or not exact_integer(row.get('setupSubtreeRounds'),32) or not exact_integer(row.get('setupMutationCalls'),2*retired+160):
                    raise ValueError('replay setup mutation count mismatch')
                state=row.get('initialState');validate_state(state,report['nodeSizeBytes'])
                if state['uniqueNodes']!=4+files+dirs+retired+64 or state['namespacePaths']!=4+files+dirs or state['liveDirectoryNodes']!=4+dirs or state['retiredDirectoryNodes']!=retired+64 or state['journalFrames']!=1+2*retired+160:
                    raise ValueError('replay history state mismatch')
        else:
            validate_durations(row,8,12)
            if not exact_integer(row.get('batches'),12) or not exact_integer(row.get('totalTimedApiCalls'),96) or row.get('oraclePassedBeforeEveryBatch') is not True or row.get('oraclePassedAfterEveryBatch') is not True or row.get('replayVerifiedAfterTiming') is not True:
                raise ValueError('mutation batch oracle/replay mismatch')
            setup_extra={'directory-create':0,'directory-remove':96,'directory-rename-same-parent':96,'directory-rename-cross-parent':96,'directory-overwrite':192,'directory-subtree-rename':384,'file-create':0,'file-hardlink':2}[case]
            if not exact_integer(row.get('setupMutationCalls'),2*retired+setup_extra) or not exact_integer(row.get('subtreeEntriesMovedPerCall'),4 if case=='directory-subtree-rename' else 1):
                raise ValueError('mutation setup/scope mismatch')
            for key in ['initialState','finalState']: validate_state(row.get(key),report['nodeSizeBytes'])
            initial,final=row['initialState'],row['finalState']
            common=(4+files+dirs+retired,4+files+dirs,4+dirs,retired,1+2*retired)
            initial_delta={'directory-create':(0,0,0,0,0),'directory-remove':(96,96,96,0,96),
                'directory-rename-same-parent':(96,96,96,0,96),'directory-rename-cross-parent':(96,96,96,0,96),
                'directory-overwrite':(192,192,192,0,192),'directory-subtree-rename':(384,384,288,0,384),
                'file-create':(0,0,0,0,0),'file-hardlink':(1,2,0,0,2)}[case]
            final_delta={'directory-create':(96,96,96,0,96),'directory-remove':(96,0,0,96,192),
                'directory-rename-same-parent':(96,96,96,0,192),'directory-rename-cross-parent':(96,96,96,0,192),
                'directory-overwrite':(192,96,96,96,288),'directory-subtree-rename':(384,384,288,0,480),
                'file-create':(96,96,0,0,96),'file-hardlink':(1,98,0,0,98)}[case]
            keys=['uniqueNodes','namespacePaths','liveDirectoryNodes','retiredDirectoryNodes','journalFrames']
            for state,delta in [(initial,initial_delta),(final,final_delta)]:
                if [state[k] for k in keys]!=[a+b for a,b in zip(common,delta)]:
                    raise ValueError('mutation exact state/frame count mismatch')
            validate_memory(row.get('memoryBeforeBatches'),True)
            samples=row.get('memoryAfterBatches')
            if not isinstance(samples,list) or len(samples)!=12: raise ValueError('missing mutation memory checkpoints')
            for value in samples: validate_memory(value,True)


def comparable_topology(report, suite):
    if suite=='attr':
        return {key:report[key] for key in ['fixtureHash','uniqueNodes','liveNodes']}
    rows=[]
    for case in report['cases']:
        states=case.get('stateAfterSamples',[]) or [case[key] for key in ['initialState','finalState'] if key in case]
        rows.append((case['case'],[{key:value for key,value in state.items() if key not in ['inlineNodePayloadBytes','journalBytes']} for state in states]))
    return {'fixtureHash':report['fixtureHash'],'states':rows}


def memory_cases(report, suite):
    if suite=='attr':
        return {key:{'rssBytes':value['rssBytes'],'highWaterBytes':value['highWaterBytes']}
                for key,value in report['memory'].items()}
    values={}
    for row in report['cases']:
        samples=row.get('memoryAfterSamples',row.get('memoryAfterBatches'))
        before=row.get('memoryBeforeSamples',row.get('memoryBeforeBatches'))
        values[row['case']]={'rssBytes':statistics.median(sample['vmRssKiB']*1024 for sample in samples),
                            'highWaterBytes':max(sample['vmHwmKiB']*1024 for sample in samples),
                            'beforeRssBytes':before['vmRssKiB']*1024}
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',required=True)
    parser.add_argument('--mode',choices=['canary','full'],required=True)
    parser.add_argument('--suite',choices=['attr','lifecycle','all'],required=True)
    parser.add_argument('--baseline-build-summary',type=Path,required=True)
    parser.add_argument('--candidate-build-summary',type=Path,required=True)
    parser.add_argument('--baseline-binary-sha256',required=True)
    parser.add_argument('--candidate-binary-sha256',required=True)
    args=parser.parse_args()
    manifest_path=BASE/'manifest-v2.json'
    manifest=json.loads(manifest_path.read_text())
    for filename,expected in manifest['runnerSha256'].items():
        if digest(BASE/filename)!=expected: raise SystemExit(f'reviewed runner changed: {filename}')
    expected_heads={variant:data['benchmarkCommit'] for variant,data in manifest['variants'].items()}
    expected_binary={'baseline':args.baseline_binary_sha256,'candidate':args.candidate_binary_sha256}
    if set(expected_heads)!={'baseline','candidate'} or any(not valid_hash(value) for value in expected_binary.values()):
        raise SystemExit('exact baseline/candidate manifest and frozen binary hashes required')
    spec=importlib.util.spec_from_file_location('owned_guard',BASE/'run_root_build_v2.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    binaries={};builds={}
    for variant, summary_path in [('baseline',args.baseline_build_summary),('candidate',args.candidate_build_summary)]:
        data=json.loads(summary_path.read_text()); copied=data.get('binary_copy') or {}
        if data.get('schema')!='sprig-directory-counts-build-v2' or data.get('success') is not True or data.get('source_commit') != expected_heads[variant] or copied.get('source_commit') != expected_heads[variant] or data.get('manifest_sha256')!=digest(manifest_path):
            raise SystemExit(f'{variant} build did not succeed at exact expected head')
        proof=data.get('artifact_verification') or {}
        inventory=data.get('embedded_test_inventory') or {}
        if proof.get('passed') is not True or proof.get('compiler_artifact',{}).get('fresh') is not False:
            raise SystemExit(f'{variant} lacks forced fresh root compilation provenance')
        if inventory.get('passed') is not True or inventory.get('actual_names')!=manifest['variants'][variant]['expectedTests']:
            raise SystemExit(f'{variant} lacks exact embedded test inventory')
        if any(data.get('source_sha256',{}).get(path)!=expected for path,expected in manifest['instrumentationSha256'].items()):
            raise SystemExit(f'{variant} benchmark harness mismatch')
        path=Path(copied.get('copy',''))
        if not path.is_file() or path.resolve()!=path or not path.is_relative_to(BASE/'root-validation'):
            raise SystemExit(f'{variant} binary is not an owned immutable copy')
        if copied.get('sha256') != expected_binary[variant] or digest(path) != expected_binary[variant]:
            raise SystemExit(f'{variant} binary SHA not frozen/verified')
        binaries[variant]=path;builds[variant]={'summary':str(summary_path),'summarySha256':digest(summary_path),'head':expected_heads[variant],'productionCommit':manifest['variants'][variant]['productionCommit'],'binary':str(path),'binarySha256':expected_binary[variant]}
    if expected_binary['baseline']==expected_binary['candidate'] or binaries['baseline']==binaries['candidate']:
        raise SystemExit('baseline and candidate must be distinct verified ELF identities')
    if shutil.disk_usage(WORKSPACE).free < FLOOR + OUTPUT_LIMIT:
        raise SystemExit('preflight disk requires 1.5 GiB floor plus full 64 MiB output reserve')
    root=BASE/'paired-runs'/f'v3-{args.suite}-{args.mode}-{time.time_ns()}-{os.getpid()}'
    root.mkdir(parents=True,exist_ok=False)
    profiles=[]
    if args.suite in ['attr','all']:
        profiles += [('attr',profile) for profile in ([PROFILES[1],PROFILES[7],PROFILES[12]] if args.mode=='canary' else PROFILES)]
    if args.suite in ['lifecycle','all']:
        profiles += [('lifecycle',profile) for profile in ([LIFECYCLE_PROFILES[0],LIFECYCLE_PROFILES[3]] if args.mode=='canary' else LIFECYCLE_PROFILES)]
    pairs=1 if args.mode=='canary' else 4
    started=time.monotonic(); deadline=started+TOTAL_SECONDS
    result={'schema':'sprig-directory-counts-pairs-v3','suite':args.suite,'mode':args.mode,'complete':False,'ok':False,
            'manifestSha256':digest(manifest_path),'runnerSha256':digest(Path(__file__)),'guardSha256':digest(BASE/'run_root_build_v2.py'),'builds':builds,'limits':{'minimumFreeBytes':FLOOR,'maximumOutputAllocatedBytes':OUTPUT_LIMIT,'perProcessSeconds':PER_PROCESS_SECONDS,'totalSeconds':TOTAL_SECONDS},
            'profiles':profiles,'pairsPerProfile':pairs,'records':[],'error':None,
            'interpretationDeclaredBeforeRun':'Report absolute ns/call and all four pair ratios; tiny-control percentages can magnify a few ns. Do not drop negative controls or tune thresholds from one profile. This debug-core run alone cannot authorize promotion; correctness, quiet repeatability and actual mounted release pressure remain required.',
            'caveat':'Unmounted warm core attribute/lifecycle batches, not independent within-process trials, mounted throughput or task p99. Startup includes create durability barriers; buffered mutations exclude sync. Canary validates protocol only. RSS is process-wide and allocator-influenced; actual Node inline layout is reported separately.'}
    def save():
        result['elapsedSeconds']=time.monotonic()-started
        pending=root/'summary.pending.json';pending.write_text(json.dumps(result,indent=2)+'\n');pending.replace(root/'summary.json')
    save()
    computations_complete = False
    try:
        node_layout={}
        for suite,profile in profiles:
            name=profile[0]
            fixture=None
            topology=None
            for pair in range(pairs):
                order=['baseline','candidate'] if pair%2==0 else ['candidate','baseline']
                for position,variant in enumerate(order):
                    if time.monotonic()>=deadline or shutil.disk_usage(WORKSPACE).free<FLOOR or guard.allocated(root)>OUTPUT_LIMIT:
                        raise RuntimeError('resource budget exhausted before next ordinary process')
                    folder=root/f'{suite}-{name}-pair{pair}-{position}-{variant}';folder.mkdir()
                    fixture_path=folder/'fixture'
                    command=[str(binaries[variant]),TESTS[suite],'--ignored','--exact','--test-threads=1','--nocapture']
                    env=os.environ.copy()
                    for key in list(env):
                        if key.startswith('SPRIG_DIRECTORY_'): env.pop(key)
                    env['SPRIG_DIRECTORY_OUTPUT']=str(fixture_path)
                    if suite=='attr':
                        _,unrelated,retired,layout,wide,hot=profile
                        env.update(SPRIG_DIRECTORY_UNRELATED=str(unrelated),SPRIG_DIRECTORY_RETIRED=str(retired),SPRIG_DIRECTORY_LAYOUT=layout,SPRIG_DIRECTORY_WIDE=str(wide),SPRIG_DIRECTORY_HOT_ENTRIES=str(hot))
                    else: env['SPRIG_DIRECTORY_LIFECYCLE_PROFILE']=name
                    env.pop('SPRIG_WRITABLE_DIAGNOSTICS',None)
                    record={'suite':suite,'profile':name,'pair':pair,'order':order,'position':position,'variant':variant,'command':command,'folder':str(folder)}
                    result['records'].append(record);save()
                    log_path=folder/'process.log';sample_started=time.monotonic();reason=None;settled=False
                    with log_path.open('xb') as log:
                        process=subprocess.Popen(command,cwd=WORKSPACE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                        try:
                            while process.poll() is None:
                                elapsed=time.monotonic()-sample_started
                                if elapsed>PER_PROCESS_SECONDS:reason='per-process wall bound exceeded'
                                elif time.monotonic()>deadline:reason='whole comparison wall bound exceeded'
                                elif shutil.disk_usage(WORKSPACE).free<FLOOR:reason='available disk below 1.5 GiB floor'
                                elif guard.allocated(root)>OUTPUT_LIMIT:reason='owned output allocation exceeded 64 MiB'
                                if reason:break
                                time.sleep(.25)
                        except BaseException as error:
                            reason=f'runner interrupted: {type(error).__name__}: {error}'
                        finally:
                            if process.poll() is not None and guard.group_exists(process.pid) and reason is None:
                                reason='process returned with live owned descendants'
                            try:
                                settled=guard.settle_owned_group(process)
                            except BaseException as error:
                                detail=f'owned process-group settlement uncertain: {type(error).__name__}: {error}'
                                reason=f'{reason}; {detail}' if reason else detail
                                settled=False
                    record.update(returncode=process.returncode,wallSeconds=time.monotonic()-sample_started,guardReason=reason,ownedProcessGroupSettled=settled,logSha256=digest(log_path))
                    if process.returncode!=0 or reason or not settled:raise RuntimeError(f'{name}/{variant} incomplete: {reason or process.returncode}')
                    if record['wallSeconds']>PER_PROCESS_SECONDS or time.monotonic()>deadline or shutil.disk_usage(WORKSPACE).free<FLOOR or guard.allocated(root)>OUTPUT_LIMIT:
                        raise RuntimeError('resource bound exceeded on final process observation')
                    report_path=fixture_path/'report.json'
                    if report_path.stat().st_size>1024**2: raise RuntimeError('per-process report exceeds 1 MiB')
                    report=json.loads(report_path.read_text())
                    (validate_attr_report if suite=='attr' else validate_lifecycle_report)(report,profile)
                    if suite=='lifecycle' and {path.name for path in fixture_path.iterdir()}!={'objects','report.json'}:
                        raise RuntimeError('successful lifecycle fixture retained unexpected generations/files')
                    if fixture is None:fixture=report['fixtureHash']
                    if report['fixtureHash']!=fixture:raise RuntimeError('paired fixtures differ')
                    observed_topology=comparable_topology(report,suite)
                    if topology is None: topology=observed_topology
                    if topology!=observed_topology: raise RuntimeError('paired lifecycle topology/count state differs')
                    observed_layout=(report['nodeSizeBytes'],report['nodeAlignmentBytes'])
                    if variant in node_layout and node_layout[variant]!=observed_layout: raise RuntimeError('Node layout changed within a frozen binary')
                    node_layout[variant]=observed_layout
                    record.update(report=report,reportSha256=digest(report_path),ok=True);save()
        result['protectedBinariesUnchanged']=all(digest(path)==expected_binary[var] for var,path in binaries.items())
        if not result['protectedBinariesUnchanged']:raise RuntimeError('frozen executable changed during comparison')
        if args.mode=='full':
            comparisons=[]
            for suite,profile in profiles:
                for case in (['root','hot','wide','flat'] if suite=='attr' else ['create-initialization','replay-history']+MUTATION_CASES):
                    values={variant:[] for variant in binaries}
                    for variant in binaries:
                        rows=[r for r in result['records'] if r['suite']==suite and r['profile']==profile[0] and r['variant']==variant]
                        for row in sorted(rows,key=lambda r:r['pair']):
                            raw=next(c for c in row['report']['cases'] if c['case']==case)
                            values[variant].append(statistics.median(raw['batchesNanoseconds'])/raw['callsPerBatch'])
                    ratios=[c/b for b,c in zip(values['baseline'],values['candidate'])]
                    base_mean=math.exp(statistics.mean(map(math.log,values['baseline'])))
                    candidate_mean=math.exp(statistics.mean(map(math.log,values['candidate'])))
                    comparisons.append({'suite':suite,'profile':profile[0],'case':case,'perProcessMedianBatchNsPerCall':values,'pairedRatios':ratios,'geometricMeanPairedRatio':math.exp(statistics.mean(map(math.log,ratios))),'baselineGeomeanNsPerCall':base_mean,'candidateGeomeanNsPerCall':candidate_mean,'deltaNsPerCall':candidate_mean-base_mean,'allFourSlower':all(ratio>1 for ratio in ratios)})
            result['comparisons']=comparisons
        result['nodeLayoutByVariant']={variant:{'sizeBytes':layout[0],'alignmentBytes':layout[1]} for variant,layout in node_layout.items()}
        memory_comparisons=[]
        for suite,profile in profiles:
            rows=[record for record in result['records'] if record['suite']==suite and record['profile']==profile[0]]
            case_names=list(memory_cases(rows[0]['report'],suite))
            for case in case_names:
                values={variant:[memory_cases(record['report'],suite)[case] for record in sorted(rows,key=lambda record:record['pair']) if record['variant']==variant] for variant in binaries}
                deltas=[candidate['rssBytes']-baseline['rssBytes'] for baseline,candidate in zip(values['baseline'],values['candidate'])]
                memory_comparisons.append({'suite':suite,'profile':profile[0],'case':case,'perProcessMemory':values,'pairedRssDeltaBytes':deltas})
        result['memoryComparisons']=memory_comparisons
        result['memoryInterpretation']='RSS/HWM are raw process/allocator observations outside timers, not isolated index allocations. Report paired deltas alongside actual Node size and complete mutation/startup/replay controls; never infer heap cost solely from size_of or percent RSS changes.'
        computations_complete = True
    except BaseException as error:
        result['complete']=False;result['ok']=False
        result['error']=f'{type(error).__name__}: {error}'
    finally:
        # Persist a non-passing report first, then include that report in the
        # final bounds observation. Never advertise success before comparisons.
        result['complete']=False;result['ok']=False
        result['outputAllocatedBytes']=guard.allocated(root)
        result['finalFreeBytes']=shutil.disk_usage(WORKSPACE).free
        save()
        def final_bound_error():
            if guard.allocated(root)>OUTPUT_LIMIT:return 'report-inclusive output allocation exceeded 64 MiB'
            if shutil.disk_usage(WORKSPACE).free<FLOOR:return 'final available disk below 1.5 GiB floor'
            if time.monotonic()>deadline:return 'final whole comparison wall bound exceeded'
            return None
        violation=final_bound_error()
        if computations_complete and violation is None:
            result['complete']=True;result['ok']=True
        elif violation:
            result['error']=f"{result['error']}; {violation}" if result['error'] else violation
        result['outputAllocatedBytes']=guard.allocated(root)
        result['finalFreeBytes']=shutil.disk_usage(WORKSPACE).free
        save()
        # A passing report can itself allocate another block or cross the
        # deadline. Observe again after its final write and fail closed.
        violation=final_bound_error()
        if violation:
            result['complete']=False;result['ok']=False
            result['error']=f"{result['error']}; {violation}" if result['error'] else violation
            result['outputAllocatedBytes']=guard.allocated(root)
            result['finalFreeBytes']=shutil.disk_usage(WORKSPACE).free
            save()
    print(json.dumps({'ok':result['ok'],'complete':result['complete'],'summary':str(root/'summary.json'),'records':len(result['records']),'error':result['error']}))
    raise SystemExit(0 if result['ok'] else 1)

if __name__=='__main__':main()
