#!/usr/bin/env python3
"""Read-only complete archive verifier. Does not extract, import helpers or run products."""
import hashlib,json,sys,tarfile
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text())
archive=root/manifest['archive']
assert archive.parent==root and archive.is_file() and not archive.is_symlink()
assert archive.stat().st_size==manifest['archiveBytes']
def hash_stream(stream):
 h=hashlib.sha256();size=0
 for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk);size+=len(chunk)
 return size,h.hexdigest()
with archive.open('rb') as stream:assert hash_stream(stream)==(manifest['archiveBytes'],manifest['archiveSha256'])
expected={r['path']:r for r in manifest['files']};assert len(expected)==len(manifest['files']);seen=set();total=0
with tarfile.open(archive,'r:gz') as tar:
 for member in tar:
  assert member.isfile() and member.name not in seen and member.name in expected
  assert not member.name.startswith('/') and '..' not in Path(member.name).parts
  row=expected[member.name];assert member.size==row['bytes']
  with tar.extractfile(member) as stream:assert hash_stream(stream)==(row['bytes'],row['sha256'])
  total+=row['bytes'];seen.add(member.name)
assert seen==set(expected) and total==manifest['completeUncompressedBytes']
print(json.dumps({'complete':True,'files':len(seen),'uncompressedBytes':total,'originalArtifactFiles':manifest['originalArtifactFiles'],'archiveSha256':manifest['archiveSha256']}))
