#!/usr/bin/env python3
"""Copy only named benchmark evidence; never traverse runtime roots or change sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from stress_cargo_pressure_profiles import experiment_for

RESULTS = set('cargo-toolchain-capacity.txt cargo-image-capacity.txt cargo-image-build.txt cargo-image.json cargo-software-identity.txt current-writable-contract.json docker-updated.txt environment.txt production-binary-hash.txt production-kernel-contract.json production-source-hashes.txt projection-rust-version.txt runtime-image.json script-hashes.txt stress-cargo-capacity-status.json stress-cargo-capacity.json stress-cargo-generated.json stress-cargo-lock-generation.txt stress-cargo-manifest.json stress-cargo-oracle.json'.split())
CLEAN_SYNC_TTL_RESULTS = set(RESULTS)
VERIFIED_READ_REUSE_RESULTS = set(RESULTS)
LATEST_DIRECT_RESULTS = set(RESULTS)
RESULTS.update('stress-cargo-own-ab-summary.json stress-cargo-ab-products.json baseline-source-hashes.txt candidate-source-hashes.txt baseline-binary-hash.txt candidate-binary-hash.txt baseline-release-build.log candidate-release-build.log baseline-tests.txt candidate-tests.txt baseline-projection-gate.json candidate-projection-gate.json baseline-writable-gate.json candidate-writable-gate.json'.split())
LATEST_DIRECT_SETUP = set('stress-cargo-latest-direct-identity.json stress-cargo-latest-direct-summary.json latest-main-selection.txt layerfs-source-hashes.txt layerfs-binary-hashes.txt layerfs-rust-version.txt layerfs-cargo-version.txt node-npm-versions.txt layerfs-release-build.log production-tests.txt production-release-build.log'.split())
RESULTS.update(LATEST_DIRECT_SETUP)
LATEST_DIRECT_RESULTS.update(LATEST_DIRECT_SETUP)
RESULTS.update('stress-cargo-directory-abc-products.json stress-cargo-directory-abc-plan.json stress-cargo-directory-abc-summary.json abc-rust-version.txt abc-cargo-version.txt abc-toolchain-hashes.txt abc-source-pins.json'.split())
for _label in ('baseline','count','narrow'):
    RESULTS.update(f'abc-{_label}-{suffix}' for suffix in ('source-hashes.txt','binary-hash.txt','release-build.log','tests.txt'))
ABC_PRODUCTS = ('sprig-baseline', 'sprig-count', 'sprig-narrow')
ABC_EXPERIMENT = dict(schema='sprig-cargo-directory-abc-experiment-v1',profile='ordinary',roundsPerMode=6,incrementalModes=[0,1],order='six-permutations-reverse-mode1',pressure=None)
CLEAN_SYNC_TTL_PRODUCTS = ('sprig-baseline', 'sprig-clean-sync', 'sprig-read-ttl')
CLEAN_SYNC_TTL_EXPERIMENT = dict(schema='sprig-cargo-clean-sync-ttl-experiment-v1',profile='ordinary',roundsPerMode=6,incrementalModes=[0,1],order='six-permutations-reverse-mode1',pressure=None)
CLEAN_SYNC_TTL_RESULTS.update('stress-cargo-clean-sync-ttl-products.json stress-cargo-clean-sync-ttl-plan.json stress-cargo-clean-sync-ttl-summary.json cst-rust-version.txt cst-cargo-version.txt cst-toolchain-hashes.txt cst-source-pins.json cst-source-selection.json'.split())
for _label in ('baseline','clean-sync','read-ttl'):
    CLEAN_SYNC_TTL_RESULTS.update(f'cst-{_label}-{suffix}' for suffix in ('source-hashes.txt','binary-hash.txt','release-build.log','tests.txt'))
CLEAN_SYNC_TTL_PRODUCT = r'(?:' + '|'.join(CLEAN_SYNC_TTL_PRODUCTS) + ')'
CLEAN_SYNC_TTL_ROUND_PRODUCT = CLEAN_SYNC_TTL_PRODUCT + r'-[0-5]'
CLEAN_SYNC_TTL_SAMPLE_NAME = CLEAN_SYNC_TTL_PRODUCT + r'-inc[01]-[0-5]'
VERIFIED_READ_REUSE_PRODUCTS = ('sprig-baseline', 'sprig-verified-read-reuse')
VERIFIED_READ_REUSE_EXPERIMENT = dict(schema='sprig-cargo-verified-read-reuse-experiment-v1',profile='ordinary',roundsPerMode=6,incrementalModes=[0,1],order='six-alternating-reverse-mode1',pressure=None)
VERIFIED_READ_REUSE_RESULTS.update('stress-cargo-verified-read-reuse-products.json stress-cargo-verified-read-reuse-plan.json stress-cargo-verified-read-reuse-summary.json vrr-rust-version.txt vrr-cargo-version.txt vrr-toolchain-hashes.txt vrr-source-pins.json vrr-source-selection.json'.split())
for _label in ('baseline','verified-read-reuse'):
    VERIFIED_READ_REUSE_RESULTS.update(f'vrr-{_label}-{suffix}' for suffix in ('source-hashes.txt','binary-hash.txt','release-build.log','tests.txt'))
VERIFIED_READ_REUSE_PRODUCT = r'(?:' + '|'.join(VERIFIED_READ_REUSE_PRODUCTS) + ')'
VERIFIED_READ_REUSE_ROUND_PRODUCT = VERIFIED_READ_REUSE_PRODUCT + r'-[0-5]'
VERIFIED_READ_REUSE_SAMPLE_NAME = VERIFIED_READ_REUSE_PRODUCT + r'-inc[01]-[0-5]'
COMPARATOR_PRODUCTS = ('sprig-writable', 'layerfs')
OWN_AB_PRODUCTS = ('sprig-baseline', 'sprig-candidate')
PRODUCT = r'(?:' + '|'.join(dict.fromkeys(COMPARATOR_PRODUCTS + OWN_AB_PRODUCTS + ABC_PRODUCTS)) + ')'
COMPARATOR = r'(?:' + '|'.join(COMPARATOR_PRODUCTS) + ')'
OWN_AB = r'(?:' + '|'.join(OWN_AB_PRODUCTS) + ')'
ABC = r'(?:' + '|'.join(ABC_PRODUCTS) + ')'
ROUND_PRODUCT = r'(?:' + COMPARATOR + r'-[0-2]|' + OWN_AB + r'-[0-3])'
ABC_ROUND_PRODUCT = r'(?:' + ROUND_PRODUCT + '|' + ABC + r'-[0-5])'
SAMPLE_NAME = r'(?:' + COMPARATOR + r'-inc[01]-[0-2]|' + OWN_AB + r'-inc[01]-[0-3])'
ABC_SAMPLE_NAME = r'(?:' + SAMPLE_NAME + '|' + ABC + r'-inc[01]-[0-5])'
LATEST_DIRECT_ROUND_PRODUCT = COMPARATOR + r'-[01]'
LATEST_DIRECT_SAMPLE_NAME = COMPARATOR + r'-inc[01]-[01]'
ORDINARY_EXPERIMENT = dict(schema='sprig-cargo-experiment-v1',profile='ordinary',roundsPerMode=4,incrementalModes=[0,1],order='alternating-pairs-mode-offset',pressure=None)

def allowed(group, parts, abc=False, latest_direct=False, clean_sync_ttl=False, verified_read_reuse=False):
    if sum(map(bool,(abc,latest_direct,clean_sync_ttl,verified_read_reuse)))>1:raise ValueError('ABC, latest-direct, clean-sync-TTL and verified-read collection modes are mutually exclusive')
    round_product=VERIFIED_READ_REUSE_ROUND_PRODUCT if verified_read_reuse else CLEAN_SYNC_TTL_ROUND_PRODUCT if clean_sync_ttl else LATEST_DIRECT_ROUND_PRODUCT if latest_direct else ABC_ROUND_PRODUCT if abc else ROUND_PRODUCT
    sample_name=VERIFIED_READ_REUSE_SAMPLE_NAME if verified_read_reuse else CLEAN_SYNC_TTL_SAMPLE_NAME if clean_sync_ttl else LATEST_DIRECT_SAMPLE_NAME if latest_direct else ABC_SAMPLE_NAME if abc else SAMPLE_NAME
    if group == 'results':
        names=VERIFIED_READ_REUSE_RESULTS if verified_read_reuse else CLEAN_SYNC_TTL_RESULTS if clean_sync_ttl else LATEST_DIRECT_RESULTS if latest_direct else RESULTS
        comparisons='verified-read-reuse' if verified_read_reuse else 'clean-sync-ttl' if clean_sync_ttl else 'comparison' if latest_direct else 'comparison|own-ab|directory-abc'
        return len(parts)==1 and (parts[0] in names or re.fullmatch(r'stress-cargo-(?:(?:'+comparisons+r')-[01]|'+sample_name+r')\.json', parts[0]))
    if group == 'capacity':
        return len(parts)==1 and re.fullmatch(r'inc[01]\.(?:stdout|stderr)', parts[0])
    if group == 'records' and len(parts) in (2,3) and re.fullmatch(r'inc[01]',parts[0]):
        if len(parts)==2:
            return re.fullmatch(round_product+r'(?:\.jsonl|-options\.json)',parts[1])
        return re.fullmatch(round_product+r'\.jsonl\.logs',parts[1]) and re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:stdout|stderr|log|jsonl)',parts[2])
    return False


def verify_declared_archives(destination, temporary, copied, abc_mode=False, latest_direct_mode=False, clean_sync_ttl_mode=False, verified_read_reuse_mode=False):
    """Check declarations against copied bytes, never follow a report-provided path."""
    inventory={row['path']:row for row in copied}
    errors=[];verified=set();samples=0
    def verify(sample, product, incremental, round_):
        nonlocal samples
        samples+=1
        if not isinstance(sample,dict):errors.append('invalid sample report');return
        archive=sample.get('completeLogArchive')
        if archive is None and sample.get('ok') is not True:return
        if not isinstance(archive,list) or (sample.get('ok') is True and not archive):
            errors.append('missing/non-list archive declaration');return
        expected=temporary/'stress-cargo-records'/f'inc{incremental}'/f'{product}-{round_}.jsonl.logs'
        seen=set()
        for item in archive:
            if not isinstance(item,dict):errors.append('invalid archive entry');continue
            if not isinstance(item.get('archived'),str):errors.append('invalid archive path');continue
            if type(item.get('bytes')) is not int or item['bytes'] < 0 or not isinstance(item.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', item['sha256']):
                errors.append('invalid archive size/hash');continue
            path=Path(item['archived'])
            parts=(f'inc{incremental}',f'{product}-{round_}.jsonl.logs',path.name)
            if path.parent!=expected or not allowed('records',parts,abc=abc_mode,latest_direct=latest_direct_mode,clean_sync_ttl=clean_sync_ttl_mode,verified_read_reuse=verified_read_reuse_mode):
                errors.append('archive path outside exact sample allowlist');continue
            key='records/'+'/'.join(parts)
            if key in seen:errors.append('duplicate archive declaration');continue
            seen.add(key);actual=inventory.get(key)
            if actual is None or actual['bytes']!=item.get('bytes') or actual['sha256']!=item.get('sha256'):
                errors.append('missing or mismatched declared archive: '+key);continue
            verified.add(key)
    for row in copied:
        name=Path(row['path']).name
        if not row['path'].startswith('results/'):continue
        match=re.fullmatch(r'stress-cargo-('+(VERIFIED_READ_REUSE_PRODUCT if verified_read_reuse_mode else CLEAN_SYNC_TTL_PRODUCT if clean_sync_ttl_mode else PRODUCT)+r')-inc([01])-([0-5])\.json',name)
        comparison=re.fullmatch(r'stress-cargo-(' + ('verified-read-reuse' if verified_read_reuse_mode else 'clean-sync-ttl' if clean_sync_ttl_mode else 'comparison|own-ab|directory-abc') + r')-([01])\.json',name)
        if not match and not comparison:continue
        try:report=json.loads((destination/row['path']).read_text())
        except (ValueError,UnicodeError):errors.append('invalid report JSON: '+row['path']);continue
        if not isinstance(report,dict):errors.append('invalid report object');continue
        if match:verify(report,match[1],match[2],match[3])
        else:
            verified_read_reuse = comparison[1]=='verified-read-reuse'
            if verified_read_reuse and (report.get('schema')!='sprig-stress-cargo-verified-read-reuse-v1' or type(report.get('rounds')) is not int or report['rounds']!=6 or type(report.get('expectedRecords')) is not int or report['expectedRecords']!=12 or type(report.get('incremental')) is not int or report['incremental']!=int(comparison[2]) or report.get('abcExperiment')!=VERIFIED_READ_REUSE_EXPERIMENT):
                errors.append('invalid verified-read report identity');continue
            clean_sync_ttl = comparison[1]=='clean-sync-ttl'
            if clean_sync_ttl and (report.get('schema')!='sprig-stress-cargo-clean-sync-ttl-v1' or type(report.get('rounds')) is not int or report['rounds']!=6 or type(report.get('expectedRecords')) is not int or report['expectedRecords']!=18 or type(report.get('incremental')) is not int or report['incremental']!=int(comparison[2]) or report.get('abcExperiment')!=CLEAN_SYNC_TTL_EXPERIMENT):
                errors.append('invalid clean-sync-TTL report identity');continue
            abc = comparison[1]=='directory-abc'
            if abc and (report.get('schema')!='sprig-stress-cargo-directory-abc-v1' or type(report.get('rounds')) is not int or report['rounds']!=6 or type(report.get('expectedRecords')) is not int or report['expectedRecords']!=18 or type(report.get('incremental')) is not int or report['incremental']!=int(comparison[2]) or report.get('abcExperiment')!=ABC_EXPERIMENT):
                errors.append('invalid directory-ABC report identity');continue
            own_ab = comparison[1]=='own-ab'
            latest_direct_v2 = report.get('schema')=='sprig-stress-cargo-latest-direct-v2'
            latest_direct = latest_direct_v2 or report.get('schema')=='sprig-stress-cargo-latest-direct-v1'
            if latest_direct_mode and (comparison[1]!='comparison' or not latest_direct_v2):
                errors.append('invalid latest-direct-v2 report schema');continue
            if latest_direct and (own_ab or (latest_direct_v2 and comparison[1]!='comparison') or type(report.get('rounds')) is not int or report['rounds']!=2 or type(report.get('expectedRecords')) is not int or report['expectedRecords']!=4 or type(report.get('incremental')) is not int or report['incremental']!=int(comparison[2])):
                errors.append('invalid current-main direct report shape');continue
            if own_ab and (report.get('schema') not in ('sprig-stress-cargo-own-ab-v1','sprig-stress-cargo-own-ab-v2') or type(report.get('incremental')) is not int or report['incremental']!=int(comparison[2])):
                errors.append('invalid own-AB report schema/incremental identity');continue
            repeated=own_ab and report.get('schema')=='sprig-stress-cargo-own-ab-v2'
            expected_experiment=ORDINARY_EXPERIMENT
            if repeated:
                try:expected_experiment=experiment_for(report.get('experimentSpec',{}).get('profile','ordinary'))
                except (ValueError,AttributeError):errors.append('invalid repeated own-AB experiment profile');continue
            if repeated and (report.get('rounds')!=4 or type(report.get('rounds')) is not int or report.get('experimentSpec')!=expected_experiment):
                errors.append('invalid repeated own-AB experiment identity');continue
            records=report.get('records',[])
            if not isinstance(records,list):errors.append('invalid comparison records');continue
            if latest_direct_v2 and (len(records)>4 or (report.get('complete') is True and len(records)!=4)):
                errors.append('invalid latest-direct-v2 record count');continue
            if clean_sync_ttl and (len(records)>18 or (report.get('complete') is True and len(records)!=18)):
                errors.append('invalid clean-sync-TTL record count');continue
            if verified_read_reuse and (len(records)>12 or (report.get('complete') is True and len(records)!=12)):
                errors.append('invalid verified-read record count');continue
            direct_seen=set();clean_seen=set()
            for record in records:
                if not isinstance(record,dict):errors.append('invalid comparison record');continue
                if clean_sync_ttl or verified_read_reuse:
                    fixed_products=VERIFIED_READ_REUSE_PRODUCTS if verified_read_reuse else CLEAN_SYNC_TTL_PRODUCTS
                    if record.get('product') not in fixed_products or type(record.get('round')) is not int or record['round'] not in range(6) or ('incremental' in record and (type(record['incremental']) is not int or record['incremental']!=int(comparison[2]))):
                        errors.append('invalid fixed-series record identity');continue
                    identity=(record['product'],record['round'])
                    if identity in clean_seen:errors.append('duplicate fixed-series record');continue
                    clean_seen.add(identity)
                if latest_direct_v2:
                    if record.get('product') not in COMPARATOR_PRODUCTS or type(record.get('round')) is not int or record['round'] not in (0,1) or ('incremental' in record and (type(record['incremental']) is not int or record['incremental']!=int(comparison[2]))):
                        errors.append('invalid latest-direct-v2 record identity');continue
                    identity=(record['product'],record['round'])
                    if identity in direct_seen:errors.append('duplicate latest-direct-v2 record');continue
                    direct_seen.add(identity)
                if 'sample' not in record:continue # runtime setup can fail before sampler
                products = VERIFIED_READ_REUSE_PRODUCTS if verified_read_reuse else CLEAN_SYNC_TTL_PRODUCTS if clean_sync_ttl else ABC_PRODUCTS if abc else OWN_AB_PRODUCTS if comparison[1]=='own-ab' else COMPARATOR_PRODUCTS
                if record.get('product') not in products or type(record.get('round')) is not int or record['round'] not in (range(6) if abc or clean_sync_ttl or verified_read_reuse else range(4) if repeated else range(1) if own_ab else range(2) if latest_direct else range(3)):
                    errors.append('invalid comparison sample identity');continue
                verify(record['sample'],record['product'],comparison[2],record['round'])
    return {'ok':not errors,'sampleDeclarations':samples,'verifiedUniqueFiles':len(verified),'errors':errors}


ABC_EVIDENCE_CAP = 1024**3
ABC_MANIFEST_RESERVE = 8 * 1024**2


def evidence_charge(info):
    return max(info.st_size, info.st_blocks * 512)


def stable_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def collect_abc_bounded(results, temporary, destination, uid, gid, latest_direct=False, clean_sync_ttl=False, verified_read_reuse=False):
    """Explicit bounded series: admit every named file before copying; retain originals.

    One GiB bounds the complete destination, including allocated file/directory
    bytes and the transient pending manifest. It is not a source-filesystem quota.
    """
    plan=[]; directories={destination}
    label='verified-read' if verified_read_reuse else 'clean-sync-TTL' if clean_sync_ttl else 'latest-direct' if latest_direct else 'ABC'
    series={'series':'sprig-stress-cargo-verified-read-reuse-v1'} if verified_read_reuse else {'series':'sprig-stress-cargo-clean-sync-ttl-v1'} if clean_sync_ttl else {'series':'sprig-stress-cargo-latest-direct-v2'} if latest_direct else {}
    round_product=VERIFIED_READ_REUSE_ROUND_PRODUCT if verified_read_reuse else CLEAN_SYNC_TTL_ROUND_PRODUCT if clean_sync_ttl else LATEST_DIRECT_ROUND_PRODUCT if latest_direct else ABC_ROUND_PRODUCT
    roots={'results':results,'capacity':temporary/'stress-cargo-capacity-pilot',
           'records':temporary/'stress-cargo-records'}
    for group,root in roots.items():
        if not root.exists() and not root.is_symlink():continue
        if root.is_symlink() or not root.is_dir():raise ValueError('unsafe evidence root')
        candidates=[]
        if group!='records':candidates=[(p,(p.name,)) for p in root.iterdir()]
        else:
            for inc in ('inc0','inc1'):
                directory=root/inc
                if not directory.exists() and not directory.is_symlink():continue
                if directory.is_symlink() or not directory.is_dir():raise ValueError('unsafe records directory')
                for source in directory.iterdir():
                    candidates.append((source,(inc,source.name)))
                    if re.fullmatch(round_product+r'\.jsonl\.logs',source.name):
                        if source.is_symlink() or not source.is_dir():raise ValueError('unsafe log directory')
                        candidates.extend((f,(inc,source.name,f.name)) for f in source.iterdir())
        for source,parts in sorted(candidates):
            if not allowed(group,parts,abc=not (latest_direct or clean_sync_ttl or verified_read_reuse),latest_direct=latest_direct,clean_sync_ttl=clean_sync_ttl,verified_read_reuse=verified_read_reuse):continue
            info=source.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('only independent regular evidence files allowed')
            target=destination/group/Path(*parts)
            parent=target.parent
            while parent!=destination:
                directories.add(parent);parent=parent.parent
            plan.append((source,target,info))
    # Source allocation can exceed logical bytes; destination rounds up even when
    # a sparse source uses fewer blocks. Reserve the entire final JSON separately.
    planned=sum(max(evidence_charge(info),((info.st_size+4095)//4096)*4096) for _,_,info in plan)
    planned+=len(directories)*4096+ABC_MANIFEST_RESERVE
    if planned>ABC_EVIDENCE_CAP:raise ValueError(label+' full evidence plan exceeds 1 GiB; no archive copied; originals retained')
    rows=[]; files=[]; made=[]; sealed={}
    def charge(extra=0):
        # Closed destination files are immutable in this owner; scan directory
        # blocks and the active stream on each write, then strictly recheck all
        # sealed identities before final promotion (avoid quadratic stat work).
        total=sum(sealed[path][1] if path in sealed else evidence_charge(path.lstat()) for path in files)
        total+=sum(evidence_charge(path.lstat()) for path in made)
        if total+extra>ABC_EVIDENCE_CAP:raise ValueError(label+' evidence budget exceeded; originals retained')
        return total
    def mkdir(path):
        if path in made:return
        if path!=destination:mkdir(path.parent)
        charge(4096+ABC_MANIFEST_RESERVE)
        path.mkdir(mode=0o755);os.chmod(path,0o755);os.chown(path,uid,gid);made.append(path)
        charge(ABC_MANIFEST_RESERVE)
    def save(value, final=False):
        if final:
            for target,(identity,_) in sealed.items():
                if stable_identity(target.lstat())!=identity:raise ValueError('copied evidence changed before manifest promotion')
        data=(json.dumps(value,indent=2)+'\n').encode()
        if len(data)>ABC_MANIFEST_RESERVE//2:raise ValueError(label+' collection manifest exceeds reserved bound')
        pending=destination/'collection.pending.json'
        charge(((len(data)+4095)//4096)*4096)
        fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno());os.fchown(out.fileno(),uid,gid)
        files.append(pending);charge()
        # Last operation publishes the fully written and budget-checked receipt.
        manifest=destination/'collection.json';old=manifest in files
        os.replace(pending,manifest)
        files.remove(pending)
        if not old:files.append(manifest)
    mkdir(destination)
    save({'schema':'sprig-cargo-artifact-copy-v1',**series,'complete':False,'files':[],
          'sourceFilesRetained':True,'budgetBytes':ABC_EVIDENCE_CAP,'plannedBytesWithReserve':planned})
    try:
        for source,target,before in plan:
            mkdir(target.parent)
            fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as stream:
                if stable_identity(os.fstat(stream.fileno()))!=stable_identity(before):raise ValueError('source evidence changed before copy')
                fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
                files.append(target);hash_=hashlib.sha256();count=0
                with os.fdopen(fd,'wb') as out:
                    os.fchmod(out.fileno(),0o644);os.fchown(out.fileno(),uid,gid)
                    while count<before.st_size:
                        block=stream.read(min(1024**2,before.st_size-count))
                        if not block:raise ValueError('source evidence shortened during copy')
                        charge(len(block)+4096+ABC_MANIFEST_RESERVE)
                        out.write(block);out.flush();hash_.update(block);count+=len(block)
                        charge(ABC_MANIFEST_RESERVE)
                    if stream.read(1):raise ValueError('source evidence grew during copy')
                    if stable_identity(os.fstat(stream.fileno()))!=stable_identity(before) or stable_identity(source.lstat())!=stable_identity(before):raise ValueError('source evidence identity changed during copy')
                    out.flush();os.fsync(out.fileno())
                    charge(ABC_MANIFEST_RESERVE)
            finished=target.lstat();sealed[target]=(stable_identity(finished),evidence_charge(finished))
            rows.append({'path':str(target.relative_to(destination)),'bytes':count,
                         'allocatedBytes':finished.st_blocks*512,'sha256':hash_.hexdigest()})
        for target,(identity,_) in sealed.items():
            if stable_identity(target.lstat())!=identity:raise ValueError('copied evidence changed before final audit')
        coverage=verify_declared_archives(destination,temporary,rows,abc_mode=not (latest_direct or clean_sync_ttl or verified_read_reuse),latest_direct_mode=latest_direct,clean_sync_ttl_mode=clean_sync_ttl,verified_read_reuse_mode=verified_read_reuse)
        value={'schema':'sprig-cargo-artifact-copy-v1',**series,'complete':coverage['ok'],
               'files':rows,'declaredArchiveVerification':coverage,'sourceFilesRetained':True,
               'budgetBytes':ABC_EVIDENCE_CAP,'plannedBytesWithReserve':planned,
               'chargedBytesBeforeFinalManifest':charge(),
               'accounting':'sum max(logical, allocated) for every copied file and directory; pending manifest charged before promotion'}
        save(value,final=True)
        if not coverage['ok']:raise ValueError('declared archive completeness failed; see collection.json')
        return rows
    except Exception as error:
        # No subset is complete. Input reports/archives remain; image retention
        # follows the unchanged sampler cleanup (no image-backup promise).
        try:save({'schema':'sprig-cargo-artifact-copy-v1',**series,'complete':False,'files':rows,
                  'sourceFilesRetained':True,'budgetBytes':ABC_EVIDENCE_CAP,'error':str(error),
                  'declaredArchiveVerification':locals().get('coverage',{'ok':False,'errors':['collection incomplete']})})
        except Exception:pass # the authoritative initial receipt is already FAIL
        raise


def collect(results, temporary, destination, uid, gid, abc=False, latest_direct=False, clean_sync_ttl=False, verified_read_reuse=False):
    if sum(map(bool,(abc,latest_direct,clean_sync_ttl,verified_read_reuse)))>1:raise ValueError('ABC, latest-direct, clean-sync-TTL and verified-read collection modes are mutually exclusive')
    for parent in (results.parent, temporary, destination.parent):
        if parent.resolve(strict=True)!=parent:raise ValueError('exact nonsymlink parents required')
    if destination.exists() or destination.is_symlink():raise ValueError('new artifact destination required')
    if destination.is_relative_to(results) or destination.is_relative_to(temporary):
        raise ValueError('artifact destination must be separate from evidence input roots')
    if verified_read_reuse:
        return collect_abc_bounded(results,temporary,destination,uid,gid,verified_read_reuse=True)
    if clean_sync_ttl:
        return collect_abc_bounded(results,temporary,destination,uid,gid,clean_sync_ttl=True)
    if latest_direct:
        return collect_abc_bounded(results,temporary,destination,uid,gid,latest_direct=True)
    if abc or any((results/name).exists() for name in ('stress-cargo-directory-abc-products.json','stress-cargo-directory-abc-0.json','stress-cargo-directory-abc-1.json')):
        return collect_abc_bounded(results,temporary,destination,uid,gid)
    def mkdir(path):
        if not path.exists():
            path.mkdir(mode=0o755);os.chmod(path,0o755);os.chown(path,uid,gid)
    mkdir(destination)
    rows=[]
    abc_mode=any((results/name).exists() for name in ('stress-cargo-directory-abc-products.json','stress-cargo-directory-abc-0.json','stress-cargo-directory-abc-1.json'))
    round_product=ABC_ROUND_PRODUCT if abc_mode else ROUND_PRODUCT
    roots={'results':results,'capacity':temporary/'stress-cargo-capacity-pilot','records':temporary/'stress-cargo-records'}
    for group,root in roots.items():
        if not root.exists() and not root.is_symlink():continue # failed setup may create none
        if root.is_symlink() or not root.is_dir():raise ValueError('unsafe evidence root')
        # Explicit depth/shape limits: never descend into pilot source/target or runtime.
        candidates=[]
        if group!='records':candidates=[(p,(p.name,)) for p in root.iterdir()]
        else:
            for inc in ('inc0','inc1'):
                directory=root/inc
                if not directory.exists() and not directory.is_symlink():continue
                if directory.is_symlink() or not directory.is_dir():raise ValueError('unsafe records directory')
                for p in directory.iterdir():
                    candidates.append((p,(inc,p.name)))
                    if re.fullmatch(round_product+r'\.jsonl\.logs',p.name):
                        if p.is_symlink() or not p.is_dir():raise ValueError('unsafe log directory')
                        candidates.extend((f,(inc,p.name,f.name)) for f in p.iterdir())
        for source,parts in sorted(candidates):
            if not allowed(group,parts,abc=abc_mode):continue
            fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('only independent regular evidence files allowed')
                data=stream.read()
            target=destination/group
            mkdir(target)
            for part in parts[:-1]:target=target/part;mkdir(target)
            target=target/parts[-1]
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'wb') as out:out.write(data);os.fchmod(out.fileno(),0o644);os.fchown(out.fileno(),uid,gid)
            rows.append({'path':str(target.relative_to(destination)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    coverage=verify_declared_archives(destination,temporary,rows,abc_mode=abc_mode)
    manifest=destination/'collection.json'
    manifest.write_text(json.dumps({'schema':'sprig-cargo-artifact-copy-v1','files':rows,'declaredArchiveVerification':coverage},indent=2)+'\n')
    os.chmod(manifest,0o644);os.chown(manifest,uid,gid)
    if not coverage['ok']:raise ValueError('declared archive completeness failed; see collection.json')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('results','temporary','destination'):p.add_argument('--'+name,type=Path,required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--abc',action='store_true',help='explicit bounded ABC collection, including failures before identity setup')
    mode.add_argument('--verified-read-reuse',action='store_true',help='explicit bounded verified-read A/B collection, including early setup failure')
    mode.add_argument('--clean-sync-ttl',action='store_true',help='explicit bounded fixed clean-sync/TTL collection, including early setup failure')
    mode.add_argument('--latest-direct',action='store_true',help='explicit bounded latest-direct-v2 collection, including failures before identity setup')
    p.add_argument('--uid',type=int,required=True);p.add_argument('--gid',type=int,required=True);a=p.parse_args()
    if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true' or a.uid<=0 or a.gid<0:raise ValueError('authorized CI root copy to runner identity required')
    print(json.dumps({'copiedFiles':len(collect(a.results,a.temporary,a.destination,a.uid,a.gid,abc=a.abc,latest_direct=a.latest_direct,clean_sync_ttl=a.clean_sync_ttl,verified_read_reuse=a.verified_read_reuse))}))
