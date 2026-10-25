#!/usr/bin/env python3
"""Copy only named benchmark evidence; never traverse runtime roots or change sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

RESULTS = set('cargo-toolchain-capacity.txt cargo-image-capacity.txt cargo-image-build.txt cargo-image.json cargo-software-identity.txt current-writable-contract.json docker-updated.txt environment.txt production-binary-hash.txt production-kernel-contract.json production-source-hashes.txt projection-rust-version.txt runtime-image.json script-hashes.txt stress-cargo-capacity-status.json stress-cargo-capacity.json stress-cargo-generated.json stress-cargo-lock-generation.txt stress-cargo-manifest.json stress-cargo-oracle.json'.split())
PRODUCT = r'(?:sprig-writable|layerfs)'

def allowed(group, parts):
    if group == 'results':
        return len(parts)==1 and (parts[0] in RESULTS or re.fullmatch(r'stress-cargo-(?:comparison-[01]|'+PRODUCT+r'-inc[01]-[0-2])\.json', parts[0]))
    if group == 'capacity':
        return len(parts)==1 and re.fullmatch(r'inc[01]\.(?:stdout|stderr)', parts[0])
    if group == 'records' and len(parts) in (2,3) and re.fullmatch(r'inc[01]',parts[0]):
        if len(parts)==2:
            return re.fullmatch(PRODUCT+r'-[0-2](?:\.jsonl|-options\.json)',parts[1])
        return re.fullmatch(PRODUCT+r'-[0-2]\.jsonl\.logs',parts[1]) and re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:stdout|stderr|log)',parts[2])
    return False


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
                    if re.fullmatch(PRODUCT+r'-[0-2]\.jsonl\.logs',p.name):
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
    manifest=destination/'collection.json'
    manifest.write_text(json.dumps({'schema':'sprig-cargo-artifact-copy-v1','files':rows},indent=2)+'\n')
    os.chmod(manifest,0o644);os.chown(manifest,uid,gid)
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('results','temporary','destination'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--uid',type=int,required=True);p.add_argument('--gid',type=int,required=True);a=p.parse_args()
    if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true' or a.uid<=0 or a.gid<0:raise ValueError('authorized CI root copy to runner identity required')
    print(json.dumps({'copiedFiles':len(collect(a.results,a.temporary,a.destination,a.uid,a.gid))}))
