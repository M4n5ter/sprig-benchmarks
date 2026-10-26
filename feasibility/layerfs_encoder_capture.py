#!/usr/bin/env python3
"""Bounded capture for owned source-only compiler/proof children, never a daemon."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time

MIB = 1024 * 1024
CHUNK = 64 * 1024
DRAIN_RESERVE = MIB
TERM_GRACE = 2.0
DRAIN_GRACE = 5.0
BUILD = ['cargo', '+1.85.1', 'build', '--manifest-path', 'core/Cargo.toml',
         '--locked', '--offline', '--release', '-p', 'layerfs-daemon',
         '--message-format=json', '-vv']
FETCH = ['cargo', '+1.85.1', 'fetch', '--manifest-path', 'core/Cargo.toml', '--locked']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def new_path(path):
    path = Path(os.path.abspath(path))
    require(path.parent.resolve(strict=True) == path.parent, 'noncanonical output parent')
    require(not path.exists() and not path.is_symlink(), 'output already exists')
    return path


def validate_command(stage, argv):
    require(isinstance(argv, list) and 1 <= len(argv) <= 16 and
            all(isinstance(x, str) and x and '\0' not in x and len(x) <= 4096 for x in argv),
            'invalid command argv')
    if stage == 'fetch':
        require(argv == FETCH, 'not the fixed locked fetch')
    elif stage == 'build':
        require(argv == BUILD, 'not the fixed production daemon build')
    elif stage == 'compile':
        require(len(argv) == 10 and argv[:3] == ['rustc', '+1.85.1', '--edition=2021']
                and Path(argv[3]).is_absolute() and Path(argv[3]).name == 'proof.rs'
                and argv[4] == '--extern' and argv[5].startswith('layerfs_bridge=/')
                and argv[6] == '-L' and argv[7].startswith('dependency=/')
                and argv[8] == '-o' and Path(argv[9]).is_absolute()
                and Path(argv[9]).name == 'layerfs-encoder-proof', 'not the external proof compile')
    elif stage == 'proof':
        require(len(argv) == 1 and Path(argv[0]).is_absolute()
                and Path(argv[0]).name == 'layerfs-encoder-proof', 'not the external proof executable')
    else:
        raise ValueError('unknown source-only stage')


def capture(argv, cwd, stdout_path, stderr_path, receipt_path, seconds, cap,
            drain_reserve=DRAIN_RESERVE):
    """The CLI allowlists argv; tests call this with inert Python children only."""
    require(type(seconds) is int and 1 <= seconds <= 2400, 'invalid finite deadline')
    require(type(cap) is int and 0 < cap <= 32 * MIB, 'invalid stream cap')
    require(type(drain_reserve) is int and 0 <= drain_reserve <= MIB, 'invalid drain reserve')
    cwd = Path(os.path.abspath(cwd))
    require(cwd.resolve(strict=True) == cwd and cwd.is_dir(), 'noncanonical cwd')
    paths = [new_path(p) for p in (stdout_path, stderr_path, receipt_path)]
    require(len(set(paths)) == 3, 'output paths must differ')
    started = time.monotonic()
    errors, signals = [], []
    streams = {}
    proc = None
    owned_group_verified = False
    group_settled = False
    selector = selectors.DefaultSelector()
    stopping = None
    killed = False
    try:
        for name, path in zip(('stdout', 'stderr'), paths[:2]):
            output = path.open('xb')
            streams[name] = {'file': output, 'path': str(path), 'received': 0,
                             'retained': 0, 'discarded': 0, 'digest': hashlib.sha256(),
                             'retainedDigest': hashlib.sha256(), 'eof': False}
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True, close_fds=True)
        except OSError as error:
            errors.append('spawn_failed:' + type(error).__name__)
        if proc is not None:
            # start_new_session gives this child, and only its descendants, a new pgid.
            require(os.getpgid(proc.pid) == proc.pid, 'child does not own a new process group')
            owned_group_verified = True
            for name, pipe in (('stdout', proc.stdout), ('stderr', proc.stderr)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, name)
            parent_exited = None

            def send_owned(sig):
                try:
                    os.killpg(proc.pid, sig)
                    signals.append({'signal': sig.name, 'elapsedSeconds': time.monotonic() - started})
                except ProcessLookupError:
                    signals.append({'signal': sig.name, 'groupAlreadyGone': True,
                                    'elapsedSeconds': time.monotonic() - started})

            def stop(reason):
                nonlocal stopping
                if reason not in errors:
                    errors.append(reason)
                if stopping is None:
                    stopping = time.monotonic()
                    send_owned(signal.SIGTERM)

            def group_alive():
                try:
                    os.killpg(proc.pid, 0)
                    return True
                except ProcessLookupError:
                    return False

            while True:
                parent_done = proc.poll() is not None
                alive = group_alive()
                if not selector.get_map() and parent_done and not alive:
                    group_settled = True
                    if time.monotonic() - started >= seconds and 'deadline_exceeded' not in errors:
                        errors.append('deadline_exceeded')
                    break
                now = time.monotonic()
                if parent_done and alive:
                    stop('owned_group_remained_after_parent_exit')
                if now - started >= seconds:
                    stop('deadline_exceeded')
                if proc.poll() is not None:
                    if parent_exited is None:
                        parent_exited = now
                    if selector.get_map() and now - parent_exited >= 1:
                        stop('descendant_pipes_remained_open')
                if stopping is not None:
                    if not killed and now - stopping >= TERM_GRACE:
                        send_owned(signal.SIGKILL)
                        killed = True
                    if now - stopping >= DRAIN_GRACE:
                        stop('drain_deadline_exceeded')
                        break
                for key, _ in selector.select(0.05):
                    record = streams[key.data]
                    try:
                        chunk = os.read(key.fileobj.fileno(), CHUNK)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        record['eof'] = True
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    record['received'] += len(chunk)
                    record['digest'].update(chunk)
                    remaining = cap + drain_reserve - record['retained']
                    saved = chunk[:max(0, remaining)]
                    record['file'].write(saved)
                    record['retained'] += len(saved)
                    record['retainedDigest'].update(saved)
                    record['discarded'] += len(chunk) - len(saved)
                    if record['received'] > cap:
                        stop(key.data + '_overflow')
            if proc.poll() is None:
                if stopping is None:
                    stop('child_wait_incomplete')
                if not killed:
                    send_owned(signal.SIGKILL)
                    killed = True
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    errors.append('child_exit_unknown')
    except (OSError, ValueError) as error:
        errors.append('capture_error:' + type(error).__name__)
        if proc is not None:
            # Never signal a group unless its ownership was verified after spawn.
            try:
                if owned_group_verified:
                    os.killpg(proc.pid, signal.SIGKILL)
                    signals.append({'signal': 'SIGKILL', 'reason': 'capture_error'})
                elif proc.poll() is None:
                    proc.kill()
                    signals.append({'signal': 'SIGKILL', 'scope': 'owned-child-only', 'reason': 'unverified-group'})
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                errors.append('child_exit_unknown')
    finally:
        for key in list(selector.get_map().values()):
            selector.unregister(key.fileobj)
            key.fileobj.close()
        selector.close()
        if proc is not None:
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
        for record in streams.values():
            record['file'].close()
    rc = None if proc is None else proc.poll()
    complete = proc is not None and rc is not None and group_settled and all(s['eof'] for s in streams.values())
    retained = complete and all(s['discarded'] == 0 for s in streams.values())
    accepted = complete and retained and rc == 0 and not errors
    rows = {name: {'path': s['path'], 'receivedBytes': s['received'],
                   'retainedBytes': s['retained'], 'discardedBytes': s['discarded'],
                   'receivedSha256': s['digest'].hexdigest(),
                   'retainedSha256': s['retainedDigest'].hexdigest(), 'eof': s['eof'],
                   'unobservedBytes': 0 if s['eof'] or proc is None else None}
            for name, s in streams.items()}
    receipt = {'schema': 'layerfs-source-only-capture-v1', 'argv': argv, 'cwd': str(cwd),
               'accepted': accepted, 'processStarted': proc is not None,
               'ownedProcessGroup': proc.pid if owned_group_verified else None,
               'ownedGroupSettled': group_settled,
               'processReturncode': rc, 'deadlineSeconds': seconds,
               'elapsedSeconds': time.monotonic() - started, 'streamAcceptanceCapBytes': cap,
               'perStreamDrainReserveBytes': drain_reserve,
               'hardRetainedStreamBytes': cap + drain_reserve,
               'captureComplete': complete, 'allObservedBytesRetained': retained,
               'errors': errors, 'signals': signals, 'streams': rows,
               'mountedProcess': False, 'daemonInvoked': False}
    data = (json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode()
    require(len(data) <= 2 * MIB, 'capture receipt exceeds cap')
    with paths[2].open('xb') as f:
        f.write(data)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['fetch', 'build', 'compile', 'proof'])
    for name in ('argv-json', 'cwd', 'stdout', 'stderr', 'receipt'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--seconds', required=True, type=int)
    args = parser.parse_args()
    p = Path(args.argv_json)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 65536, 'bad argv file')
    argv = json.loads(p.read_text())
    validate_command(args.stage, argv)
    cap = 32 * MIB if args.stage in ('fetch', 'build') else MIB
    receipt = capture(argv, args.cwd, args.stdout, args.stderr, args.receipt, args.seconds, cap)
    return 0 if receipt['accepted'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print('source-only capture rejected: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
