# Frozen seed-1 dedup_branch_history recipe port. Upstream MIT; see LICENSE.upstream.
# Source d296981ace76fe751bebf00dee52818fe18a3eef, workload/dedup_workloads.rs
# and workload/workspace_common.rs under benchmark/fs-bench-pro.
import hashlib, struct
from fixtures import content, M
def splitmix(seed,n):
    state=seed;out=bytearray()
    while len(out)<n:
        state=(state+0x9e3779b97f4a7c15)&M;z=state
        z=((z^(z>>30))*0xbf58476d1ce4e5b9)&M
        z=((z^(z>>27))*0x94d049bb133111eb)&M
        out.extend(struct.pack('<Q',z^(z>>31)))
    return bytes(out[:n])

def framed(s):
    b=s.encode();return struct.pack('<Q',len(b))+b

def history_path(j):
    if j<64:return f'wide/s000-f{j:03}.dat'
    if j<199:return f'regular/s000/f{j:03}.dat'
    return 'spine/'+'/'.join(f'd{i:03}' for i in range(1,129))+'/s000.dat'

def history_genesis():
    # 200 regular files; callers must create parents, root and empty dest/.
    files={}
    for j in range(200):
        h=hashlib.sha256(framed('workspace-shards-v1')+framed('layerfs-v0.1.3-seed-1')+struct.pack('<QQ',0,j)).digest()
        n=1024 if j<128 else 8192 if j<192 else 49152
        files[history_path(j)]=splitmix(int.from_bytes(h[:8],'little'),n)
    return files

def history_rank(profile):
    ids=range(192,200) if profile=='hotset' else range(200)
    prefix=framed('layerfs-v0.1.3-seed-1')+framed('dedup-history-'+profile)
    return [j for _,j in sorted((hashlib.sha256(prefix+struct.pack('<Q',j)).digest(),j) for j in ids)]

def history_edit(profile,step,genesis):
    # step zero-based; exactly one ordinary positional replacement per commit.
    if profile=='recurring':
        p=history_path(192)
        return p,0,49152,(genesis[p] if step%2 else content('dedup_branch_history',profile,0,'B',49152))
    rank=history_rank(profile);j=rank[step%len(rank)];p=history_path(j)
    return p,len(genesis[p])//2-32,64,content('dedup_branch_history',profile,step,'replacement',64)
# Materialize genesis; chmod dirs 0750/files0640 and mtime1700000000ns0.
# For each step mutate selected file only and restore its mtime, retain all
# versions with same parent chain. Recurring odd completed states B, even A.
