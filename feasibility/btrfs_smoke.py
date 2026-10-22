"""Capability/accounting smoke only; not a product performance result."""
import atexit, fcntl, hashlib, json, os, pathlib, re, struct, subprocess, sys
root=pathlib.Path(sys.argv[1]).resolve(); out=pathlib.Path(sys.argv[2]).resolve()
def cmd(*args): return subprocess.check_output(args,text=True)
def stats():
    cmd('btrfs','filesystem','sync',str(root))
    usage=cmd('btrfs','filesystem','usage','-b',str(root))
    groups=cmd('btrfs','filesystem','df','-b',str(root))
    du=cmd('btrfs','filesystem','du','-s','--raw',str(root))
    used=int(re.search(r'^\s*Used:\s*(\d+)\s*$',usage,re.M).group(1))
    data_used=int(re.search(r'^Data, single: total=\d+, used=(\d+)$',groups,re.M).group(1))
    total,exclusive,shared=map(int,re.search(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+',du,re.M).groups())
    return dict(usedBytes=used,dataUsedBytes=data_used,referencedBytes=total,fileExtentUnionBytes=exclusive+shared,usageRaw=usage,groupsRaw=groups,extentSetRaw=du)
assert cmd('stat','-f','-c','%T',str(root)).strip()=='btrfs'
report={'kind':'capability-smoke-not-performance','passed':False,'empty':stats()}
atexit.register(lambda:out.write_text(json.dumps(report,indent=2)+'\n'))
cmd('btrfs','subvolume','create',str(root/'base'))
data=hashlib.shake_256(b'isolated-btrfs-smoke-v1').digest(4*1024*1024)
p=root/'base/data'
with p.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
cmd('btrfs','subvolume','snapshot','-r',str(root/'base'),str(root/'snapshot'))
cmd('cp','--reflink=always',str(p),str(root/'clone'))
with (root/'independent').open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
report['beforeDedup']=stats()
with p.open('rb') as source,(root/'independent').open('r+b') as target:
    buf=bytearray(struct.pack('=QQHHI',0,len(data),1,0,0)+struct.pack('=qQQiI',target.fileno(),0,0,0,0))
    fcntl.ioctl(source.fileno(),0xc0189436,buf,True)
    _,_,deduped,status,_=struct.unpack_from('=qQQiI',buf,24)
    assert status==0 and deduped==len(data),(status,deduped)
report['dedupedBytes']=deduped;report['afterDedup']=stats()
with p.open('r+b') as f:f.write(b'CHANGED!');f.flush();os.fsync(f.fileno())
for name in ['snapshot/data','clone','independent']:assert (root/name).read_bytes()==data
assert p.read_bytes()==b'CHANGED!'+data[8:]
report['copyOnWriteIsolation']=True;report['afterEdit']=stats()
assert report['beforeDedup']['dataUsedBytes']==2*len(data)
assert report['afterDedup']['dataUsedBytes']==len(data)
for stage in ['beforeDedup','afterDedup']:
    assert report[stage]['fileExtentUnionBytes']==report[stage]['dataUsedBytes']
# Unique data falls by one independent 4 MiB copy; tolerate metadata tree changes.
assert report['beforeDedup']['usedBytes']-report['afterDedup']['usedBytes']>3*1024*1024
report['passed']=True
out.write_text(json.dumps(report,indent=2)+'\n')
