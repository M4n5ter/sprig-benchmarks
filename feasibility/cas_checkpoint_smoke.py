"""Same isolated runner mount boundary; semantic checks, never performance claims."""
import hashlib,json,os,pathlib,subprocess,tempfile,time,traceback
from cas_overlay_smoke import command,mounted

def main():
 assert os.environ.get('GITHUB_ACTIONS')=='true' and os.geteuid()==0
 root=pathlib.Path(tempfile.mkdtemp(prefix='sprig-cas-checkpoint-',dir=pathlib.Path(os.environ['RUNNER_TEMP']).resolve(strict=True)))
 binary=pathlib.Path('feasibility/cas-projection/target/release/sprig-cas-projection-prototype').resolve(strict=True)
 result=pathlib.Path('results');result.mkdir(exist_ok=True);source=root/'source';source.mkdir();lower=root/'lower';lower.mkdir();store=root/'store'
 original='one\ntwo\nthree\nfour\nfive\nsix\nseven\n';(source/'shared.txt').write_text(original)
 (source/'binary').write_bytes(hashlib.shake_256(b'checkpoint-immutable').digest(1024*1024));(source/'forged').write_bytes(b'0123456789')
 (source/'dir').mkdir();(source/'dir'/'nested').write_bytes(b'nested\n');(source/'opaque').mkdir();(source/'opaque'/'old').write_bytes(b'old\n');(source/'victim').write_bytes(b'victim\n');(source/'link').symlink_to('binary')
 ns=1700000000123456789
 for p in [source,*source.rglob('*')]:os.utime(p,ns=(ns,ns),follow_symlinks=False)
 report={'prototypeOnly':True,'performanceComparison':False,'ok':False,'checks':[],'captures':{},'publications':{}};fuse=None;views=[];failure=None
 def cli(action,*args):return json.loads(command(str(binary),action,'--root',str(store),*map(str,args)))
 def common(view,base):return ['--projection-base','manifest.json','--base',base,'--merged',view['view'],'--upper',view['upper'],'--lower',lower]
 def cap(label,view,base,identity=None):
  extra=['--identity-base',identity] if identity else []
  value=cli('capture',*common(view,base),'--output',label+'.json',*extra);report['captures'][label]=value
  oracle=cli('verify','--merged',view['view'],'--manifest',value['manifest']);assert oracle['event']=='full_capture_verified'
  return value
 def checkpoint(label,view,base,identity=None):
  value=cli('checkpoint',*common(view,base),*(['--identity-base',identity] if identity else []));report['publications'][label]=value;return value['publication']
 def read(revision,path):return bytes(cli('read','--base',revision,'--path',path)['bytes'])
 def newview(name):
  v={k:root/(name+'-'+k) for k in ['upper','work','view']}
  for p in v.values():p.mkdir()
  v['upper'].chmod(source.stat().st_mode&0o7777);os.utime(v['upper'],ns=(ns,ns));views.append(v)
  command('mount','-t','overlay','overlay','-o',f"lowerdir={lower},upperdir={v['upper']},workdir={v['work']},redirect_dir=on,index=off,nfs_export=off,metacopy=off",str(v['view']))
  return v
 try:
  report['import']=cli('import','--source',source);h0=cli('head');initial=(store/'manifest.json').read_bytes();report['initialHead']=h0
  logpath=result/'checkpoint-projection-lifecycle.jsonl'
  with logpath.open('w') as log:
   fuse=subprocess.Popen([str(binary),'mount','--root',str(store),'--mountpoint',str(lower)],stdout=log,stderr=log)
   for _ in range(150):
    if fuse.poll() is not None:raise RuntimeError('FUSE process exited before init')
    if mounted(lower) and 'fuse_initialized' in logpath.read_text():break
    time.sleep(.1)
   else:raise RuntimeError('FUSE initialization timed out')
   a,b=newview('a'),newview('b')
   for name,v in [('initial-a',a),('initial-b',b)]:
    stats=cap(name,v,h0['head'])['stats'];assert stats['lower_reuse_enabled'],stats['fallback_reason'];assert stats['bytes_reused']>0 and stats['bytes_hashed']==0
   av,bv=a['view'],b['view'];a_text=original.replace('one\n','A-one\n');(av/'shared.txt').write_text(a_text);(av/'added').write_bytes(b'added\n')
   origin=os.getxattr(lower/'forged','user.sprig.prototype.origin');(av/'forged').write_bytes(b'9876543210');os.utime(av/'forged',ns=(ns,ns));os.setxattr(av/'forged','user.sprig.prototype.origin',origin)
   (av/'dir').rename(av/'renamed');(av/'link').rename(av/'renamed-link');(av/'victim').unlink();(av/'opaque'/'old').unlink();(av/'opaque').rmdir();(av/'opaque').mkdir()
   assert os.readlink(av/'renamed-link')=='binary' and not (av/'link').exists() and not (av/'opaque'/'old').exists()
   changed=cap('changed-a',a,h0['head']);assert changed['stats']['bytes_hashed']>=10 and changed['stats']['bytes_reused']>0
   pa=checkpoint('a',a,h0['head']);assert pa['status']=='published';ha=pa['head']['head']
   same=cap('unchanged-a',a,ha);assert json.loads((store/same['manifest']).read_text())==next(r['manifest'] for r in cli('history') if r['id']==ha)
   noop=checkpoint('a-noop',a,ha);assert noop['status']=='noop' and noop['head']==pa['head']
   assert (store/'manifest.json').read_bytes()==initial and (lower/'shared.txt').read_text()==original and (lower/'forged').read_bytes()==b'0123456789'
   b_text=original.replace('seven\n','B-seven\n');(bv/'shared.txt').write_text(b_text);cap('changed-b',b,h0['head']);pb=checkpoint('b-merge',b,h0['head']);assert pb['status']=='published' and pb['merged']
   merged=a_text.replace('seven\n','B-seven\n');assert read(pb['head']['head'],'shared.txt')==merged.encode();assert read(pb['head']['head'],'added')==b'added\n';assert read(pb['head']['head'],'renamed/nested')==b'nested\n'
   assert (bv/'shared.txt').read_text()==b_text
   sdk=cli('write','--base',pb['head']['head'],'--path','sdk.txt','--text','sdk\n');report['publications']['sdk']=sdk;assert sdk['status']=='published'
   b2_text=b_text.replace('four\n','B-four\n');(bv/'shared.txt').write_text(b2_text);cap('changed-b-again',b,h0['head'],pb['candidate_manifest']);pb2=checkpoint('b-again',b,h0['head'],pb['candidate_manifest']);assert pb2['status']=='published' and pb2['merged']
   expected=merged.replace('four\n','B-four\n');assert read(pb2['head']['head'],'shared.txt')==expected.encode() and read(pb2['head']['head'],'sdk.txt')==b'sdk\n'
   before=cli('head');c=newview('c');conflicting=original.replace('one\n','C-one\n');(c['view']/'shared.txt').write_text(conflicting);cap('conflicting-c',c,h0['head']);pc=checkpoint('c-conflict',c,h0['head']);assert pc['status']=='conflict' and cli('head')==before
   assert read(pc['candidate'],'shared.txt')==conflicting.encode();assert (store/pc['conflict_file']).is_file() and pc['conflicts'];assert (c['view']/'shared.txt').read_text()==conflicting
   for name,args in [('stale-cas',['--base',before['head'],'--expected-head',h0['head'],'--expected-generation',str(h0['generation'])]),('orphan-base',['--base',pc['candidate']])]:
    attempt=subprocess.run([str(binary),'write','--root',str(store),*args,'--path','refused.txt','--text','refused'],capture_output=True,text=True);assert attempt.returncode!=0 and cli('head')==before;report[name]={'exitCode':attempt.returncode,'stderr':attempt.stderr}
   history=cli('history');report['history']=history;ids={r['id'] for r in history};assert {h0['head'],ha,pb['head']['head'],sdk['head']['head'],pb2['head']['head']}<=ids;assert sum(len(r['parents'])==2 for r in history)>=2
   assert read(h0['head'],'shared.txt')==original.encode() and read(ha,'shared.txt')==a_text.encode() and read(pb['candidate'],'shared.txt')==b_text.encode()
   final_manifest=next(r['manifest'] for r in history if r['id']==before['head']);assert 'victim' not in final_manifest and 'dir' not in final_manifest and 'link' not in final_manifest and 'renamed-link' in final_manifest and 'opaque/old' not in final_manifest
   with (av/'shared.txt').open('rb') as held:
    attempt=subprocess.run(['umount','-i',str(av)],capture_output=True,text=True);assert attempt.returncode!=0 and mounted(av);assert held.read()==a_text.encode()
   report['checks']=['Untouched views reuse lower bytes with zero content hashing','Independent full-capture oracle for all captured paths, contents, modes and mtimes','Forged origin plus same size/mtime does not skip upper hashing','Directory and symlink rename, whiteout, opaque and lower isolation','Checkpoint identity continuity and no-op','Two non-overlapping workspace merges and shared SDK-write publication','Retained conflict candidate, strict stale CAS and orphan-base refusal','Immutable historical reads and merge parents','Busy ordinary unmount refusal']
   for v in reversed(views):command('umount','-i',str(v['view']))
   command('umount','-i',str(lower));assert fuse.wait(timeout=10)==0;report['ok']=True
 except BaseException as e:
  failure=e;report['error']=traceback.format_exc()
  if isinstance(e,subprocess.CalledProcessError):report['commandOutput']=e.output
 finally:
  cleanup=[]
  for v in reversed(views):
   if mounted(v['view']):
    try:command('umount','-i',str(v['view']))
    except Exception as e:cleanup.append(str(e))
  if not any(mounted(v['view']) for v in views) and mounted(lower):
   try:command('umount','-i',str(lower))
   except Exception as e:cleanup.append(str(e))
  if fuse and not mounted(lower):
   try:fuse.wait(timeout=10)
   except Exception as e:cleanup.append(str(e))
  report['remainingMounts']={'views':[str(v['view']) for v in views if mounted(v['view'])],'lower':mounted(lower)}
  if cleanup:report['cleanupErrors']=cleanup
  if cleanup or report['remainingMounts']['views'] or report['remainingMounts']['lower']:report['ok']=False
  (result/'cas-checkpoint-smoke.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
 if failure:raise failure
 assert report['ok']
if __name__=='__main__':main()
