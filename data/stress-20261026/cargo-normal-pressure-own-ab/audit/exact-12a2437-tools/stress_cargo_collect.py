#!/usr/bin/env python3
"""Copy only named benchmark evidence; never traverse runtime roots or change sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from stress_cargo_pressure import SPEC as PRESSURE_SPEC, pressure_identity

RESULTS = set('cargo-toolchain-capacity.txt cargo-image-capacity.txt cargo-image-build.txt cargo-image.json cargo-software-identity.txt current-writable-contract.json docker-updated.txt environment.txt production-binary-hash.txt production-kernel-contract.json production-source-hashes.txt projection-rust-version.txt runtime-image.json script-hashes.txt stress-cargo-capacity-status.json stress-cargo-capacity.json stress-cargo-generated.json stress-cargo-lock-generation.txt stress-cargo-manifest.json stress-cargo-oracle.json'.split())
RESULTS.update('stress-cargo-own-ab-summary.json stress-cargo-ab-products.json baseline-source-hashes.txt candidate-source-hashes.txt baseline-binary-hash.txt candidate-binary-hash.txt baseline-release-build.log candidate-release-build.log baseline-tests.txt candidate-tests.txt baseline-projection-gate.json candidate-projection-gate.json baseline-writable-gate.json candidate-writable-gate.json'.split())
COMPARATOR_PRODUCTS = ('sprig-writable', 'layerfs')
OWN_AB_PRODUCTS = ('sprig-baseline', 'sprig-candidate')
PRODUCT = r'(?:' + '|'.join(COMPARATOR_PRODUCTS + OWN_AB_PRODUCTS) + ')'
COMPARATOR = r'(?:' + '|'.join(COMPARATOR_PRODUCTS) + ')'
OWN_AB = r'(?:' + '|'.join(OWN_AB_PRODUCTS) + ')'
ROUND_PRODUCT = r'(?:' + COMPARATOR + r'-[0-2]|' + OWN_AB + r'-[0-3])'
SAMPLE_NAME = r'(?:' + COMPARATOR + r'-inc[01]-[0-2]|' + OWN_AB + r'-inc[01]-[0-3])'
ORDINARY_EXPERIMENT = dict(schema='sprig-cargo-experiment-v1',profile='ordinary',roundsPerMode=4,incrementalModes=[0,1],order='alternating-pairs-mode-offset',pressure=None)

def allowed(group, parts):
    if group == 'results':
        return len(parts)==1 and (parts[0] in RESULTS or re.fullmatch(r'stress-cargo-(?:(?:comparison|own-ab)-[01]|'+SAMPLE_NAME+r')\.json', parts[0]))
    if group == 'capacity':
        return len(parts)==1 and re.fullmatch(r'inc[01]\.(?:stdout|stderr)', parts[0])
    if group == 'records' and len(parts) in (2,3) and re.fullmatch(r'inc[01]',parts[0]):
        if len(parts)==2:
            return re.fullmatch(ROUND_PRODUCT+r'(?:\.jsonl|-options\.json)',parts[1])
        return re.fullmatch(ROUND_PRODUCT+r'\.jsonl\.logs',parts[1]) and re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:stdout|stderr|log|jsonl)',parts[2])
    return False


def verify_declared_archives(destination, temporary, copied):
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
            if path.parent!=expected or not allowed('records',parts):
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
        match=re.fullmatch(r'stress-cargo-('+PRODUCT+r')-inc([01])-([0-3])\.json',name)
        comparison=re.fullmatch(r'stress-cargo-(comparison|own-ab)-([01])\.json',name)
        if not match and not comparison:continue
        try:report=json.loads((destination/row['path']).read_text())
        except (ValueError,UnicodeError):errors.append('invalid report JSON: '+row['path']);continue
        if not isinstance(report,dict):errors.append('invalid report object');continue
        if match:verify(report,match[1],match[2],match[3])
        else:
            own_ab = comparison[1]=='own-ab'
            if own_ab and (report.get('schema') not in ('sprig-stress-cargo-own-ab-v1','sprig-stress-cargo-own-ab-v2') or type(report.get('incremental')) is not int or report['incremental']!=int(comparison[2])):
                errors.append('invalid own-AB report schema/incremental identity');continue
            repeated=own_ab and report.get('schema')=='sprig-stress-cargo-own-ab-v2'
            expected_experiment=ORDINARY_EXPERIMENT
            if isinstance(report.get('experimentSpec'),dict) and report['experimentSpec'].get('profile')==PRESSURE_SPEC['profile']:
                expected_experiment={**ORDINARY_EXPERIMENT,'profile':PRESSURE_SPEC['profile'],'pressure':pressure_identity()}
            if repeated and (report.get('rounds')!=4 or type(report.get('rounds')) is not int or report.get('experimentSpec')!=expected_experiment):
                errors.append('invalid repeated own-AB experiment identity');continue
            records=report.get('records',[])
            if not isinstance(records,list):errors.append('invalid comparison records');continue
            for record in records:
                if not isinstance(record,dict):errors.append('invalid comparison record');continue
                if 'sample' not in record:continue # runtime setup can fail before sampler
                products = OWN_AB_PRODUCTS if comparison[1]=='own-ab' else COMPARATOR_PRODUCTS
                if record.get('product') not in products or type(record.get('round')) is not int or record['round'] not in (range(4) if repeated else range(1) if own_ab else range(3)):
                    errors.append('invalid comparison sample identity');continue
                verify(record['sample'],record['product'],comparison[2],record['round'])
    return {'ok':not errors,'sampleDeclarations':samples,'verifiedUniqueFiles':len(verified),'errors':errors}


def collect(results, temporary, destination, uid, gid):
    for parent in (results.parent, temporary, destination.parent):
        if parent.resolve(strict=True)!=parent:raise ValueError('exact nonsymlink parents required')
    if destination.exists() or destination.is_symlink():raise ValueError('new artifact destination required')
    if destination.is_relative_to(results) or destination.is_relative_to(temporary):
        raise ValueError('artifact destination must be separate from evidence input roots')
    def mkdir(path):
        if not path.exists():
            path.mkdir(mode=0o755);os.chmod(path,0o755);os.chown(path,uid,gid)
    mkdir(destination)
    rows=[]
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
                    if re.fullmatch(ROUND_PRODUCT+r'\.jsonl\.logs',p.name):
                        if p.is_symlink() or not p.is_dir():raise ValueError('unsafe log directory')
                        candidates.extend((f,(inc,p.name,f.name)) for f in p.iterdir())
        for source,parts in sorted(candidates):
            if not allowed(group,parts):continue
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
    coverage=verify_declared_archives(destination,temporary,rows)
    manifest=destination/'collection.json'
    manifest.write_text(json.dumps({'schema':'sprig-cargo-artifact-copy-v1','files':rows,'declaredArchiveVerification':coverage},indent=2)+'\n')
    os.chmod(manifest,0o644);os.chown(manifest,uid,gid)
    if not coverage['ok']:raise ValueError('declared archive completeness failed; see collection.json')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('results','temporary','destination'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--uid',type=int,required=True);p.add_argument('--gid',type=int,required=True);a=p.parse_args()
    if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true' or a.uid<=0 or a.gid<0:raise ValueError('authorized CI root copy to runner identity required')
    print(json.dumps({'copiedFiles':len(collect(a.results,a.temporary,a.destination,a.uid,a.gid))}))
