"""Runner-only, single-daemon storage relocation; no networking/security changes."""
import argparse, hashlib, json, os, pathlib, re, stat, subprocess, tempfile, time, tomllib, sys
DOCKER=pathlib.Path('/etc/docker/daemon.json');CONTAINERD=pathlib.Path('/etc/containerd/config.toml')
def cmd(*args):return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT)
def digest(data):return hashlib.sha256(data).hexdigest()
def atomic(path,data,mode):
    fd,name=tempfile.mkstemp(prefix=path.name+'.sprig-benchmark-',dir=path.parent);tmp=pathlib.Path(name)
    os.fchmod(fd,mode)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def wait_docker():
    for _ in range(60):
        try:cmd('docker','info');return
        except subprocess.CalledProcessError:time.sleep(1)
    raise RuntimeError('Docker did not become ready')
def stop():cmd('systemctl','stop','docker.service','docker.socket','containerd.service')
def start():
    try:
        cmd('systemctl','start','containerd.service')
        cmd('systemctl','start','docker.socket')
        cmd('systemctl','start','docker.service');wait_docker()
    except (subprocess.CalledProcessError,RuntimeError) as error:
        print(getattr(error,"output",str(error)),file=sys.stderr)
        # Only runtime service diagnostics, never product records/config contents.
        print(cmd('journalctl','-u','docker.service','-u','containerd.service','-n','30','--no-pager'),file=sys.stderr)
        raise
def require_empty():
    if cmd('docker','ps','-aq').strip():raise RuntimeError('Refusing runtime relocation with any existing container')
def restore(state_path):
    state=json.loads(state_path.read_text())
    if state.get('restored'):return
    if state.get('configurationRestored'):
        for item in state['files']:
            path=pathlib.Path(item['path'])
            assert (digest(path.read_bytes())==item['original_sha256']) if item['existed'] else not path.exists()
        start();state['restored']=True;state_path.write_text(json.dumps(state));return
    # Refuse to overwrite unrelated changes, including after a daemon outage.
    for item in state['files']:
        path=pathlib.Path(item['path'])
        assert path.exists() and digest(path.read_bytes())==item['installed_sha256']
    try:require_empty()
    except subprocess.CalledProcessError:pass
    stop()
    for item in state['files']:
        path=pathlib.Path(item['path'])
        if item['existed']:atomic(path,pathlib.Path(item['backup']).read_bytes(),item['mode'])
        elif path.exists():
            assert digest(path.read_bytes())==item['installed_sha256']
            path.unlink()
    state['configurationRestored']=True;state_path.write_text(json.dumps(state))
    start();state['restored']=True;state_path.write_text(json.dumps(state))
