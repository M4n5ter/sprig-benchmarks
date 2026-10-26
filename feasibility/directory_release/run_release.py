#!/usr/bin/env python3
"""Frozen, serial release-core protocol. Remote/root execution only; never auto-dispatches."""
import argparse
import fcntl
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import statistics
import subprocess
import time
import shutil

SCHEMA = 'sprig-directory-counts-release-manifest-v1'
VARIANTS = ['baseline', 'count', 'narrow']
TESTS = {
    'attr': 'writable::directory_benchmark::ordinary_directory_attribute_pressure',
    'lifecycle': 'writable::directory_lifecycle_benchmark::ordinary_directory_lifecycle_pressure',
}
_ACCOUNTING = None


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def valid_hash(value, length=64):
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def child(path, root):
    path, root = Path(path), Path(root)
    if not path.is_absolute() or path.resolve() != path or not path.is_relative_to(root.resolve()) or path == root:
        raise ValueError(f'not an exact owned descendant path: {path}')
    return path


def validate_manifest(m):
    if m.get('schema') != SCHEMA or m.get('approvedForExecution') is not True:
        raise ValueError('manifest is not a root-approved frozen release protocol')
    if m.get('variantOrder') != VARIANTS or set(m.get('variants', {})) != set(VARIANTS):
        raise ValueError('all three exact variants are required')
    pins = []
    for variant in VARIANTS:
        row = m['variants'][variant]
        tests = row.get('expectedTests')
        if not valid_hash(row.get('productionCommit'), 40) or not isinstance(tests, list) or not tests or tests != sorted(set(tests)) or not set(TESTS.values()).issubset(tests):
            raise ValueError(f'{variant}: immutable source pin and complete test inventory required')
        pins.append(row['productionCommit'])
    if len(set(pins)) != 3:
        raise ValueError('production pins must be distinct')
    if not isinstance(m.get('toolchain', {}).get('requested'), str) or not re.fullmatch(r'\d+\.\d+\.\d+',m['toolchain']['requested']) or m['toolchain'].get('requireSameExactCompiler') is not True:
        raise ValueError('exact toolchain version must be frozen, not a floating channel')
    orders = m.get('fullOrders')
    if not isinstance(orders, list) or len(orders) != 6 or {tuple(row) for row in orders} != set(itertools.permutations(VARIANTS)):
        raise ValueError('six complete permutation blocks required')
    if m.get('expectedProcessCounts') != {'canary': 15, 'full': 396, 'total': 411}:
        raise ValueError('fixed process counts required')
    limits = m.get('limits', {})
    required = {'jobSeconds':2700, 'admissionSeconds':2400, 'processSeconds':120,
                'cleanupReserveSeconds':10, 'finalizeReserveSeconds':60,
                'minimumFreeBytes':1610612736, 'maximumEvidenceBytes':1073741824,
                'evidenceFinalizeReserveBytes':8388608, 'maximumReportBytes':1048576,
                'cargoBuildJobs':2}
    if limits != required:
        raise ValueError('resource limits differ from reviewed bounded envelope')
    if len(m.get('profiles', {}).get('attr', [])) != 18 or len(m.get('profiles', {}).get('lifecycle', [])) != 4:
        raise ValueError('complete 18 attribute / 4 lifecycle controls required')
    for suite, profiles in m['profiles'].items():
        names = [p[0] for p in profiles]
        if len(names) != len(set(names)) or any(not isinstance(n, str) or not n or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in n) for n in names):
            raise ValueError('profile names must be unique safe identifiers')
        if not set(m['canary'].get(suite, [])).issubset(names):
            raise ValueError('canary profile missing from full controls')
    if m['canary'].get('orders') != [VARIANTS] or len(m['canary']['attr']) != 3 or len(m['canary']['lifecycle']) != 2:
        raise ValueError('canary must be the frozen 15-process protocol check')
    return m


def load_validator(manifest, directory):
    path = directory / 'reference_validators.py'
    if digest(path) != manifest['validatorSha256']:
        raise ValueError('frozen reference validators changed')
    spec = importlib.util.spec_from_file_location('sprig_release_reference_validators', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if manifest['profiles']['attr'] != [list(p) for p in module.PROFILES] or manifest['profiles']['lifecycle'] != [list(p) for p in module.LIFECYCLE_PROFILES]:
        raise ValueError('controls differ from the identical validated instrumentation')
    return module


def validate_clock(clock, now, boot_id):
    start = clock.get('startedMonotonic')
    if type(start) not in (int, float) or not math.isfinite(start) or start < 0 or start > now or clock.get('bootId') != boot_id:
        raise ValueError('invalid setup-inclusive same-host monotonic clock')
    return start + 2400


def accounting_helper():
    global _ACCOUNTING
    if _ACCOUNTING is None:
        spec=importlib.util.spec_from_file_location('sprig_release_publication',Path(__file__).with_name('build_release.py'))
        _ACCOUNTING=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ACCOUNTING)
    return _ACCOUNTING


