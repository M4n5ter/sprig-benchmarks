#!/usr/bin/env python3
"""Frozen upstream seed-1 recipe port, not a new synthetic workload distribution.
Source d296981ace76fe751bebf00dee52818fe18a3eef:
benchmark/fs-bench-pro/workload/{dedup_workloads,sdk_edit_common}.rs
families/{dedup_cross_file,dedup_cdc_locality}/mod.rs
Current v1.0.0 family.json pins those original sources. MIT upstream.
"""
import hashlib,json,os,struct,sys
from pathlib import Path
M=2**64-1

def digest(family,profile,ordinal,role):
    h=hashlib.sha256()
    for s in ('dedup-input-v1',family,profile,'layerfs-v0.1.3-seed-1'):
        b=s.encode();h.update(struct.pack('<Q',len(b)));h.update(b)
    h.update(struct.pack('<Q',ordinal));b=role.encode();h.update(struct.pack('<Q',len(b)));h.update(b)
    return h.digest()

def content(family,profile,ordinal,role,n):
    state=int.from_bytes(digest(family,profile,ordinal,role)[:8],'little');out=bytearray()
    while len(out)<n:
        state=(state+0x9e3779b97f4a7c15)&M;z=state
        z=((z^(z>>30))*0xbf58476d1ce4e5b9)&M;z=((z^(z>>27))*0x94d049bb133111eb)&M
        out.extend(struct.pack('<Q',z^(z>>31)))
    return bytes(out[:n])

def make(root,case,count):
    root.mkdir(parents=True)
    if case in ('identical','unique','mixed'):
        family='dedup_cross_file';cache={}
        for i in range(count):
            base=0 if case=='identical' else i if case=='unique' else 3*(i//4)+max(0,i%4-1)
            if base not in cache:cache[base]=content(family,'base',base,'bytes',1048576)
            p=root/'files'/f'f{i:04}.dat';p.parent.mkdir(exist_ok=True);p.write_bytes(cache[base])
    elif case=='insert':
        family='dedup_cdc_locality';base=content(family,case,0,'reference',1048576)
        (root/'reference.dat').write_bytes(base);(root/'variants').mkdir()
        for i in range(count):
            at=65536+int.from_bytes(digest(family,case,i,'offset')[:8],'little')%917505
            (root/'variants'/f'v{i:04}.dat').write_bytes(base[:at]+content(family,case,i,'insertion',4096)+base[at:])
    elif case.startswith('history-'):
        from history_recipe import history_genesis,history_edit
        import base64
        genesis=history_genesis();current=genesis.copy();steps=[]
        for name,data in genesis.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        (root/'dest').mkdir()
        profile=case.removeprefix('history-')
        for k in range(100):
            name,offset,length,data=history_edit(profile,k,genesis)
            current[name]=current[name][:offset]+data+current[name][offset+length:]
            steps.append({'step':k+1,'path':name,'offset':offset,'data':base64.b64encode(data).decode(),'sha256':hashlib.sha256(current[name]).hexdigest()})
        (root.parent/(case+'-steps.json')).write_text(json.dumps(steps))
        (root.parent/(case+'-final.json')).write_text(json.dumps([{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(current.items())]))
    else: raise ValueError(case)
    manifest=[]
    for p in sorted(root.rglob('*')):
        os.chmod(p,0o750 if p.is_dir() else 0o640);os.utime(p,(1700000000,1700000000))
        if p.is_file():manifest.append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    os.chmod(root,0o750);os.utime(root,(1700000000,1700000000))
    return manifest
if __name__=='__main__':
    out=Path(sys.argv[1]);count=int(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    for case in ('identical','unique','mixed','insert','history-distributed','history-hotset','history-recurring'):
        manifest=make(out/case,case,count);(out/(case+'.json')).write_text(json.dumps(manifest,indent=2))
        print(case,len(manifest),sum(x['bytes'] for x in manifest),hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),flush=True)
