#!/usr/bin/env python3
"""External common-image setup pilot; never a product measurement/cache input.
No runtime relocation, image build/pull, added privileges, or forced cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from stress_cargo_prepare import PROTOCOL,PROTOCOL_SHA,validate_manifest
from stress_cargo_sample import build_observation
from cargo_sample import ENVIRONMENT,PREFIX,fixture_inventory


def pilot_script():
    # Fixed scripts come from a versioned local protocol, not untrusted argv.
    commands=PROTOCOL['commands']
    sequence=[('clean_build',commands['build']),('target_probe',commands['probe']),
              ('clean_artifacts',commands['verifyBefore']),('clean_execute',commands['program']),
              ('noop_build',commands['build']),('edit',commands['edit']),('edit_build',commands['build']),
              ('edit_artifacts',commands['verifyAfter']),('edit_execute',commands['program']),
              ('noop_after_edit',commands['build'])]
    code='''import json,os,subprocess
from pathlib import Path
for name in ('.cargo-home','.tmp'):
    assert not Path(name).exists();Path(name).mkdir()
rows=[]
for purpose,script in SEQUENCE:
    result=subprocess.run(['/bin/bash','-c',PREFIX+script],text=True,capture_output=True)
    rows.append(dict(purpose=purpose,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    if result.returncode:
        print(json.dumps({'ok':False,'commands':rows}));raise SystemExit(result.returncode)
software=subprocess.check_output(['/bin/bash','-c','rustc -Vv; cargo -V'],text=True)
allocated=int(subprocess.check_output(['du','-sB1','target'],text=True).split()[0])
logical=int(subprocess.check_output(['du','-sb','target'],text=True).split()[0])
print(json.dumps({'ok':True,'software':software,'targetAllocatedBytes':allocated,'targetLogicalBytes':logical,'commands':rows}))
'''.replace('SEQUENCE',repr(sequence)).replace('PREFIX',repr(PREFIX))
    return 'python3 -B - <<\'SPRIG_CAPACITY_PY\'\n'+code+'\nSPRIG_CAPACITY_PY'


def validate_pilot(row,manifest):
    if row.get('ok') is not True or not re.search(r'^rustc 1\.90\.0 ',row.get('software',''),re.M) or not re.search(r'^cargo 1\.90\.0 ',row.get('software',''),re.M):
        raise ValueError('capacity pilot must use actual pinned Rust/Cargo1.90.0')
    if not isinstance(row.get('targetAllocatedBytes'),int) or row['targetAllocatedBytes']<=0:
        raise ValueError('target allocation must be measured positive integer')
    by={c['purpose']:c for c in row['commands']}
    if len(by)!=len(row['commands']) or any(c.get('returncode')!=0 for c in row['commands']):
        raise ValueError('duplicate or failed pilot command')
    for purpose in ('clean_build','noop_build','edit_build','noop_after_edit'):
        c=by[purpose]
        if c['returncode']!=0:raise ValueError('pilot build failed')
        c['packageAcceptance']=build_observation(c['stderr'],'noop_build' if purpose=='noop_after_edit' else purpose)
    for purpose,key in [('clean_execute','expectedStdoutBefore'),('edit_execute','expectedStdoutAfter')]:
        if by[purpose]['stdout']!=manifest[key]:raise ValueError('pilot executable value mismatch')
    for purpose,value in [('clean_artifacts',1),('edit_artifacts',2)]:
        data=json.loads(by[purpose]['stdout'])
        if data.get('ok') is not True or data.get('buildValue')!=value or data.get('hardlinkProbe') is not True or data.get('exactMtime') is not True or not data.get('generatedFiles'):
            raise ValueError('pilot artifact validation failed')
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','manifest','output','root'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--image',required=True);a=p.parse_args()
    if os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('authorized root CI setup only')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',a.image):raise ValueError('immutable local image required')
    for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','DOCKER_TLS'):
        if os.environ.get(key):raise ValueError('unexpected Docker route setting '+key)
    temporary=Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    if not a.root.is_absolute() or a.root.exists() or not a.root.is_relative_to(temporary) or a.root==temporary:
        raise ValueError('new private pilot root below RUNNER_TEMP required')
    if a.root.parent.resolve(strict=True)!=a.root.parent or any(c in str(a.root) for c in ',\n\r'):
        raise ValueError('pilot root must have exact nonsymlink parent and safe bind path')
    if a.output.exists():raise ValueError('refuse overwrite of existing capacity evidence')
    if any(c in str(a.source) for c in ',\n\r'):raise ValueError('unsafe source bind path')
    if not a.source.is_absolute() or a.source.resolve(strict=True)!=a.source:raise ValueError('exact absolute fixture source required')
    manifest_raw=a.manifest.read_bytes();manifest=validate_manifest(json.loads(manifest_raw))
    fixture_inventory(a.source,manifest['initial'])
    image=json.loads(subprocess.check_output(['docker','image','inspect',a.image],text=True))
    if len(image)!=1 or image[0]['Id']!=a.image:raise ValueError('image identity mismatch')
    if image[0].get('Config',{}).get('User','') not in ('','0','root','0:0','root:root'):raise ValueError('compiler image must use ordinary default root')
    if shutil.disk_usage(a.root.parent).free<512*1024**2:raise ValueError('capacity_blocked: insufficient external setup disk')
    a.root.mkdir(mode=0o700)
    report={'schema':'sprig-stress-cargo-capacity-v1','image':a.image,'protocolSha256':PROTOCOL_SHA,
            'fixtureManifestSha256':hashlib.sha256(manifest_raw).hexdigest(),
            'toolchain':{'rustc':'1.90.0','cargo':'1.90.0'},'pilots':[],
            'scope':'external symmetric setup only; no pilot source/target/cache imported or reused by either product',
            'retainedPilotRoot':str(a.root)}
    for incremental in (0,1):
        tree=a.root/f'incremental-{incremental}';shutil.copytree(a.source,tree,copy_function=shutil.copy2)
        name='sprig-capacity-'+uuid.uuid4().hex
        args=['docker','run','--rm','--pull=never','--name',name,'--label','sprig.cargo.capacity='+name,
              '--mount',f'type=bind,source={tree},target=/work','--workdir','/work','--entrypoint','/bin/bash']
        for k,v in {**ENVIRONMENT,'CARGO_INCREMENTAL':str(incremental)}.items():args+=['--env',k+'='+v]
        args += [a.image,'-c',PREFIX+pilot_script()]
        proc=subprocess.run(args,text=True,capture_output=True)
        (a.root/f'inc{incremental}.stdout').write_text(proc.stdout);(a.root/f'inc{incremental}.stderr').write_text(proc.stderr)
        # Read-only inventory; a failure/uncertain command is never replayed or killed.
        inventory=subprocess.check_output(['docker','ps','-aq','--filter','label=sprig.cargo.capacity='+name],text=True).strip()
        if proc.returncode or inventory:raise RuntimeError('capacity pilot failed/uncertain; preserve evidence and container, no retry')
        row=validate_pilot(json.loads(proc.stdout),manifest);row['incremental']=incremental
        report['pilots'].append(row)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'ok':True,'capacityFile':str(a.output),'pilots':[{k:r[k] for k in ('incremental','targetAllocatedBytes','targetLogicalBytes')} for r in report['pilots']]}))

if __name__=='__main__':main()