def allocated(root):
    # Progress/final scans run outside a child and are always strict. Reuse the
    # same lstat/type/error audit as the builder; never suppress walk errors.
    return accounting_helper().evidence_size(root)


def make_schedule(manifest):
    records = []
    for phase in ['canary', 'full']:
        for suite in ['attr', 'lifecycle']:
            for profile in manifest['profiles'][suite]:
                if phase == 'canary' and profile[0] not in manifest['canary'][suite]:
                    continue
                orders = manifest['canary']['orders'] if phase == 'canary' else manifest['fullOrders']
                for block, order in enumerate(orders):
                    for position, variant in enumerate(order):
                        records.append({'phase':phase, 'suite':suite, 'profile':profile[0], 'profileParameters':profile,
                                        'block':block, 'order':order, 'position':position, 'variant':variant,
                                        'productionCommit':manifest['variants'][variant]['productionCommit'],
                                        'status':'not-run', 'reason':'awaiting prior protocol steps'})
    if len(records) != 411 or sum(r['phase'] == 'full' for r in records) != 396:
        raise ValueError('unexpected scheduled sample count')
    return records


def validate_build_identity(receipts, manifest, manifest_sha, clock_sha):
    hashes = []
    compiler_identities = []
    for variant in VARIANTS:
        row = receipts[variant]
        artifact = row.get('rootArtifact', {})
        compiler = artifact.get('compilerArtifact', {})
        profile = compiler.get('profile', {})
        inventory = row.get('inventory', {})
        if row.get('schema') != 'sprig-release-build-receipt-v1' or row.get('ok') is not True or row.get('variant') != variant or row.get('productionCommit') != manifest['variants'][variant]['productionCommit'] or row.get('manifestSha256') != manifest_sha:
            raise ValueError(f'{variant}: rejected/mismatched build receipt')
        if row.get('budget',{}).get('clockSha256') != clock_sha:
            raise ValueError(f'{variant}: setup clock differs from build admission clock')
        if artifact.get('passed') is not True or compiler.get('fresh') is not False or profile.get('opt_level') != '3' or profile.get('debug_assertions') is not False or profile.get('overflow_checks') is not False:
            raise ValueError(f'{variant}: actual fresh ordinary release artifact proof missing')
        if inventory.get('passed') is not True or inventory.get('actualNames') != manifest['variants'][variant]['expectedTests']:
            raise ValueError(f'{variant}: embedded inventory mismatch')
        if row.get('source', {}).get('appendOnly') is not True or row['source'].get('instrumentationSha256') != manifest['instrumentationSha256']:
            raise ValueError(f'{variant}: identical append-only instrumentation proof missing')
        binary_hash = row.get('binary', {}).get('sha256')
        if not valid_hash(binary_hash):
            raise ValueError(f'{variant}: invalid binary identity')
        hashes.append(binary_hash)
        toolchain = row.get('toolchain', {})
        identity = tuple((toolchain.get(tool, {}).get('sha256'), toolchain.get(tool, {}).get('versionSha256')) for tool in ['cargo', 'rustc'])
        if any(not valid_hash(value) for item in identity for value in item):
            raise ValueError(f'{variant}: actual compiler/toolchain identity missing')
        compiler_identities.append(identity)
    if len(set(hashes)) != 3:
        raise ValueError('identical ELF hashes across distinct variants reject stale build evidence')
    if len(set(compiler_identities)) != 1:
        raise ValueError('variants used different actual compiler identities')


