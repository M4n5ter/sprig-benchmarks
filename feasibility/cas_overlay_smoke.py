"""Runner-only synthetic RO FUSE / kernel OverlayFS semantics experiment."""
import errno,hashlib,json,mmap,os,pathlib,stat,subprocess,tempfile,time,traceback

def command(*args):return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT)
def mounted(path):return subprocess.run(['mountpoint','-q',str(path)],check=False).returncode==0

def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.geteuid()==0
    temp=pathlib.Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    root=pathlib.Path(tempfile.mkdtemp(prefix='sprig-cas-overlay-',dir=temp))
    binary=pathlib.Path('feasibility/cas-projection/target/release/sprig-cas-projection-prototype').resolve(strict=True)
    results=pathlib.Path('results');results.mkdir(exist_ok=True)
    source=root/'source';source.mkdir();lower=root/'lower';lower.mkdir();upper=root/'upper';upper.mkdir();work=root/'work';work.mkdir();merged=root/'merged';merged.mkdir();library=root/'library'
    original=hashlib.shake_256(b'cas-overlay-synthetic').digest(4*1024*1024)
    (source/'data').write_bytes(original);(source/'gone').write_bytes(b'old\n');(source/'directory').mkdir();(source/'directory'/'nested').write_bytes(b'nested\n');(source/'empty').mkdir();(source/'opaque').mkdir();(source/'opaque'/'old-child').write_bytes(b'hidden lower child\n');(source/'link').symlink_to('data');(source/'exec').write_text('#!/bin/sh\nprintf projection-ok');(source/'exec').chmod(0o755)
    for p in source.rglob('*'):
        if not p.is_symlink():os.utime(p,ns=(1700000000123456789,)*2)
    report={'prototypeOnly':True,'performanceComparison':False,'ok':False,'checks':[], 'root':str(root)}
    fuse=None;failure=None
    logpath=results/'projection-lifecycle.jsonl'
    try:
        report['import']=json.loads(command(str(binary),'import','--source',str(source),'--root',str(library)))
        with logpath.open('w') as log:
            fuse=subprocess.Popen([str(binary),'mount','--root',str(library),'--mountpoint',str(lower)],stdout=log,stderr=log)
            for _ in range(150):
                if fuse.poll() is not None:raise RuntimeError('FUSE process exited before initialization')
                if mounted(lower) and 'fuse_initialized' in logpath.read_text():break
                time.sleep(.1)
            else:raise RuntimeError('FUSE initialization timed out')
            assert (lower/'data').read_bytes()==original
            assert os.readlink(lower/'link')=='data'
            assert stat.S_IMODE((lower/'exec').stat().st_mode)==0o755
            assert (lower/'data').stat().st_mtime_ns==1700000000123456789
            for _ in range(3):assert sorted(p.name for p in lower.iterdir())==sorted(p.name for p in source.iterdir())
            report['checks'].append('FUSE bytes, symlink, mode, nanosecond mtime and repeated readdir')
            try:fd=os.open(lower/'data',os.O_WRONLY)
            except OSError as e:assert e.errno==errno.EROFS
            else:os.close(fd);raise AssertionError('Read-only mount accepted writable open')
            options=f'lowerdir={lower},upperdir={upper},workdir={work},redirect_dir=on,index=off,nfs_export=off,metacopy=off'
            command('mount','-t','overlay','overlay','-o',options,str(merged))
            report['mountInfo']=command('findmnt','-T',str(merged));assert (merged/'data').read_bytes()==original
            assert command(str(merged/'exec'))=='projection-ok'
            with (merged/'data').open('r+b') as f:
                f.seek(100);f.write(b'edit');f.flush()
                with mmap.mmap(f.fileno(),0) as mapping:mapping[200:204]=b'mmap';mapping.flush()
                f.truncate(len(original)//2);f.flush();os.fsync(f.fileno())
            expected=bytearray(original[:len(original)//2]);expected[100:104]=b'edit';expected[200:204]=b'mmap';assert (merged/'data').read_bytes()==expected
            assert (lower/'data').read_bytes()==original
            report['checks'].append('One write-open copy-up followed by write/mmap/truncate and lower isolation')
            (merged/'directory').rename(merged/'renamed');assert (merged/'renamed'/'nested').read_bytes()==b'nested\n';assert not (merged/'directory').exists()
            report['redirectXattr']=os.getxattr(upper/'renamed','trusted.overlay.redirect').decode();assert report['redirectXattr']
            (merged/'gone').unlink();assert not (merged/'gone').exists()
            whiteout=upper/'gone';info=whiteout.lstat();report['whiteoutCharacterDevice']=stat.S_ISCHR(info.st_mode) and info.st_rdev==0
            report['whiteoutXattrs']=os.listxattr(whiteout)
            assert report['whiteoutCharacterDevice'] or 'trusted.overlay.whiteout' in report['whiteoutXattrs']
            (merged/'gone').write_bytes(b'recreated\n');assert (merged/'gone').read_bytes()==b'recreated\n' and (lower/'gone').read_bytes()==b'old\n'
            (merged/'opaque'/'old-child').unlink();(merged/'opaque').rmdir();(merged/'opaque').mkdir()
            report['opaqueXattr']=os.getxattr(upper/'opaque','trusted.overlay.opaque').decode();assert report['opaqueXattr']=='y'
            assert not (merged/'opaque'/'old-child').exists() and (lower/'opaque'/'old-child').read_bytes()==b'hidden lower child\n'
            report['checks'].append('Lower-directory rename, redirect, whiteout, delete/recreate and opaque xattrs')
            with (merged/'data').open('rb') as held:
                attempted=subprocess.run(['umount','-i',str(merged)],capture_output=True,text=True)
                assert attempted.returncode!=0 and mounted(merged);assert held.read(4)==original[:4]
            report['checks'].append('Ordinary unmount refuses an open file descriptor')
            command('umount','-i',str(merged));assert not mounted(merged)
            assert (lower/'data').read_bytes()==original and (lower/'directory'/'nested').read_bytes()==b'nested\n'
            command('umount','-i',str(lower));assert not mounted(lower)
            assert fuse.wait(timeout=10)==0
            report['checks'].append('Normal ordered unmount and foreground FUSE shutdown')
            report['ok']=True
    except BaseException as e:failure=e;report['error']=traceback.format_exc()
    finally:
        cleanup=[]
        if mounted(merged):
            try:command('umount','-i',str(merged))
            except Exception as e:cleanup.append(str(e))
        if not mounted(merged) and mounted(lower):
            try:command('umount','-i',str(lower))
            except Exception as e:cleanup.append(str(e))
        if fuse and not mounted(lower):
            try:fuse.wait(timeout=10)
            except Exception as e:cleanup.append(str(e))
        # Never force/lazy unmount or kill a process serving a retained mount.
        if cleanup:report['cleanupErrors']=cleanup;report['ok']=False
        report['remainingMounts']={'overlay':mounted(merged),'fuse':mounted(lower)}
        if any(report['remainingMounts'].values()):report['ok']=False
        (results/'cas-overlay-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    if failure:raise failure
    assert report['ok']
if __name__=='__main__':main()
