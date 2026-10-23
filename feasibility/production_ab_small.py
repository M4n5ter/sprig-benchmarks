#!/usr/bin/env python3
"""Deterministic small-tree control, not an upstream workload fixture.

Eight root-level 1 KiB files; 100 real 64-byte replacements. Successive visits
alternate two in-file slots, and each payload is unique. No paths are added by
edits, so the logical tree always has nine entries including its root.
Output schemas match fixtures.py's genesis, steps and final JSON sidecars.
"""
import base64
import hashlib
import json
import os
from pathlib import Path

STAMP = 1_700_000_000


def oracle(files):
    return [{"path": name, "bytes": len(data),
             "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(files.items())]


def generate(root):
    """Create a new source directory and three new sibling JSON files."""
    root = Path(root)
    outputs = [root.parent / (root.name + suffix)
               for suffix in (".json", "-steps.json", "-final.json")]
    for path in [root, *outputs]:
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
    root.mkdir()
    genesis = {f"file-{index:02}.dat": hashlib.shake_256(
        f"small-tree-control-v1/genesis/{index}".encode()).digest(1024)
        for index in range(8)}
    for name, data in genesis.items():
        path = root / name
        with path.open("xb") as handle:
            handle.write(data)
        path.chmod(0o640)
        os.utime(path, ns=(STAMP * 10**9, STAMP * 10**9))
    root.chmod(0o750)
    os.utime(root, ns=(STAMP * 10**9, STAMP * 10**9))
    current = genesis.copy()
    steps = []
    states = set()
    for index in range(100):
        name = f"file-{index % 8:02}.dat"
        offset = 128 if (index // 8) % 2 == 0 else 640
        payload = (index + 1).to_bytes(8, "little") + hashlib.shake_256(
            f"small-tree-control-v1/edit/{index}".encode()).digest(56)
        before = current[name]
        assert before[offset:offset + 64] != payload
        current[name] = before[:offset] + payload + before[offset + 64:]
        steps.append({"step": index + 1, "path": name, "offset": offset,
                      "data": base64.b64encode(payload).decode(),
                      "sha256": hashlib.sha256(current[name]).hexdigest()})
        states.add(hashlib.sha256(b"".join(current[name] for name in sorted(current))).digest())
    assert len(states) == 100
    manifests = [oracle(genesis), steps, oracle(current)]
    for path, value in zip(outputs, manifests):
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
    return {"files": 8, "logical_entries_including_root": 9,
            "logical_bytes": 8192, "edits": 100,
            "distinct_post_edit_states": len(states)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="new source path; its parent must exist")
    print(json.dumps(generate(parser.parse_args().root), sort_keys=True))