def summarize(records, validator):
    full = [r for r in records if r['phase'] == 'full']
    if len(full) != 396 or any(r['status'] != 'passed' for r in full):
        raise ValueError('cannot summarize incomplete full comparison')
    comparisons, memory = [], []
    for suite, profile in dict.fromkeys((r['suite'], r['profile']) for r in full):
        rows = [r for r in full if r['suite'] == suite and r['profile'] == profile]
        if len(rows) != 18 or any(len([r for r in rows if r['variant'] == v]) != 6 for v in VARIANTS):
            raise ValueError('incomplete profile/permutation gate')
        cases = [c['case'] for c in rows[0]['report']['cases']]
        values = {}
        for case in cases:
            values[case] = {v:[statistics.median(next(c for c in r['report']['cases'] if c['case'] == case)['batchesNanoseconds']) / next(c for c in r['report']['cases'] if c['case'] == case)['callsPerBatch']
                              for r in sorted(rows, key=lambda r:r['block']) if r['variant'] == v] for v in VARIANTS}
        mem = {case:{v:[validator.memory_cases(r['report'], suite)[case] for r in sorted(rows, key=lambda r:r['block']) if r['variant'] == v] for v in VARIANTS}
               for case in validator.memory_cases(rows[0]['report'], suite)}
        for baseline, candidate in [('baseline','count'), ('baseline','narrow'), ('count','narrow')]:
            for case in cases:
                b, c = values[case][baseline], values[case][candidate]
                ratios = [y/x for x,y in zip(b,c)]
                gm = lambda seq: math.exp(statistics.mean(map(math.log, seq)))
                comparisons.append({'suite':suite,'profile':profile,'case':case,'baseline':baseline,'candidate':candidate,
                                    'perProcessMedianBatchNsPerCall':{baseline:b,candidate:c},'pairedRatios':ratios,
                                    'geometricMeanPairedRatio':gm(ratios),'baselineGeomeanNsPerCall':gm(b),'candidateGeomeanNsPerCall':gm(c),
                                    'deltaNsPerCall':gm(c)-gm(b),'allSixSlower':all(r>1 for r in ratios),'allSixFaster':all(r<1 for r in ratios)})
            for case, values_ in mem.items():
                memory.append({'suite':suite,'profile':profile,'case':case,'baseline':baseline,'candidate':candidate,
                               'perProcessMemory':{baseline:values_[baseline],candidate:values_[candidate]},
                               'pairedRssDeltaBytes':[c['rssBytes']-b['rssBytes'] for b,c in zip(values_[baseline],values_[candidate])]})
    if len(comparisons) != 336:
        raise ValueError('full three-way comparison row count mismatch')
    return comparisons, memory


