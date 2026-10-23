#!/usr/bin/env python3
"""Fixed same-runner A/B experiment. No source patches or comparator runtime."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from cas_sample import filesystem_used
from production_ab_sample import PINS

CASES = ['history-distributed', 'history-hotset', 'history-recurring', 'history-small-control']
BACKENDS = ['native', 'projection']
PAIRS = 5
SIZE = 2 * 1024**3
RESERVE = 8 * 1024**3


def command(args):
    return subprocess.check_output([str(x) for x in args], text=True, stderr=subprocess.PIPE)


def save(path, data):
    # Harness records are outside the measured filesystem; publish after each stage.
    with path.open('w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def empty_space(mount):
    command(['btrfs', 'filesystem', 'sync', mount])
    usage = command(['btrfs', 'filesystem', 'usage', '-b', mount])
    return {'filesystemUsedBytes': filesystem_used(usage), 'usageRaw': usage,
            'groupsRaw': command(['btrfs', 'filesystem', 'df', '-b', mount])}


def validate(sample, label, backend):
    assert sample['ok'] and not sample['prototype_only']
    assert sample['production_sha'] == PINS[label] and sample['backend'] == backend
    for field in ['init_seconds', 'import_seconds', 'first_fork_seconds', 'first_read_seconds',
                  'total_import_fork_read_seconds', 'warm_fork_seconds', 'warm_read_seconds',
                  'warm_total_seconds', 'write_seconds', 'checkpoint_seconds']:
        v = sample[field]
        assert type(v) in (int, float) and math.isfinite(v) and v >= 0, field
    assert sample['history_distinct_revisions'] == 100
    assert len(sample['checkpoint_steps']) == 100 and sample['fullHistoricalSnapshotReadbacks'] == 100
    assert all(sample[k] for k in ['allAcknowledgedIdsPresent', 'sourceUnchanged',
                                 'originalMainViewUnchanged', 'originalSecondViewUnchanged'])
    assert sample['remainingMounts'] == [] and sample['lifecycle']['cleanup']['complete']
    active = sample['lifecycle']['activeAtSpace']
    assert len(active['views']) == 3 and not active['historicalReadbacksStarted']
    assert len(active['foregroundFuseProcesses']) == (3 if backend == 'projection' else 0)
    assert active['controlProcessesRunning'] == (3 if backend == 'projection' else 0)


def run():
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.geteuid() == 0
    temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    cwd = Path.cwd().resolve(strict=True)
    results = cwd / 'results'
    results.mkdir(exist_ok=True)
    ledger = temp / 'production-ab-records'
    ledger.mkdir(exist_ok=False)
    built = json.loads((results / 'ab-builds.json').read_text())
    binary_hashes = {}
    for label, sha in PINS.items():
        checkout = cwd / ('sprig-' + label)
        assert built[label]['sha'] == sha
        binary = checkout / 'target/release/sprig'
        binary_hashes[label] = hashlib.sha256(binary.read_bytes()).hexdigest()
        assert binary_hashes[label] == built[label]['binarySha256']
    small = cwd / 'fixtures/history-small-control'
    assert len(list(small.iterdir())) == 8
    assert all(p.is_file() and not p.is_symlink() for p in small.iterdir())
    schedule = []
    for pair in range(PAIRS):
        for ci, case in enumerate(CASES):
            for backend in (BACKENDS if (pair + ci) % 2 == 0 else BACKENDS[::-1]):
                bi = BACKENDS.index(backend)
                order = ['baseline', 'candidate'] if (pair + ci + bi) % 2 == 0 else ['candidate', 'baseline']
                schedule.append({'pair': pair, 'case': case, 'backend': backend, 'order': order})
    report = {'pins': PINS, 'binaryHashes': binary_hashes, 'schedule': schedule,
              'expectedRecords': 80, 'expectedHistoricalReadbacks': 8000,
              'complete': False, 'records': [], 'pairCleanup': [],
              'postBuildDisk': dict(zip(['total', 'used', 'free'], shutil.disk_usage(temp)))}
    output = results / 'production-ab.json'
    save(output, report)
    try:
        for plan in schedule:
            capacity = shutil.disk_usage(temp)
            assert capacity.free >= 2 * SIZE + RESERVE, 'insufficient space for whole A/B pair and reserve'
            images = []
            for label in plan['order']:
                r = {**plan, 'revision': label, 'correct': False, 'freeBeforePair': capacity.free}
                report['records'].append(r)
                save(output, report)
                directory = Path(tempfile.mkdtemp(prefix='sprig-ab-', dir=temp))
                image, mount = directory / 'new.img', directory / 'mount'
                with image.open('xb') as f:
                    f.truncate(SIZE)
                identity = (image.stat().st_dev, image.stat().st_ino)
                mount.mkdir()
                r['filesystem'] = {'image': str(image), 'mount': str(mount)}
                save(output, report)
                r['filesystem']['mkfs'] = command(['mkfs.btrfs', '-d', 'single', '-m', 'dup', image])
                child_started = False
                unmount_attempted = False
                try:
                    command(['mount', '-o', 'loop,noatime', image, mount])
                    assert command(['stat', '-f', '-c', '%T', mount]).strip() == 'btrfs'
                    r['filesystem']['empty'] = empty_space(mount)
                    source = cwd / 'fixtures' / plan['case']
                    args = ['/usr/bin/python3', cwd / 'feasibility/production_ab_sample.py', label,
                        'run', '--root', mount / 'store', '--source', source,
                        '--oracle', str(source) + '.json', '--steps', str(source) + '-steps.json',
                        '--binary', cwd / ('sprig-' + label) / 'target/release/sprig',
                        '--backend', plan['backend'], '--records',
                        ledger / f"{plan['backend']}-{plan['case']}-{plan['pair']}-{label}.jsonl"]
                    started = time.monotonic()
                    child_started = True
                    proc = subprocess.run([str(x) for x in args], text=True, capture_output=True)
                    r['sampleWallSeconds'] = time.monotonic() - started
                    r['sampleStderr'] = proc.stderr
                    try:
                        r['sample'] = json.loads(proc.stdout)
                    except Exception:
                        r['invalidSampleStdout'] = proc.stdout
                        raise
                    save(output, report)
                    assert proc.returncode == 0, 'sample failed; preserve image and mount diagnostics'
                    validate(r['sample'], label, plan['backend'])
                    r['filesystemUsedDeltaBytes'] = (r['sample']['activeSpace']['filesystemUsedBytes']
                        - r['filesystem']['empty']['filesystemUsedBytes'])
                    assert r['filesystemUsedDeltaBytes'] >= 0
                    unmount_attempted = True
                    command(['umount', '-i', mount])
                    assert subprocess.run(['mountpoint', '-q', str(mount)]).returncode == 32
                    r['correct'] = True
                    images.append((image, mount, identity))
                    save(output, report)
                    print(json.dumps({**plan, 'revision': label, 'correct': True,
                          'sampleWallSeconds': r['sampleWallSeconds']}), flush=True)
                finally:
                    if not r['correct']:
                        diagnostic = {'imagePreserved': True, 'mount': str(mount), 'image': str(image)}
                        diagnostic['mountinfo'] = Path('/proc/self/mountinfo').read_text()
                        try:
                            diagnostic['loopDevices'] = command(['losetup', '-j', image])
                            mounted = subprocess.run(['mountpoint', '-q', str(mount)]).returncode == 0
                            child_clean = r.get('sample', {}).get('lifecycle', {}).get('cleanup', {}).get('complete') is True
                            if mounted and not unmount_attempted and (not child_started or child_clean):
                                command(['umount', '-i', mount])
                                diagnostic['ordinaryUnmount'] = 'success'
                            elif mounted:
                                diagnostic['ordinaryUnmount'] = 'preserved: prior ordinary unmount failed or child teardown unconfirmed'
                            else:
                                diagnostic['ordinaryUnmount'] = 'not mounted'
                        except Exception as cleanup:
                            diagnostic['cleanupError'] = str(cleanup)
                            diagnostic['cleanupStderr'] = getattr(cleanup, 'stderr', None)
                        r['failureLifecycle'] = diagnostic
                        save(output, report)
            # Only completed, fully verified pairs may dispose their own unmounted images.
            clean = {**plan, 'complete': False, 'images': []}
            report['pairCleanup'].append(clean)
            for image, mount, identity in images:
                assert image.parent.parent == temp and image.parent.name.startswith('sprig-ab-')
                info = image.lstat()
                assert stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == identity
                assert image.resolve(strict=True) == image
                assert subprocess.run(['mountpoint', '-q', str(mount)]).returncode == 32
                for attempt in range(20):
                    loops = command(['losetup', '-j', image]).strip()
                    if not loops:
                        break
                    time.sleep(0.25)
                assert not loops, 'loop still attached; preserve image'
                clean['images'].append({'path': str(image), 'allocatedBytes': info.st_blocks * 512,
                                        'bytes': info.st_size, 'removed': False})
                save(output, report)
                image.unlink()
                clean['images'][-1]['removed'] = True
                save(output, report)
            clean['complete'] = True
            save(output, report)
        assert len(report['records']) == 80 and all(r['correct'] for r in report['records'])
        assert len(report['pairCleanup']) == 40 and all(p['complete'] for p in report['pairCleanup'])
        report['complete'] = True
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error),
                           'stderr': getattr(error, 'stderr', None)}
        raise
    finally:
        save(output, report)


if __name__ == '__main__':
    run()
