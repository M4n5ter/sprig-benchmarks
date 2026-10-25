#!/usr/bin/env python3
"""Offline synthetic Cargo dependency DAG; no claim to be a real application.
Shared leaves, direct fanout, generics and one rerun-sensitive build script.
"""
import argparse
import json
from pathlib import Path
from stress_fixture import normalize_source
from tree_oracle import snapshot


def generate(root, crates=16):
    if crates not in (4, 16, 64):
        raise ValueError('supported crate counts: 4 (sanity), 16, 64')
    root = Path(root)
    root.mkdir()
    names = [f'node{i:03}' for i in range(crates)]
    members = ', '.join(json.dumps(x) for x in [*names, 'app'])
    (root/'Cargo.toml').write_text(f'[workspace]\nresolver = "2"\nmembers = [{members}]\n')
    graph = {}
    values = []
    for i, name in enumerate(names):
        p = root/name
        (p/'src').mkdir(parents=True)
        deps = sorted({max(0, i-1), i//2, 0}) if i else []
        graph[name] = [names[d] for d in deps]
        toml = f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'
        toml += ''.join(f'{names[d]} = {{ path = "../{names[d]}" }}\n' for d in deps)
        (p/'Cargo.toml').write_text(toml)
        terms = [str(i+1), *(f'{names[d]}::value()' for d in deps)]
        # wrapping arithmetic gives identical debug/release semantics.
        expr = '('+terms[0]+'u64)'+''.join('.wrapping_add('+term+')' for term in terms[1:])
        generic = '\n'.join(f'pub fn generic_{j}<T: Into<u64>>(v:T)->u64 {{ v.into().wrapping_add({j}) }}' for j in range(32))
        (p/'src/lib.rs').write_text(f'pub fn value()->u64 {{ {expr} }}\n{generic}\n')
        values.append((i+1+sum(values[d] for d in deps)) % 2**64)
        if i == 0:
            (p/'build.rs').write_text('fn main() { println!("cargo:rerun-if-changed=build-input.txt"); }\n')
            (p/'build-input.txt').write_text('stable-build-input-v1\n')
    app = root/'app'
    (app/'src').mkdir(parents=True)
    (app/'Cargo.toml').write_text('[package]\nname = "stress-app"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n'+f'{names[-1]} = {{ path = "../{names[-1]}" }}\n')
    (app/'src/main.rs').write_text(f'fn main() {{ println!("{{}}", {names[-1]}::value()); }}\n')
    normalize_source(root)
    return dict(schema='sprig-stress-cargo-v1', crates=crates, totalPackages=crates+1,
                graph=graph, expectedStdout=str(values[-1])+'\n', initial=snapshot(root),
                lockfileStatus='must generate with pinned Cargo before oracle freeze/import',
                verificationStatus='generated; build/Fresh not yet validated')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--crates', type=int, default=16)
    a = p.parse_args()
    print(json.dumps(generate(a.output, a.crates), sort_keys=True))
