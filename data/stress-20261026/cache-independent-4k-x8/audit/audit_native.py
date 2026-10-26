"""Read-only offline audit of the exact first three-pin screen artifact."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path('/tmp/sprig-native-cache-audit-afacf84');sys.path.insert(0,str(ROOT/'tools'))
from stress_cache_summary import summarize
from stress_cache_ablation import PINS
BENCH=Path('/workspace/scratch/5016a09b9681/sprig-comparison-20261024/stress-bench')
SOURCE=Path('/workspace/scratch/5016a09b9681/sprig-cache-admission')
HEAD='afacf84f0c6c80014c0e7c3cc00fac348357afbe'
ARTIFACT=ROOT/'artifact'
sha=lambda b:hashlib.sha256(b).hexdigest()
def one(pattern):
 values=list(ARTIFACT.rglob(pattern));assert len(values)==1,(pattern,len(values));return values[0]
def git(root,pin,path):return subprocess.check_output(['git','show',pin+':'+path],cwd=root)
reports=[(p,json.loads(p.read_text())) for p in ARTIFACT.rglob('stress-comparison.json')]
canary=next(p for p,r in reports if r['ablationStage']=='canary')
screen=next(p for p,r in reports if r['ablationStage']=='forward-latin')
result=summarize(screen,canary)
(ROOT/'recomputed-summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
server=json.loads(one('cache-screen-summary.json').read_text())
assert result['complete']==server['complete']
assert result['comparisons']==server['comparisons']
assert result['errors']==server['errors']
assert result['records']==server['records']
products=json.loads(one('cache-products.json').read_text())
assert products==json.loads(screen.read_text())['products']==json.loads(canary.read_text())['products']
assert [p['label'] for p in products]==list(PINS)
counts={};binaries={}
for product in products:
 label=product['label'];assert product['sha']==PINS[label]
 lines=one(label+'-source-hashes.txt').read_text().splitlines();counts[label]=0
 for line in lines:
  digest,path=line.split(None,1);prefix='sprig-'+label+'/'
  assert path.startswith(prefix);relative=path[len(prefix):]
  assert relative.startswith(('src/','tests/')) and sha(git(SOURCE,product['sha'],relative))==digest
  counts[label]+=1
 binary_digest,binary_path=one(label+'-binary-hash.txt').read_text().split()
 assert binary_path=='bin/'+label+'-sprig' and binary_digest==product['binarySha256']
 binaries[label]=binary_digest
scripts=one('script-hashes.txt').read_text().splitlines()
for line in scripts:
 digest,path=line.split(None,1);assert path.startswith('feasibility/') and sha(git(BENCH,HEAD,path))==digest
files=list(p for p in ARTIFACT.rglob('*') if p.is_file())
manifest=[dict(path=str(p.relative_to(ARTIFACT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(files)]
(ROOT/'artifact-files.json').write_text(json.dumps(manifest,indent=2)+'\n')
audit=dict(ok=True,complete=result['complete'],run=40294193428,head=HEAD,artifactFiles=len(files),artifactBytes=sum(f['bytes'] for f in manifest),canarySamples=3,screenSamples=len(result['records']),sourceFileCounts=counts,benchmarkScriptHashesVerified=len(scripts),recordedBinaryHashes=binaries,binaryExecutableBytesArchived=False,serverSummaryMatches=True,canaryReport=str(canary.relative_to(ARTIFACT)),screenReport=str(screen.relative_to(ARTIFACT)),errors=result['errors'])
(ROOT/'provenance-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2))
for edge,fields in (result['comparisons'] or {}).items():
 print(edge)
 for name in ('wholeSampleSeconds','restore_seconds','first_fork_seconds','warm_fork_seconds','postHistoryWholeFilesystemBytes'):
  v=fields.get(name)
  if v:print(name,[(round(p['percentChange'],3) if p['percentChange'] is not None else None) for p in v['pairs']],'median ratio',v['medianPairedRatio'],'geom ratio',v['geometricMeanPairedRatio'])