def relocate(mount,state_path,archive,image):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.geteuid()==0
    mount=mount.resolve(strict=True);temporary=pathlib.Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    assert mount.is_relative_to(temporary) and cmd('stat','-f','-c','%T',str(mount)).strip()=='btrfs'
    assert not state_path.exists();require_empty()
    # These services must use their standard configuration files, not override
    # storage roots on a command line. Existing socket/network/TLS flags remain.
    docker_exec=cmd('systemctl','show','docker.service','--property=ExecStart','--value')
    containerd_exec=cmd('systemctl','show','containerd.service','--property=ExecStart','--value')
    assert not any(k in docker_exec for k in ['--data-root','--storage-driver','--config-file'])
    assert not any(k in containerd_exec for k in ['--root','--config'])
    assert not re.search(r'(?:^|\s)-(?:c|r)(?:\s|=)',containerd_exec)
    old_docker=DOCKER.read_bytes() if DOCKER.exists() else b'{}'
    old_containerd=CONTAINERD.read_bytes() if CONTAINERD.exists() else b''
    d=json.loads(old_docker);new=json.loads(old_docker)
    assert isinstance(new,dict) and isinstance(new.get('features',{}),dict)
    new['data-root']=str(mount/'docker-data');new['storage-driver']='overlay2'
    new.setdefault('features',{})['containerd-snapshotter']=False
    docker_bytes=(json.dumps(new,indent=2)+'\n').encode()
    c=tomllib.loads(old_containerd.decode());assert not c.get('imports'), 'Imported configuration needs separate review'
    text=old_containerd.decode();header=re.search(r'^\s*\[',text,re.M)
    at=header.start() if header else len(text);prefix,suffix=text[:at],text[at:];sep=''
    if re.search(r'^\s*root\s*=',prefix,re.M):prefix=re.sub(r'^\s*root\s*=.*$', 'root = '+json.dumps(str(mount/'containerd-data')),prefix,flags=re.M)
    else:prefix='root = '+json.dumps(str(mount/'containerd-data'))+'\n'+prefix
    containerd_bytes=(prefix+sep+suffix).encode();new_c=tomllib.loads(containerd_bytes.decode())
    assert {k:v for k,v in new_c.items() if k!='root'}=={k:v for k,v in c.items() if k!='root'}
    # Verify the exact allowed Docker semantic diff, not only the written keys.
    check=json.loads(docker_bytes);check.pop('data-root',None);check.pop('storage-driver',None)
    prior=json.loads(old_docker);prior.pop('data-root',None);prior.pop('storage-driver',None)
    for x in [check,prior]:
        if 'features' in x:
            x['features'].pop('containerd-snapshotter',None)
            if not x['features']:x.pop('features')
    assert check==prior
    files=[]
    for path,data in [(DOCKER,docker_bytes),(CONTAINERD,containerd_bytes)]:
        assert not path.is_symlink()
        existed=path.exists();mode=stat.S_IMODE(path.stat().st_mode) if existed else 0o600
        backup=state_path.parent/(path.name+'.original')
        if existed:
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(path.read_bytes())
        files.append(dict(path=str(path),backup=str(backup),existed=existed,mode=mode,original_sha256=digest(path.read_bytes()) if existed else None,installed_sha256=digest(data)))
    state_path.write_text(json.dumps({'files':files,'restored':False}));os.chmod(state_path,0o600)
    try:
        stop()
        atomic(DOCKER,docker_bytes,files[0]['mode']);atomic(CONTAINERD,containerd_bytes,files[1]['mode'])
        start()
        info=json.loads(cmd('docker','info','--format','{{json .}}'))
        assert info['Driver']=='overlay2' and pathlib.Path(info['DockerRootDir']).resolve()==mount/'docker-data'
        effective=tomllib.loads(subprocess.check_output(['containerd','config','dump'],text=True))
        assert effective['root']==str(mount/'containerd-data')
        cmd('docker','load','-i',str(archive))
        assert cmd('docker','image','inspect','--format','{{.Id}}',image).strip()==image
        return {'dockerRoot':info['DockerRootDir'],'driver':info['Driver'],'driverStatus':info.get('DriverStatus'),'containerdRoot':effective['root'],'image':image}
    except BaseException:
        # Restore only configuration, never delete old data directories.
        # Failed daemon startup may prevent docker ps; services are stopped first.
        stop()
        for item in files:
            path=pathlib.Path(item['path'])
            if item['existed']:atomic(path,pathlib.Path(item['backup']).read_bytes(),item['mode'])
            elif path.exists() and digest(path.read_bytes())==item['installed_sha256']:path.unlink()
        state=json.loads(state_path.read_text());state['configurationRestored']=True;state_path.write_text(json.dumps(state))
        start();state['restored']=True;state_path.write_text(json.dumps(state));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['enter','leave']);p.add_argument('--state',required=True);p.add_argument('--mount');p.add_argument('--archive');p.add_argument('--image');a=p.parse_args()
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.geteuid()==0
    state=pathlib.Path(a.state)
    if a.action=='leave':restore(state);print('{"restored":true}')
    else:print(json.dumps(relocate(pathlib.Path(a.mount),state,pathlib.Path(a.archive),a.image)))
