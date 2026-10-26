#!/usr/bin/env python3
"""Quiescent-tree oracle. Snapshot to stdout; verify expected JSON from stdin.
No symlink traversal, target/cache exclusions, or writes to inspected trees.
"""
import argparse
import hashlib
import json
import os
import stat
import sys

SCHEMA = 'cargo-full-tree-v1'


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)


def snapshot(root):
    root = os.path.abspath(os.fspath(root))
    if not stat.S_ISDIR(os.lstat(root).st_mode):
        raise ValueError('root must be a directory, not a symlink')
    entries = []
    links = {}

    def walk(full, rel):
        before = os.lstat(full)
        mode = before.st_mode
        entry = dict(path=rel, mode=mode & 0o777, mtime_ns=before.st_mtime_ns)
        if stat.S_ISREG(mode):
            entry['type'] = 'file'
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(full, flags)
            with os.fdopen(fd, 'rb') as stream:
                if stamp(os.fstat(stream.fileno())) != stamp(before):
                    raise ValueError('file changed before read: ' + repr(rel))
                h = hashlib.sha256()
                size = 0
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    h.update(block)
                    size += len(block)
                if stamp(os.fstat(stream.fileno())) != stamp(before):
                    raise ValueError('file changed during read: ' + repr(rel))
            if size != before.st_size:
                raise ValueError('size changed: ' + repr(rel))
            entry.update(size=size, sha256=h.hexdigest())
            links.setdefault((before.st_dev, before.st_ino), []).append(rel)
        elif stat.S_ISLNK(mode):
            entry.update(type='symlink', target=os.readlink(full))
        elif stat.S_ISDIR(mode):
            entry['type'] = 'directory'
            with os.scandir(full) as scan:
                names = sorted((item.name for item in scan), key=os.fsencode)
            for name in names:
                walk(os.path.join(full, name), name if rel == '.' else rel + '/' + name)
        else:
            raise ValueError('unsupported special node: ' + repr(rel))
        if stamp(os.lstat(full)) != stamp(before):
            raise ValueError('entry changed during snapshot: ' + repr(rel))
        entries.append(entry)

    walk(root, '.')
    entries.sort(key=lambda x: os.fsencode(x['path']))
    groups = [sorted(paths, key=os.fsencode) for paths in links.values()]
    groups.sort(key=lambda paths: os.fsencode(paths[0]))
    return dict(schema=SCHEMA, entries=entries, hardlink_groups=groups)


def differences(expected, actual):
    if not isinstance(expected, dict) or expected.get('schema') != SCHEMA:
        raise ValueError('unexpected schema')
    left = expected.get('entries')
    if not isinstance(left, list) or any(not isinstance(e, dict) or not isinstance(e.get('path'), str) for e in left):
        raise ValueError('invalid expected entries')
    mapping = {e['path']: e for e in left}
    if len(mapping) != len(left):
        raise ValueError('duplicate expected paths')
    right = {e['path']: e for e in actual['entries']}
    result = []
    for path in sorted(set(mapping) | set(right), key=os.fsencode):
        if mapping.get(path) != right.get(path):
            result.append(dict(path=path, expected=mapping.get(path), actual=right.get(path)))
    if expected.get('hardlink_groups') != actual['hardlink_groups']:
        result.append(dict(field='hardlink_groups', expected=expected.get('hardlink_groups'), actual=actual['hardlink_groups']))
    return result


def emit(value):
    print(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'verify'])
    parser.add_argument('root')
    args = parser.parse_args()
    try:
        expected = json.load(sys.stdin) if args.action == 'verify' else None
        actual = snapshot(args.root)
        if args.action == 'snapshot':
            emit(actual)
            return 0
        mismatches = differences(expected, actual)
        emit(dict(ok=not mismatches, differences=mismatches, entries=len(actual['entries'])))
        return 1 if mismatches else 0
    except (OSError, ValueError, TypeError) as error:
        emit(dict(ok=False, error=str(error)))
        return 2


if __name__ == '__main__':
    sys.exit(main())
