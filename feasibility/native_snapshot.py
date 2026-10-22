#!/usr/bin/env python3
"""Disposable Btrfs feasibility experiment, NOT the Sprig implementation.

Requires official python3-btrfsutil and an already authorized, mounted scratch FS.
Never mounts, formats, deletes, or opens an existing store. No merge/SDK/recovery
claim: this isolates authoritative snapshots + generic aligned-block dedup.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import shlex
import subprocess
import stat
import struct
import sys
import time
import uuid

BLOCK = 4096
FIDEDUPERANGE = 0xC0189436  # Linux _IOWR(0x94, 54, struct file_dedupe_range).
DEDUPE = struct.Struct('=QQHHIqQQiI')  # 24-byte header + one 32-byte destination.
assert DEDUPE.size == 56


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write(encoded(value))
            out.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def memory_bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    total = sys.getsizeof(value)
    if isinstance(value, dict):
        total += sum(memory_bytes(k, seen) + memory_bytes(v, seen) for k, v in value.items())
    elif isinstance(value, (tuple, list, set)):
        total += sum(memory_bytes(v, seen) for v in value)
    return total


def name_ok(name):
    if not name or len(name) > 64 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        raise ValueError('invalid managed name')


def inventory(tree):
    """Trusted, quiescent tree only; never traverse child symlinks/mounts."""
    root_device = tree.stat().st_dev
    yield '', tree, tree.lstat()
    def fail_walk(error):
        raise error

    for parent, dirs, files in os.walk(tree, followlinks=False, onerror=fail_walk):
        dirs.sort()
        files.sort()
        descend = []
        for name in sorted(dirs + files):
            path = Path(parent) / name
            # os.walk yields lexical descendants; avoid pathlib's repeated ancestor
            # object construction on deep trees. No traversal or policy changes.
            relative = os.path.relpath(path, tree)
            relative.encode('utf-8')  # Reject undecodable filesystem names.
            info = path.lstat()
            if info.st_dev != root_device:
                raise ValueError('nested mount or subvolume is unsupported')
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                raise ValueError('special file is unsupported')
            if name in dirs and stat.S_ISDIR(info.st_mode):
                descend.append(name)
            yield relative, path, info
        dirs[:] = descend


def same_file_stat(before, after):
    return (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)


class NativeStore:
    def __init__(self, root):
        import btrfsutil  # Official btrfs-progs Python bindings, not vendored code.
        self.btrfs = btrfsutil
        root = Path(root)
        if root.exists() or root.is_symlink():
            raise ValueError('prototype requires a NEW store; never overwrites an existing path')
        self.root = root.parent.resolve(strict=True) / root.name
        # This checks the actual filesystem; unsupported hosts fail, not copy-fallback.
        btrfsutil.subvolume_id(self.root.parent)
        if os.statvfs(self.root.parent).f_frsize != BLOCK:
            raise ValueError('this experiment requires a 4096-byte Btrfs sector size')
        btrfsutil.create_subvolume(self.root)
        os.chmod(self.root, 0o700)
        for directory in ('workspaces', 'snapshots', 'revisions', 'backups'):
            (self.root / directory).mkdir(mode=0o700)
        self.lock = open(self.root / 'lock', 'xb+')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.state = {'schema': 'native-feasibility-1', 'generation': 0, 'branches': {}, 'workspaces': {}}
        write_new(self.root / 'state.json', self.state)
        sync_dir(self.root)
        # Hash candidates only; no data cache, persistent index, or mtime shortcut.
        # RAM is reported. A production reopen/index rebuild is NOT implemented.
        self.index = {}
        self.workspace_hashes = {}
        self.dedup = {'ioctls': 0, 'bytes_compared_and_shared': 0, 'different': 0}

    def _publish(self):
        current = json.loads((self.root / 'state.json').read_bytes())
        if current['generation'] != self.state['generation']:
            raise RuntimeError('metadata generation moved; refusing to publish')
        write_new(self.root / 'backups' / f"{current['generation']}.json", current)
        sync_dir(self.root / 'backups')
        self.state['generation'] += 1
        staged = self.root / ('state-' + uuid.uuid4().hex + '.tmp')
        write_new(staged, self.state)
        os.replace(staged, self.root / 'state.json')
        sync_dir(self.root)

    def _share(self, target_fd, groups):
        for source, source_offset, target_offset, length in groups:
            source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                    raise ValueError('dedup source is not a regular file')
                data = bytearray(DEDUPE.pack(source_offset, length, 1, 0, 0, target_fd, target_offset, 0, 0, 0))
                fcntl.ioctl(source_fd, FIDEDUPERANGE, data, True)
                _, _, _, _, _, _, _, done, status, _ = DEDUPE.unpack(data)
                self.dedup['ioctls'] += 1
                if status < 0:
                    raise OSError(-status, 'FIDEDUPERANGE destination failed')
                if status == 1:
                    # A hash candidate never authorizes overwriting bytes.
                    self.dedup['different'] += 1
                elif status != 0 or done != length:
                    raise RuntimeError('unexpected or partial deduplication result')
                else:
                    self.dedup['bytes_compared_and_shared'] += done
            finally:
                os.close(source_fd)

    def _capture(self, tree, previous_hashes):
        tree_digest = hashlib.sha256()
        hashes = {}
        pending = {}
        for relative, path, info in inventory(tree):
            record = [relative, stat.S_IMODE(info.st_mode), info.st_mtime_ns]
            if stat.S_ISDIR(info.st_mode):
                record += ['directory']
            elif stat.S_ISLNK(info.st_mode):
                record += ['symlink', os.fsencode(os.readlink(path)).hex()]
            else:
                if info.st_nlink != 1:
                    raise ValueError('hardlinked workspace files are unsupported by this prototype')
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or not same_file_stat(info, before):
                        raise ValueError('file changed before capture')
                    full = hashlib.sha256()
                    blocks = []
                    offset = 0
                    # Every file is read on every checkpoint, even if mtime/size match.
                    # Real files may return short reads; concatenate to block boundaries.
                    carry = b''
                    while True:
                        data = os.read(fd, 1024 * 1024)
                        if not data:
                            break
                        full.update(data)
                        data = carry + data
                        complete = len(data) // BLOCK * BLOCK
                        view = memoryview(data)
                        for start in range(0, complete, BLOCK):
                            blocks.append((hashlib.sha256(view[start:start + BLOCK]).digest(), offset))
                            offset += BLOCK
                        carry = data[complete:]
                    after = os.fstat(fd)
                    if not same_file_stat(before, after) or offset + len(carry) != before.st_size:
                        raise ValueError('file changed during capture')
                finally:
                    os.close(fd)
                digest = full.hexdigest()
                hashes[relative] = digest
                record += ['file', before.st_size, digest]
                groups = []
                for block_hash, offset in blocks:
                    candidate = self.index.get(block_hash) or pending.get(block_hash)
                    if candidate is None:
                        pending[block_hash] = (str(path), offset)
                    elif previous_hashes.get(relative) != digest:
                        source, source_offset = candidate
                        if source == str(path) and source_offset == offset:
                            continue
                        if (groups and groups[-1][0] == source
                                and groups[-1][1] + groups[-1][3] == source_offset
                                and groups[-1][2] + groups[-1][3] == offset
                                and groups[-1][3] + BLOCK <= 16 * 1024 * 1024
                                and (source != str(path) or source_offset + BLOCK <= groups[-1][2])):
                            old = groups[-1]
                            groups[-1] = (old[0], old[1], old[2], old[3] + BLOCK)
                        else:
                            groups.append((source, source_offset, offset, BLOCK))
                if groups:
                    destination = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
                    try:
                        self._share(destination, groups)
                        # Persist dedup remappings, without changing file contents.
                        os.fsync(destination)
                    finally:
                        os.close(destination)
            tree_digest.update(encoded(record) + b'\n')
        return tree_digest.hexdigest(), hashes, pending

    def _revision(self, workspace, parents, message, digest, pending):
        clock = 1 + max((json.loads((self.root / 'revisions' / f'{p}.json').read_bytes())['clock'] for p in parents), default=0)
        record = {'parents': parents, 'clock': clock, 'message': message, 'tree_sha256': digest}
        revision = hashlib.sha256(encoded(record)).hexdigest()
        snapshot = self.root / 'snapshots' / revision
        # Non-async Btrfs snapshot creation commits its transaction and flushes
        # source ordered data. Publish the user-space DAG/head only afterward.
        self.btrfs.create_snapshot(workspace, snapshot, read_only=True)
        if not self.btrfs.get_subvolume_read_only(snapshot):
            raise RuntimeError('history snapshot is not read-only')
        sync_dir(self.root / 'snapshots')
        record['id'] = revision
        record['snapshot_uuid'] = str(self.btrfs.subvolume_info(snapshot).uuid)
        write_new(self.root / 'revisions' / f'{revision}.json', record)
        sync_dir(self.root / 'revisions')
        # New index candidates are rebased to immutable snapshots, never to a
        # mutable workspace that could later change under the same pathname.
        for key, (path, offset) in pending.items():
            relative = Path(path).relative_to(workspace)
            self.index[key] = (str(snapshot / relative), offset)
        return revision

    def import_tree(self, source, name='main'):
        name_ok(name)
        source = Path(source)
        if source.is_symlink():
            raise ValueError('source root must be a real directory')
        source = source.resolve(strict=True)
        if not source.is_dir() or self.root == source or self.root in source.parents or source in self.root.parents:
            raise ValueError('invalid/overlapping source tree')
        list(inventory(source))  # Reject special files/mounts before making a copy.
        workspace = self.root / 'workspaces' / name
        self.btrfs.create_subvolume(workspace)
        # Deliberate byte copy from the external common fixture. No uncharged
        # reflink to fixture-owned extents. Symlinks remain opaque.
        shutil.copytree(source, workspace, dirs_exist_ok=True, symlinks=True)
        # Check copied-file writeback errors before snapshot publication. A
        # snapshot transaction is not a replacement for writer error reporting.
        for _, copied, info in inventory(workspace):
            if stat.S_ISREG(info.st_mode):
                fd = os.open(copied, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        digest, hashes, pending = self._capture(workspace, {})
        revision = self._revision(workspace, [], 'import', digest, pending)
        self.state['branches'][name] = revision
        self.state['workspaces'][name] = {'branch': name, 'base': revision}
        self.workspace_hashes[name] = hashes
        self._publish()
        return revision

    def branch(self, source, name):
        name_ok(name)
        if name in self.state['branches']:
            raise ValueError('branch exists')
        self.state['branches'][name] = self.state['branches'][source]
        self._publish()

    def fork(self, source, name):
        name_ok(name)
        if name in self.state['workspaces'] or name in self.state['branches']:
            raise ValueError('name exists')
        original = self.state['workspaces'][source]
        target = self.root / 'workspaces' / name
        self.btrfs.create_snapshot(self.root / 'workspaces' / source, target)
        sync_dir(self.root / 'workspaces')
        self.state['branches'][name] = original['base']
        self.state['workspaces'][name] = {'branch': name, 'base': original['base']}
        self.workspace_hashes[name] = self.workspace_hashes[source]
        self._publish()
        return target

    def checkpoint(self, name, message):
        workspace = self.state['workspaces'][name]
        previous = self.state['branches'][workspace['branch']]
        if previous != workspace['base']:
            raise RuntimeError('head moved; prototype does not implement automatic merge')
        tree = self.root / 'workspaces' / name
        digest, hashes, pending = self._capture(tree, self.workspace_hashes[name])
        parent = json.loads((self.root / 'revisions' / f'{previous}.json').read_bytes())
        if digest == parent['tree_sha256']:
            return previous
        revision = self._revision(tree, [previous], message, digest, pending)
        self.state['branches'][workspace['branch']] = revision
        workspace['base'] = revision
        self.workspace_hashes[name] = hashes
        self._publish()
        return revision


def verify(tree, oracle):
    actual = {relative for relative, _, info in inventory(tree) if stat.S_ISREG(info.st_mode)}
    assert actual == {row['path'] for row in oracle}
    for row in oracle:
        data = (tree / row['path']).read_bytes()
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']


def shell(tree, command):
    subprocess.run(['bash', '-c', command], cwd=tree, check=True,
                   stdout=subprocess.DEVNULL)


def checks(oracle):
    return '(' + ';'.join("printf '%s  %s\\n' " + shlex.quote(row['sha256']) + ' ' + shlex.quote(row['path']) for row in oracle) + ') | sha256sum -c -'


def run_case(args):
    source = Path(args.source).resolve(strict=True)
    oracle = json.loads(Path(args.oracle).read_text())
    result = {'prototype_only': True, 'complete_sprig_semantics': False,
              'backend': 'Btrfs readonly snapshot history + generic aligned block dedup',
              'block_bytes': BLOCK, 'persistent_dedup_index': False,
              'index_reopen_implemented': False, 'checkpoint_steps': []}
    start = time.perf_counter()
    store = NativeStore(args.root)
    result['init_seconds'] = time.perf_counter() - start
    start = time.perf_counter()
    genesis = store.import_tree(source)
    result['import_seconds'] = time.perf_counter() - start
    start = time.perf_counter()
    store.branch('main', 'metadata')
    result['metadata_branch_seconds'] = time.perf_counter() - start
    start = time.perf_counter()
    work = store.fork('main', 'work')
    result['first_fork_seconds'] = time.perf_counter() - start
    command = checks(oracle)
    start = time.perf_counter()
    shell(work, command)
    result['first_read_seconds'] = time.perf_counter() - start
    result['total_import_fork_read_seconds'] = sum(result[k] for k in ('import_seconds', 'first_fork_seconds', 'first_read_seconds'))
    start = time.perf_counter()
    second = store.fork('main', 'second')
    result['warm_fork_seconds'] = time.perf_counter() - start
    start = time.perf_counter()
    shell(second, command)
    result['warm_read_seconds'] = time.perf_counter() - start
    result['warm_total_seconds'] = result['warm_fork_seconds'] + result['warm_read_seconds']
    history = []
    write_seconds = 0.0
    if args.steps:
        for step in json.loads(Path(args.steps).read_text()):
            target = work / step['path']
            start = time.perf_counter()
            command = ("set -e; printf '%s' " + shlex.quote(step['data'])
                       + " | base64 -d | dd of=" + shlex.quote(step['path'])
                       + " bs=65536 iflag=fullblock oflag=seek_bytes seek=" + str(int(step['offset']))
                       + " conv=notrunc,fsync status=none; touch -d @1700000000 " + shlex.quote(step['path']))
            shell(work, command)
            write_seconds += time.perf_counter() - start
            start = time.perf_counter()
            revision = store.checkpoint('work', 'Frozen history step ' + str(step['step']))
            elapsed = time.perf_counter() - start
            assert revision != genesis and revision not in {r[0] for r in history}
            shell(work, checks([step]))
            history.append((revision, step['path'], step['sha256']))
            result['checkpoint_steps'].append({'step': step['step'], 'seconds': elapsed, 'revision': revision})
        final = json.loads(Path(str(args.steps).replace('-steps.json', '-final.json')).read_text())
        shell(work, checks(final))
        verify(work, final)
        for revision, path, expected in history:
            assert hashlib.sha256((store.root / 'snapshots' / revision / path).read_bytes()).hexdigest() == expected
        chain = store.state['branches']['work']
        for revision, _, _ in reversed(history):
            assert chain == revision
            chain = json.loads((store.root / 'revisions' / f'{chain}.json').read_bytes())['parents'][0]
        assert chain == genesis
    verify(store.root / 'snapshots' / genesis, oracle)
    verify(store.root / 'workspaces' / 'main', oracle)
    verify(second, oracle)
    verify(source, oracle)
    result.update({'ok': True, 'checkpoint_seconds': sum(r['seconds'] for r in result['checkpoint_steps']),
                   'write_seconds': write_seconds, 'history_distinct_revisions': len(history),
                   'snapshot_count': len(list((store.root / 'snapshots').iterdir())),
                   'dedup': store.dedup, 'index_records': len(store.index),
                   'index_and_hash_maps_estimated_ram_bytes': memory_bytes((store.index, store.workspace_hashes)),
                   'process_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})
    print(json.dumps(result, sort_keys=True))


def smoke(args):
    source = Path(args.source)
    source.mkdir()  # Fresh synthetic fixture only; existing paths fail.
    data = hashlib.shake_256(b'native snapshot smoke').digest(3 * BLOCK + 17)
    (source / 'a').write_bytes(data)
    (source / 'b').write_bytes(data)
    (source / 'repeated').write_bytes(b'Q' * (8 * BLOCK))
    (source / 'empty').touch()
    (source / 'dir').mkdir()
    (source / 'link').symlink_to('/nonexistent/smoke-target')
    store = NativeStore(args.root)
    genesis = store.import_tree(source)
    work = store.fork('main', 'work')
    original = (work / 'a').stat()
    with (work / 'a').open('r+b') as out:
        out.write(b'changed!')
        out.flush()
        os.fsync(out.fileno())
    os.utime(work / 'a', ns=(original.st_atime_ns, original.st_mtime_ns))
    changed = store.checkpoint('work', 'same-size same-mtime edit')
    assert changed != genesis
    assert (store.root / 'snapshots' / genesis / 'a').read_bytes() == data
    assert (store.root / 'workspaces' / 'main' / 'a').read_bytes() == data
    assert (source / 'a').read_bytes() == data
    assert os.readlink(work / 'link') == '/nonexistent/smoke-target'
    assert store.checkpoint('work', 'no-op') == changed
    (work / 'a').rename(work / 'dir' / 'moved')
    (work / 'b').unlink()  # Only this newly generated synthetic fixture.
    moved = store.checkpoint('work', 'rename and delete')
    assert moved != changed
    assert (store.root / 'snapshots' / changed / 'b').read_bytes() == data
    assert not (store.root / 'snapshots' / moved / 'b').exists()
    assert (store.root / 'snapshots' / moved / 'dir' / 'moved').read_bytes().startswith(b'changed!')
    assert all(store.btrfs.get_subvolume_read_only(p) for p in (store.root / 'snapshots').iterdir())
    os.mkfifo(work / 'unsupported-fifo')
    try:
        store.checkpoint('work', 'must reject special file')
    except ValueError as error:
        assert 'special file' in str(error)
    else:
        raise AssertionError('special file unexpectedly captured')
    assert store.state['branches']['work'] == moved
    print(json.dumps({'ok': True, 'prototype_only': True, 'dedup': store.dedup,
                      'checks': ['duplicate and repeated blocks', 'same-size fixed-mtime edit',
                                 'history and fork isolation', 'opaque symlink', 'no-op',
                                 'rename and delete', 'special file rejects before publication']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run')
    run.add_argument('--root', required=True)
    run.add_argument('--source', required=True)
    run.add_argument('--oracle', required=True)
    run.add_argument('--steps')
    test = sub.add_parser('smoke')
    test.add_argument('--root', required=True)
    test.add_argument('--source', required=True, help='NEW synthetic source directory outside measured filesystem')
    args = parser.parse_args()
    (run_case if args.command == 'run' else smoke)(args)


if __name__ == '__main__':
    main()
