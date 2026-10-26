import hashlib,json,re,subprocess,sys
from pathlib import Path
base=Path(sys.argv[1]);bench=Path(sys.argv[2]);sprig=Path(sys.argv[3])
sha=lambda b:hashlib.sha256(b).hexdigest()
manifest=json.loads((base/'collection.json').read_text());rows=manifest['files'];seen=set()
for row in rows:
    name=row['path'];path=Path(name)
    assert not path.is_absolute() and '..' not in path.parts and name not in seen
    seen.add(name);file=base/path;assert file.is_file() and not file.is_symlink()
    body=file.read_bytes();assert len(body)==row['bytes'] and sha(body)==row['sha256'],name
actual={str(file.relative_to(base)) for file in base.rglob('*') if file.is_file()}
assert actual==seen|{'collection.json'},(actual-seen,seen-actual)
assert manifest['declaredArchiveVerification']['ok'] is True
products=json.loads((base/'results/stress-cargo-ab-products.json').read_text())
source_counts={};binary_hashes={}
for product in products:
    variant=product['label'].removeprefix('sprig-');pin=product['sha'];expected=set(subprocess.check_output(['git','-C',str(sprig),'ls-tree','-r','--name-only',pin,'--','src','tests'],text=True).splitlines());found=set()
    for line in (base/f'results/{variant}-source-hashes.txt').read_text().splitlines():
        match=re.fullmatch(r'([a-f0-9]{64})  sprig-'+variant+r'/(.+)',line);assert match,line
        name=match[2];assert name in expected and name not in found;found.add(name)
        data=subprocess.check_output(['git','-C',str(sprig),'show',pin+':'+name]);assert sha(data)==match[1],name
    assert found==expected
    source_counts[product['label']]=len(found)
    binary=(base/f'results/{variant}-binary-hash.txt').read_text().split()[0];assert binary==product['binarySha256'];binary_hashes[product['label']]=binary
    log=(base/f'results/{variant}-release-build.log').read_text();assert 'Compiling sprig ' in log and '/sprig-'+variant in log
script_count=0
for line in (base/'results/script-hashes.txt').read_text().splitlines():
    match=re.fullmatch(r'([a-f0-9]{64})  (feasibility/.+)',line);assert match,line
    data=subprocess.check_output(['git','-C',str(bench),'show','12a243730f5db7b47dae5002bf0bc5b80a2a0b61:'+match[2]])
    assert sha(data)==match[1],match[2];script_count+=1
result={'ok':True,'collectionFilesVerified':len(rows),'declaredArchiveVerification':manifest['declaredArchiveVerification'],'sourceFileCounts':source_counts,'recordedBinaryHashes':binary_hashes,'benchmarkScriptHashesVerified':script_count,'binaryExecutableBytesArchived':False}
print(json.dumps(result,indent=2))
