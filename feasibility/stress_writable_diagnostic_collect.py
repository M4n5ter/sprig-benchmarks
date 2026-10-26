#!/usr/bin/env python3
"""Separate bounded diagnostic evidence inventory/copy; no primary allowlist changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from stress_cargo_collect import RESULTS as PRIMARY_RESULTS

CAP=1024**3
COLLECTION_RESERVE=2*1024**2
RESULTS=set(PRIMARY_RESULTS)|set('writable-diagnostic-identity.json writable-diagnostic-canary.json writable-diagnostic-summary.json diagnostic-source-hashes.txt diagnostic-binary-hash.txt diagnostic-release-build.log diagnostic-tests.txt diagnostic-source-ancestry.txt'.split())
RESULT_NAME=re.compile(r'(?:stress-writable-diagnostic-(?:off|on)-[01]|writable-diagnostic-audit-(?:off|on)-[01])\.json')
LOG_NAME=re.compile(r'[A-Za-z0-9_.-]+\.(?:stdout|stderr|log|jsonl)')


def candidates(results,temporary):
    for p in (results.parent,temporary):
        if p.resolve(strict=True)!=p:raise ValueError('canonical independent roots required')
    roots={'results':results,'capacity':temporary/'stress-cargo-capacity-pilot','records':temporary/'stress-writable-diagnostic-records'}
    rows=[]
    for group,root in roots.items():
        if not root.exists() and not root.is_symlink():continue
        if root.is_symlink() or not root.is_dir():raise ValueError('unsafe evidence root')
        if group=='results':files=[(p,Path(p.name)) for p in root.iterdir() if p.name in RESULTS or RESULT_NAME.fullmatch(p.name)]
        elif group=='capacity':files=[(root/n,Path(n)) for n in ('inc0.stdout','inc0.stderr','inc1.stdout','inc1.stderr') if (root/n).exists() or (root/n).is_symlink()]
        else:
            files=[];inc=root/'inc0'
            if not inc.exists() and not inc.is_symlink():continue
            if inc.is_symlink() or not inc.is_dir():raise ValueError('unsafe record directory')
            for arm,pair in [('off',0),('on',0),('on',1),('off',1)]:
                ledger=inc/f'{arm}-{pair}.jsonl'
                if ledger.exists() or ledger.is_symlink():files.append((ledger,Path('inc0')/ledger.name))
                logs=inc/f'{arm}-{pair}.jsonl.logs'
                if logs.exists() or logs.is_symlink():
                    if logs.is_symlink() or not logs.is_dir():raise ValueError('unsafe complete-log archive')
                    for p in logs.iterdir():
                        if not LOG_NAME.fullmatch(p.name):raise ValueError('unexpected archived diagnostic evidence name')
                        files.append((p,Path('inc0')/logs.name/p.name))
        for source,relative in sorted(files):
            info=source.lstat()
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink!=1:raise ValueError('independent regular evidence only')
            rows.append(dict(source=source,path=str(Path(group)/relative),bytes=info.st_size))
    if len({r['path'] for r in rows})!=len(rows):raise ValueError('duplicate evidence path')
    return rows


def inventory(results,temporary):
    rows=candidates(results,temporary);size=sum(r['bytes'] for r in rows)
    if size+COLLECTION_RESERVE>CAP:raise ValueError('complete evidence plus2MiB inventory reserve exceeds1GiB; preserve sources, never trim/filter')
    return dict(schema='sprig-writable-diagnostic-artifact-inventory-v1',files=len(rows),bytes=size,collectionReserveBytes=COLLECTION_RESERVE,admissionBytes=size+COLLECTION_RESERVE,maximumBytes=CAP,completeNamedInventory=True)


def verify_archives(destination,temporary,rows):
    by={r['path']:r for r in rows};errors=[];verified=set();sample_count=0
    for row in rows:
        if not re.fullmatch(r'results/stress-writable-diagnostic-(?:off|on)-[01]\.json',row['path']):continue
        sample_count+=1
        try:
            sample=json.loads((destination/row['path']).read_text());arm=sample.get('diagnosticArm');pair=int(Path(row['path']).stem[-1]);seen=set()
            if arm not in ('off','on'):raise ValueError('missing diagnostic sample arm')
            archive=sample.get('completeLogArchive',sample.get('partialLogArchive',[]))
            if sample.get('ok') is True and not archive:raise ValueError('successful sample has no complete archive')
            for entry in archive:
                path=Path(entry['archived']);expected=temporary/'stress-writable-diagnostic-records/inc0'/f'{arm}-{pair}.jsonl.logs'
                if path.parent!=expected or not LOG_NAME.fullmatch(path.name):raise ValueError('raw archive declaration escapes exact sample')
                key='records/inc0/'+expected.name+'/'+path.name
                if key in seen:raise ValueError('duplicate archive declaration')
                seen.add(key);actual=by.get(key)
                if actual is None or actual['bytes']!=entry.get('bytes') or actual['sha256']!=entry.get('sha256'):raise ValueError('missing/mismatched complete archive')
                verified.add(key)
        except (ValueError,KeyError,TypeError,AttributeError) as error:errors.append(dict(sample=row['path'],error=str(error)))
    return dict(ok=not errors,samples=sample_count,uniqueArchivesVerified=len(verified),errors=errors)


def collect(results,temporary,destination,uid,gid):
    rows=candidates(results,temporary);size=sum(r['bytes'] for r in rows)
    if size+COLLECTION_RESERVE>CAP:raise ValueError('complete evidence plus inventory reserve exceeds1GiB; all sources retained, no selected subset copied')
    if destination.exists() or destination.is_symlink() or destination.parent.resolve(strict=True)!=destination.parent or destination.is_relative_to(results) or destination.is_relative_to(temporary):raise ValueError('new independent artifact destination required')
    def directory(p):
        if not p.exists():p.mkdir();os.chmod(p,0o755);os.chown(p,uid,gid)
    directory(destination);copied=[]
    for row in rows:
        src=row['source'];target=destination/row['path'];p=destination
        for component in Path(row['path']).parts[:-1]:p=p/component;directory(p)
        fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);h=hashlib.sha256();size=0
        with os.fdopen(fd,'rb') as f,target.open('xb') as out:
            st=os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size!=row['bytes']:raise ValueError('source evidence changed during copy')
            for chunk in iter(lambda:f.read(1024*1024),b''):out.write(chunk);h.update(chunk);size+=len(chunk)
            os.fchmod(out.fileno(),0o644);os.fchown(out.fileno(),uid,gid)
        if size!=row['bytes']:raise ValueError('source evidence size changed')
        copied.append(dict(path=row['path'],bytes=size,sha256=h.hexdigest()))
    coverage=verify_archives(destination,temporary,copied)
    manifest=dict(schema='sprig-writable-diagnostic-artifact-copy-v1',files=copied,completeBytes=sum(r['bytes'] for r in copied),maximumBytes=CAP,declaredArchiveVerification=coverage)
    manifest_path=destination/'collection.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n');os.chmod(manifest_path,0o644);os.chown(manifest_path,uid,gid)
    # Include the collector's own complete inventory bytes in the1GiB bound.
    if manifest['completeBytes']+manifest_path.stat().st_size>CAP:raise ValueError('inventory itself exceeds complete artifact bound; no files dropped')
    if not coverage['ok']:raise ValueError('complete declared archive verification failed; retain collection.json')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['inventory','collect'])
    for name in ('results','temporary'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--destination',type=Path);p.add_argument('--uid',type=int);p.add_argument('--gid',type=int);a=p.parse_args()
    if a.command=='inventory':print(json.dumps(inventory(a.results,a.temporary)))
    else:
        if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true' or a.uid is None or a.uid<=0 or a.gid is None or a.gid<0 or a.destination is None:raise ValueError('authorized CI root copy to runner owner only')
        result=collect(a.results,a.temporary,a.destination,a.uid,a.gid);print(json.dumps({'files':len(result['files']),'bytes':result['completeBytes'],'complete':result['declaredArchiveVerification']['ok']}))
