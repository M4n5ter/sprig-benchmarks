#!/usr/bin/env python3
"""Bounded deterministic stress recipe v1; NOT the frozen upstream fixture.
Only creates a new source tree. Never normalize a product or restored tree.
"""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import random
from tree_oracle import snapshot

STAMP = 1700000000000000000
SEED = 20261025

def bytes_for(key, size):
    return hashlib.shake_256(('sprig-stress-v1:' + key).encode()).digest(size)

def normalize_source(root):
    for p in sorted([root, *root.rglob('*')], key=lambda x: len(x.parts), reverse=True):
        if not p.is_symlink():
            os.chmod(p, 0o750 if p.is_dir() else 0o640)
        os.utime(p, ns=(STAMP, STAMP), follow_symlinks=False)

def generate(root, *, files=256, size=4096, depth=0, width=32, links=0,
             steps=0, pattern='random', symlink=False):
    root = Path(root)
    if not (1 <= files <= 50000 and 1 <= size <= 16*1024*1024
            and 0 <= depth <= 128 and 1 <= width <= 1024
            and 0 <= links <= files and 0 <= steps <= 1000):
        raise ValueError('fixture outside bounded recipe')
    if files * size > 256*1024*1024 or pattern not in ('random', 'hot', 'repeated'):
        raise ValueError('invalid byte budget or edit pattern')
    if steps and size < 64:
        raise ValueError('history requires >=64-byte files')
    root.mkdir()  # fail closed on existing root; no destructive replacement
    names = []
    prefix = Path(*(['d'] * depth))
    for i in range(files):
        rel = prefix / f'w{i % width:04d}' / f'f{i:06d}.dat'
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes_for(f'file:{i}', size))
        names.append(rel.as_posix())
    if links:
        (root / 'links').mkdir()
        for i in range(links):
            os.link(root / names[i], root / 'links' / f'l{i:06d}.dat')
    if symlink:
        os.symlink(names[0], root / 'source-link')
    normalize_source(root)
    initial = snapshot(root)
    rng = random.Random(SEED)
    state = {}
    edits = []
    for k in range(steps):
        index = rng.randrange(files) if pattern == 'random' else (k % min(files, 8) if pattern == 'hot' else 0)
        name = names[index]
        data = state.setdefault(name, bytearray(bytes_for(f'file:{index}', size)))
        offset = rng.randrange(size - 63) if pattern != 'repeated' else 0
        payload = bytes_for(f'edit:{pattern}:{k}', 64) if pattern != 'repeated' else bytes_for(f'repeated:{k % 2}', 64)
        data[offset:offset+64] = payload
        aliases = [name] + ([f'links/l{index:06d}.dat'] if index < links else [])
        edits.append(dict(step=k+1, path=name, aliases=aliases, offset=offset,
                          data=base64.b64encode(payload).decode(),
                          sha256=hashlib.sha256(data).hexdigest()))
    return dict(schema='sprig-stress-fixture-v1', seed=SEED,
                parameters=dict(files=files, size=size, depth=depth, width=width,
                                links=links, steps=steps, pattern=pattern, symlink=symlink),
                initial=initial, edits=edits)

def expected_after(fixture, count):
    if not 0 <= count <= len(fixture['edits']):
        raise ValueError('invalid checkpoint ordinal')
    result = copy.deepcopy(fixture['initial'])
    entries = {e['path']: e for e in result['entries']}
    for edit in fixture['edits'][:count]:
        for path in edit['aliases']:
            entries[path]['sha256'] = edit['sha256']
    return result

def apply_edit(root, edit):
    """Run on a quiescent writable view, and exit before checkpoint.
    Positional overwrite keeps hardlinks; file fsync and fixed-mtime restore
    are charged to write task. This is not a crash-durable mtime claim.
    """
    rel = Path(edit['path'])
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('unsafe edit path')
    path = Path(root) / rel
    with path.open('r+b') as stream:
        stream.seek(edit['offset'])
        stream.write(base64.b64decode(edit['data'], validate=True))
        stream.flush()
        os.fsync(stream.fileno())
    os.utime(path, ns=(STAMP, STAMP))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    for name, default in [('files',256), ('size',4096), ('depth',0), ('width',32), ('links',0), ('steps',0)]:
        p.add_argument('--'+name, type=int, default=default)
    p.add_argument('--symlink', action='store_true')
    p.add_argument('--pattern', choices=['random','hot','repeated'], default='random')
    args = vars(p.parse_args())
    root = args.pop('output')
    print(json.dumps(generate(root, **args), sort_keys=True))

if __name__ == '__main__':
    main()
