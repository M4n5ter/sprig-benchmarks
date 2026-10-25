#!/usr/bin/env python3
"""New v2 DAG fixture. Freeze only after pinned image Cargo generated Cargo.lock."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
from stress_cargo_fixture import generate as generate_v1
from stress_fixture import normalize_source
from tree_oracle import snapshot

PROTOCOL_PATH = Path(__file__).with_name('stress-cargo-protocol.json')
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
PROTOCOL_SHA = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()


def expected(leaf):
    values = [leaf]
    for i in range(1, 16):
        deps = PROTOCOL['dependencies'][i]
        values.append((i+1+sum(values[d] for d in deps)) % 2**64)
    return str(values[-1])+'\n'


def generate(root):
    generate_v1(root,16)
    root = Path(root)
    # v2 intentionally supersedes the old serialized graph, without editing it.
    for i, deps in enumerate(PROTOCOL['dependencies']):
        name = f'node{i:03}'
        crate = root/name
        toml = f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'
        toml += ''.join(f'node{d:03} = {{ path = "../node{d:03}" }}\n' for d in deps)
        (crate/'Cargo.toml').write_text(toml)
        if i:
            old = (crate/'src/lib.rs').read_text().split('\n', 1)[1]
            expr = f'{i+1}u64'+''.join(f'.wrapping_add(node{d:03}::value())' for d in deps)
            (crate/'src/lib.rs').write_text(f'pub fn value()->u64 {{ {expr} }}\n'+old)
    (root/'node000/src/lib.rs').write_text(PROTOCOL['leafBefore'])
    (root/'node000/build.rs').write_text(PROTOCOL['buildScript'])
    (root/'node000/build-input.txt').write_text('1\n')
    normalize_source(root)
    return {'schema':'sprig-stress-cargo-prepared-v2','requiresPinnedLockfile':True,
            'protocolSha256':PROTOCOL_SHA}


def freeze(root):
    root = Path(root)
    for name in ('target','.cargo-home','.tmp'):
        if (root/name).exists():
            raise ValueError('freeze requires pristine source without '+name)
    lock = tomllib.loads((root/'Cargo.lock').read_text())
    packages=lock.get('package',[])
    if lock.get('version')!=4 or sorted(p['name'] for p in packages)!=sorted(PROTOCOL['packages']):
        raise ValueError('lockfile package set/version differs from pinned DAG')
    if any(p.get('source') or p.get('checksum') or p.get('version')!='0.1.0' for p in packages):
        raise ValueError('DAG lockfile must contain only local0.1.0 packages')
    if (root/'node000/src/lib.rs').read_text()!=PROTOCOL['leafBefore'] or (root/'node000/build.rs').read_text()!=PROTOCOL['buildScript']:
        raise ValueError('DAG source differs from fixed v2 protocol')
    normalize_source(root)
    return {'schema':'sprig-stress-cargo-v2','crates':16,'totalPackages':17,
            'packages':PROTOCOL['packages'],'dependencies':PROTOCOL['dependencies'],'protocolSha256':PROTOCOL_SHA,
            'expectedStdoutBefore':expected(2),'expectedStdoutAfter':expected(103),
            'buildScriptBefore':'pub const BUILD_VALUE: u64 = 1;\n',
            'buildScriptAfter':'pub const BUILD_VALUE: u64 = 2;\n',
            'lockfileSha256':hashlib.sha256((root/'Cargo.lock').read_bytes()).hexdigest(),
            'toolchainRequirement':'rustc 1.90.0; cargo 1.90.0; shared immutable image',
            'initial':snapshot(root)}


def validate_manifest(document):
    if document.get('schema')!='sprig-stress-cargo-v2' or document.get('crates')!=16 or document.get('totalPackages')!=17:
        raise ValueError('requires v2 16-library/17-package DAG')
    if document.get('packages')!=PROTOCOL['packages'] or document.get('protocolSha256')!=PROTOCOL_SHA:
        raise ValueError('DAG package/protocol binding mismatch')
    if document.get('dependencies')!=PROTOCOL['dependencies']:
        raise ValueError('DAG topology binding mismatch')
    if document.get('expectedStdoutBefore')!=expected(2) or document.get('expectedStdoutAfter')!=expected(103):
        raise ValueError('DAG expected executable values mismatch')
    if document.get('buildScriptBefore')!='pub const BUILD_VALUE: u64 = 1;\n' or document.get('buildScriptAfter')!='pub const BUILD_VALUE: u64 = 2;\n':
        raise ValueError('DAG generated artifact expectations mismatch')
    if len(document.get('lockfileSha256',''))!=64 or any(c not in '0123456789abcdef' for c in document.get('lockfileSha256','')):
        raise ValueError('DAG lockfile hash is invalid')
    return document


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['generate','freeze']);parser.add_argument('root',type=Path)
    parser.add_argument('--oracle',type=Path)
    args=parser.parse_args();result=generate(args.root) if args.operation=='generate' else freeze(args.root)
    if args.oracle:
        if args.operation!='freeze':parser.error('--oracle requires freeze')
        args.oracle.write_text(json.dumps(result['initial'],sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
