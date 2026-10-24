#!/usr/bin/env python3
"""Materialize a fresh deterministic SOURCE fixture before either product import."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

p=argparse.ArgumentParser()
p.add_argument('--template',required=True)
p.add_argument('--oracle',required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
source=Path(a.template).resolve(strict=True)
output=Path(a.output).absolute()
assert source.is_dir() and not output.exists() and not output.is_symlink()
assert output.parent.resolve(strict=True)==output.parent
oracle=json.loads(Path(a.oracle).read_text())
assert oracle['schema']=='cargo-full-tree-v1'
expected={x['path']:x for x in oracle['entries']}
assert len(expected)==len(oracle['entries']) and '.' in expected
for name,row in expected.items():
    relative=Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    item=source/relative
    info=item.lstat()
    assert not item.is_symlink()
    if row['type']=='directory':
        assert stat.S_ISDIR(info.st_mode)
    else:
        assert row['type']=='file' and stat.S_ISREG(info.st_mode)
        assert len(item.read_bytes())==row['size']
        assert hashlib.sha256(item.read_bytes()).hexdigest()==row['sha256']
assert {'.',*[str(x.relative_to(source)) for x in source.rglob('*')]}==set(expected)
shutil.copytree(source,output,symlinks=False)
for name,row in sorted(expected.items(),key=lambda x:len(Path(x[0]).parts),reverse=True):
    item=output/Path(name)
    os.chmod(item,row['mode'])
    os.utime(item,ns=(row['mtime_ns'],row['mtime_ns']))
print(json.dumps({'created':str(output),'entries':len(expected),'purpose':'deterministic external source fixture; never normalize imported/restored product trees'}))