def group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def settle(process):
    if group_exists(process.pid):
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    if group_exists(process.pid):
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    deadline = time.monotonic() + 2
    while group_exists(process.pid) and time.monotonic() < deadline:
        time.sleep(.05)
    return not group_exists(process.pid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ['manifest','manifest-sha256','work-root','evidence-root','clock-json']:
        parser.add_argument('--'+arg, required=True, type=str if arg == 'manifest-sha256' else Path)
    parser.add_argument('--execute', action='store_true', required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    if digest(manifest_path) != args.manifest_sha256:
        raise SystemExit('manifest digest mismatch')
    m = validate_manifest(json.loads(manifest_path.read_text()))
    for filename, expected in m['runnerSha256'].items():
        if not valid_hash(expected) or digest(manifest_path.parent / filename) != expected:
            raise SystemExit(f'frozen helper changed: {filename}')
    if m['runnerSha256'].get(Path(__file__).name) != digest(Path(__file__)):
        raise SystemExit('paired runner not frozen in manifest')
    validator = load_validator(m, manifest_path.parent)
    publication=accounting_helper()
    work = args.work_root.resolve()
    if work != args.work_root or not work.is_dir() or str(work) in {'/','/tmp','/home','/workspace'}:
        raise SystemExit('exact existing isolated work root required')
    evidence = child(args.evidence_root, work)
    evidence.mkdir(exist_ok=True)
    clock_sha = digest(args.clock_json)
    clock = json.loads(args.clock_json.read_text())
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    deadline = validate_clock(clock, time.monotonic(), boot_id)
    output = evidence / 'release-core'
    output.mkdir(exist_ok=False)
    result = {'schema':'sprig-directory-counts-release-results-v1','complete':False,'ok':False,'canaryPassed':False,
              'manifestSha256':args.manifest_sha256,'runnerSha256':digest(Path(__file__)),'clock':clock,'clockSha256':clock_sha,'limits':m['limits'],
              'label':m['label'],'interpretation':m['interpretation'],'records':make_schedule(m),'builds':{},'error':None}
    limits = m['limits']
    minimum_free = shutil.disk_usage(work).free
    command_budget=publication.Budget(args.clock_json,work,evidence,limits)
    result['captureCommands']=command_budget.commands
    def final_budget(extra=0):
        nonlocal minimum_free
        current_free=shutil.disk_usage(work).free
        minimum_free=min(minimum_free,current_free,command_budget.minimum_free)
        if digest(args.clock_json)!=clock_sha: raise RuntimeError('shared setup clock changed')
        if current_free<limits['minimumFreeBytes']+extra: raise RuntimeError('final free-space/write reservation exhausted')
        if allocated(evidence)+extra>limits['maximumEvidenceBytes']: raise RuntimeError('final evidence/write reservation exhausted')
        if time.monotonic()>deadline: raise RuntimeError('final setup-inclusive deadline exhausted')
    def save():
        result['elapsedSetupInclusiveSeconds'] = time.monotonic()-clock['startedMonotonic']
        result['minimumObservedFreeBytes'] = minimum_free
        result['evidenceAllocatedBytes'] = allocated(evidence)
        publication.write_checked_json(output/'summary.json',result,final_budget,'summary.progress-pending.json')
    def budget(admit=False):
        nonlocal minimum_free
        now = time.monotonic()
        if digest(args.clock_json) != clock_sha: raise RuntimeError('shared setup clock changed')
        validate_clock(clock, now, Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        minimum_free = min(minimum_free, shutil.disk_usage(work).free)
        reserve = limits['finalizeReserveSeconds'] + (limits['processSeconds']+limits['cleanupReserveSeconds'] if admit else 0)
        if now+reserve > deadline: raise RuntimeError('setup-inclusive admission deadline/reserve exhausted')
        if minimum_free < limits['minimumFreeBytes']: raise RuntimeError('disk free below 1.5 GiB floor')
        if allocated(evidence) > limits['maximumEvidenceBytes']-limits['evidenceFinalizeReserveBytes']: raise RuntimeError('complete evidence allocation reserve exhausted')
    save()
    binaries, receipts = {}, {}
    lock = None
    computations_complete = False
    def verify_sources():
        for variant,receipt in receipts.items():
            source = child(Path(receipt['source']['path']),work)
            for filename,expected in receipt['source']['afterHashes'].items():
                path=child(source/filename,source)
                if not path.is_file() or digest(path)!=expected: raise ValueError(f'{variant}: source changed after verified build: {filename}')
    try:
        budget()
        lock_path=work/'release-helper.lock'
        if lock_path.exists() and (lock_path.is_symlink() or lock_path.stat().st_nlink!=1):
            raise ValueError('unsafe shared serial-admission lock')
        lock=lock_path.open('a+b')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for variant in VARIANTS:
            receipt_path = child(evidence/'build-receipts'/f'{variant}.json', evidence)
            receipt = json.loads(receipt_path.read_text())
            binary = child(Path(receipt['binary']['path']), evidence)
            if not binary.is_file() or binary.stat().st_nlink!=1 or stat.S_IMODE(binary.stat().st_mode)!=0o555 or digest(binary) != receipt['binary']['sha256']:
                raise ValueError(f'{variant}: copied executable hash mismatch')
            binaries[variant] = binary; receipts[variant] = receipt
            result['builds'][variant] = {'receipt':str(receipt_path),'receiptSha256':digest(receipt_path),'binary':str(binary),'binarySha256':digest(binary),'productionCommit':receipt['productionCommit']}
        validate_build_identity(receipts,m,args.manifest_sha256,clock_sha)
        verify_sources()
        layouts, topology = {}, {}
        for record in result['records']:
            if record['phase'] == 'full' and not result['canaryPassed']:
                canary = [r for r in result['records'] if r['phase'] == 'canary']
                if len(canary) != 15 or any(r['status'] != 'passed' for r in canary):
                    raise ValueError('full run forbidden without complete successful canary')
                result['canaryPassed'] = True
                save()
            budget(admit=True)
            suite, profile, variant = record['suite'],record['profileParameters'],record['variant']
            name = f"{record['phase']}-{suite}-{record['profile']}-block{record['block']}-{record['position']}-{variant}"
            folder = output / name; folder.mkdir(exist_ok=False)
            fixture = folder / 'fixture'
            command = [str(binaries[variant]),TESTS[suite],'--ignored','--exact','--test-threads=1','--nocapture']
            env = os.environ.copy()
            for key in list(env):
                if key.startswith('SPRIG_DIRECTORY_'): env.pop(key)
            env.pop('SPRIG_WRITABLE_DIAGNOSTICS',None)
            env['SPRIG_DIRECTORY_OUTPUT'] = str(fixture)
            if suite == 'attr':
                _,files,retired,layout,wide,hot=profile
                env.update(SPRIG_DIRECTORY_UNRELATED=str(files),SPRIG_DIRECTORY_RETIRED=str(retired),SPRIG_DIRECTORY_LAYOUT=layout,SPRIG_DIRECTORY_WIDE=str(wide),SPRIG_DIRECTORY_HOT_ENTRIES=str(hot))
            else: env['SPRIG_DIRECTORY_LIFECYCLE_PROFILE']=profile[0]
            record.update(status='running',reason=None,folder=str(folder),command=command,startedMonotonic=time.monotonic())
            save()
            reason = None
            log_path=folder/'process.log'
            prior_commands=len(command_budget.commands)
            try:
                publication.command(command,work,env,log_path,command_budget,
                                    seconds=limits['processSeconds'],maximum_log_bytes=limits['maximumReportBytes'],
                                    live_cleanup_root=fixture if suite=='lifecycle' else None)
            except BaseException as error:
                reason=f'{type(error).__name__}: {error}'
            captured=command_budget.commands[-1] if len(command_budget.commands)>prior_commands else {}
            record.update(returncode=captured.get('returncode'),wallSeconds=time.monotonic()-record['startedMonotonic'],reason=reason,
                          ownedProcessGroupSettled=captured.get('settled',False),
                          logSha256=digest(log_path) if log_path.exists() else None,
                          retainedLogBytes=captured.get('retainedLogBytes'),maximumLogBytes=limits['maximumReportBytes'])
            if record['returncode'] != 0 or reason or not record['ownedProcessGroupSettled'] or record['wallSeconds']>limits['processSeconds']:
                record['status']='failed';save();raise RuntimeError(f'{name}: failed process {reason or record["returncode"]}')
            budget()
            report_path = fixture/'report.json'
            if report_path.stat().st_size > limits['maximumReportBytes']:
                raise ValueError('per-process report exceeds 1 MiB')
            report=json.loads(report_path.read_text())
            (validator.validate_attr_report if suite=='attr' else validator.validate_lifecycle_report)(report,profile)
            if suite=='lifecycle' and {p.name for p in fixture.iterdir()}!={'objects','report.json'}:
                raise ValueError('successful lifecycle generation cleanup incomplete')
            key=(suite,profile[0]); observed=validator.comparable_topology(report,suite)
            if key in topology and topology[key]!=observed: raise ValueError('cross-variant fixture/topology mismatch')
            topology[key]=observed
            layout=(report['nodeSizeBytes'],report['nodeAlignmentBytes'])
            if variant in layouts and layouts[variant]!=layout: raise ValueError('layout changed inside immutable variant')
            layouts[variant]=layout
            record.update(status='passed',report=report,reportSha256=digest(report_path));save()
        result['protectedBinariesUnchanged']=all(digest(binaries[v])==receipts[v]['binary']['sha256'] for v in VARIANTS)
        if not result['protectedBinariesUnchanged']: raise ValueError('frozen executable changed during measurements')
        verify_sources()
        result['sourcesUnchanged']=True
        if digest(manifest_path)!=args.manifest_sha256: raise ValueError('frozen manifest changed during measurements')
        if any(digest(Path(info['receipt']))!=info['receiptSha256'] for info in result['builds'].values()):
            raise ValueError('build receipt changed during measurements')
        result['comparisons'],result['memoryComparisons']=summarize(result['records'],validator)
        result['nodeLayoutByVariant']={v:{'sizeBytes':size,'alignmentBytes':align} for v,(size,align) in layouts.items()}
        budget()
        computations_complete=True
    except BaseException as error:
        result['error']=f'{type(error).__name__}: {error}'
        for record in result['records']:
            if record['status']=='running': record.update(status='failed',reason=result['error'])
            elif record['status']=='not-run': record['reason']=f'not admitted after protocol stop: {result["error"]}'
    finally:
        result['elapsedSetupInclusiveSeconds']=time.monotonic()-clock['startedMonotonic']
        result['minimumObservedFreeBytes']=min(minimum_free,command_budget.minimum_free)
        result['evidenceAllocatedBytes']=allocated(evidence)
        publication.checked_publish(output/'summary.json',result,computations_complete,final_budget)
        if lock is not None: lock.close()
    print(json.dumps({'ok':result['ok'],'complete':result['complete'],'canaryPassed':result['canaryPassed'],'summary':str(output/'summary.json'),'error':result['error'] or result.get('finalizationError')}))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
